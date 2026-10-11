from __future__ import annotations

import csv
import io
import os
import secrets
from datetime import timedelta
from typing import Any

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import db
from .engine import DIRECTIONS, Road, build_intersection, choose_next_direction, green_duration, optimize_fixed_vs_adaptive, severity

app = FastAPI(title="FlowSync API", version="0.1.0", description="Clearly labelled urban traffic signal simulation.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FLOWSYNC_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
TOKENS: dict[str, tuple[str, str]] = {}


class LoginRequest(BaseModel):
    username: str
    password: str
    role: str = "operator"


class OverrideRequest(BaseModel):
    direction: str
    duration_seconds: int = Field(ge=3, le=90)


class EmergencyRequest(BaseModel):
    vehicle_type: str = Field(pattern="^(Ambulance|Fire engine)$")
    origin: str = Field(pattern="^(North|East|South|West)$")
    destination: str = Field(pattern="^(Central Square|River Bridge|Market Street)$")


class SettingsRequest(BaseModel):
    minimum_green: int = Field(ge=5, le=30)
    maximum_green: int = Field(ge=20, le=90)


class IntersectionUpdate(BaseModel):
    enabled: bool


@app.on_event("startup")
def startup() -> None:
    db.initialize()


def actor_from_token(authorization: str | None = Header(default=None)) -> tuple[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in to use this control.")
    identity = TOKENS.get(authorization[7:])
    if identity is None:
        raise HTTPException(status_code=401, detail="Session expired. Sign in again.")
    return identity


def require_role(*roles: str):
    def check(identity: tuple[str, str] = Depends(actor_from_token)) -> tuple[str, str]:
        if identity[1] not in roles:
            raise HTTPException(status_code=403, detail="Your role does not have permission for this action.")
        return identity
    return check


def setting(db_conn: Any, key: str, default: int) -> int:
    result = db_conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return int(result["value"]) if result else default


def intersection_payload(db_conn: Any, row: Any, emergency: dict[str, Any] | None = None) -> dict[str, Any]:
    roads = db_conn.execute("SELECT * FROM roads WHERE intersection_id = ?", (row["id"],)).fetchall()
    queues = {road["direction"]: road["queue_length"] for road in roads}
    waits = {road["direction"]: road["waiting_seconds"] for road in roads}
    counts = {road["direction"]: road["vehicle_count"] for road in roads}
    return build_intersection(row["name"], queues, waits, counts, row["phase_direction"], row["phase"], row["remaining_seconds"], emergency)


def current_emergency(db_conn: Any) -> dict[str, Any] | None:
    row = db_conn.execute("SELECT * FROM emergencies WHERE status IN ('approaching', 'clearing', 'green-corridor') ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return None
    return {
        "id": row["id"], "vehicle_type": row["vehicle_type"], "origin": row["origin"],
        "destination": row["destination"], "status": row["status"], "eta_seconds": row["eta_seconds"],
        "route": ["Central Square", "River Bridge", "Market Street"],
    }


def dashboard_payload(db_conn: Any) -> dict[str, Any]:
    emergency = current_emergency(db_conn)
    rows = db_conn.execute("SELECT * FROM intersections WHERE enabled = 1 ORDER BY name").fetchall()
    intersections = []
    for row in rows:
        extra = emergency if row["id"] == "central-square" else None
        intersections.append(intersection_payload(db_conn, row, extra))
    totals = db_conn.execute(
        "SELECT COALESCE(SUM(vehicle_count), 0) vehicles, COALESCE(SUM(queue_length), 0) queue, COALESCE(AVG(waiting_seconds), 0) wait FROM roads WHERE intersection_id IN (SELECT id FROM intersections WHERE enabled = 1)"
    ).fetchone()
    queue = int(totals["queue"])
    alerts = []
    for intersection in intersections:
        for road in intersection["roads"]:
            if road["congestion"] in ("High", "Critical"):
                alerts.append({"intersection": intersection["name"], "direction": road["direction"], "level": road["congestion"], "queue": road["queue_length"]})
    return {
        "data_mode": "SIMULATION",
        "updated_at": db.utc_now().isoformat(),
        "metrics": {
            "total_vehicles": int(totals["vehicles"]),
            "average_wait_seconds": round(float(totals["wait"])),
            "estimated_queue_length": queue,
            "congestion_level": severity(round(queue / max(len(intersections), 1) / 4)),
            "active_emergencies": 1 if emergency else 0,
        },
        "intersections": intersections,
        "alerts": alerts[:6],
        "emergency": emergency,
        "system_health": {"api": "operational", "database": "operational", "camera_feeds": "simulation only", "vision_model": "configured" if os.getenv("YOLO_MODEL_PATH") else "not configured"},
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "simulation"}


@app.post("/api/auth/login")
def login(request: LoginRequest) -> dict[str, str]:
    valid_roles = {"admin": os.getenv("FLOWSYNC_ADMIN_PASSWORD"), "operator": os.getenv("FLOWSYNC_OPERATOR_PASSWORD")}
    expected_password = valid_roles.get(request.role)
    if not expected_password or request.password != expected_password or not request.username.strip():
        raise HTTPException(status_code=401, detail="Username, role, or password is incorrect.")
    token = secrets.token_urlsafe(32)
    TOKENS[token] = (request.username.strip(), request.role)
    db.log_action(request.username.strip(), "login", {"role": request.role})
    return {"access_token": token, "username": request.username.strip(), "role": request.role}


@app.get("/api/dashboard")
def get_dashboard() -> dict[str, Any]:
    with db.connect() as connection:
        return dashboard_payload(connection)


@app.post("/api/simulation/tick")
def simulation_tick() -> dict[str, Any]:
    with db.connect() as connection:
        emergency = current_emergency(connection)
        minimum = setting(connection, "minimum_green", 10)
        maximum = setting(connection, "maximum_green", 45)
        intersections = connection.execute("SELECT * FROM intersections WHERE enabled = 1 ORDER BY id").fetchall()
        for intersection in intersections:
            roads_db = connection.execute("SELECT * FROM roads WHERE intersection_id = ?", (intersection["id"],)).fetchall()
            roads = [Road(r["direction"], r["vehicle_count"], r["queue_length"], r["waiting_seconds"]) for r in roads_db]
            now = intersection["phase_started"] + 1
            phase, direction, remaining = intersection["phase"], intersection["phase_direction"], intersection["remaining_seconds"] - 1
            next_green_seconds = intersection["next_green_seconds"]
            if emergency and (intersection["id"] == "central-square" or emergency["status"] == "green-corridor"):
                if emergency["status"] == "approaching":
                    connection.execute("UPDATE emergencies SET status = 'clearing' WHERE id = ?", (emergency["id"],))
                    phase, remaining = "yellow", 3
                elif emergency["status"] == "clearing":
                    connection.execute("UPDATE emergencies SET status = 'green-corridor' WHERE id = ?", (emergency["id"],))
                    direction, phase, remaining = emergency["origin"], "green", 10
                else:
                    if intersection["id"] == "central-square":
                        connection.execute("UPDATE emergencies SET eta_seconds = MAX(0, eta_seconds - 1) WHERE id = ?", (emergency["id"],))
                    direction, phase, remaining = emergency["origin"], "green", max(1, remaining)
            elif remaining <= 0 and phase == "green":
                phase, remaining = "yellow", 3
            elif remaining <= 0 and phase == "yellow":
                if intersection["next_green_seconds"] > 0:
                    direction = intersection["next_direction"]
                    remaining = intersection["next_green_seconds"]
                    next_green_seconds = 0
                else:
                    last = {r["direction"]: r["waiting_seconds"] for r in roads_db}
                    direction = choose_next_direction(roads, direction, last, now)
                    selected = next(road for road in roads if road.direction == direction)
                    remaining = green_duration(selected, minimum, maximum)
                phase = "green"

            for road in roads:
                queue = road.queue_length
                wait = road.waiting_seconds
                vehicles = road.vehicle_count
                if phase == "green" and direction == road.direction:
                    queue = max(0, queue - (2 if emergency and intersection["id"] == "central-square" else 1))
                    wait = max(0, wait - 4)
                    vehicles = max(queue, vehicles - 1)
                else:
                    queue = min(30, max(0, queue + (1 if (now + DIRECTIONS.index(road.direction)) % 3 == 0 else 0)))
                    wait = min(180, wait + 2)
                    vehicles = max(queue, min(50, vehicles + (1 if now % 5 == 0 else 0)))
                connection.execute(
                    "UPDATE roads SET vehicle_count=?, queue_length=?, waiting_seconds=? WHERE intersection_id=? AND direction=?",
                    (vehicles, queue, wait, intersection["id"], road.direction),
                )
            connection.execute(
                "UPDATE intersections SET phase_direction=?, phase=?, remaining_seconds=?, phase_started=?, next_green_seconds=? WHERE id=?",
                (direction, phase, remaining, now, next_green_seconds, intersection["id"]),
            )
            total_vehicles = sum(road.vehicle_count for road in roads)
            total_queue = sum(road.queue_length for road in roads)
            average_wait = round(sum(road.waiting_seconds for road in roads) / len(roads))
            connection.execute(
                "INSERT INTO snapshots (created_at, intersection_id, total_vehicles, average_wait, total_queue, congestion, phase_direction) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (db.utc_now().isoformat(), intersection["id"], total_vehicles, average_wait, total_queue, severity(round(total_queue / 4)), direction),
            )
        if emergency and emergency["status"] == "green-corridor" and emergency["eta_seconds"] <= 1:
            connection.execute("UPDATE emergencies SET status='passed', passed_at=? WHERE id=?", (db.utc_now().isoformat(), emergency["id"]))
            connection.execute("UPDATE intersections SET phase='yellow', remaining_seconds=3 WHERE id IN ('central-square', 'river-bridge', 'market-street')")
        return dashboard_payload(connection)


@app.post("/api/signals/{intersection_id}/override")
def signal_override(intersection_id: str, request: OverrideRequest, actor: tuple[str, str] = Depends(require_role("admin", "operator"))) -> dict[str, Any]:
    if request.direction not in DIRECTIONS:
        raise HTTPException(status_code=422, detail="Choose a valid cardinal direction.")
    with db.connect() as connection:
        if current_emergency(connection):
            raise HTTPException(status_code=409, detail="Manual signal overrides are paused while an emergency corridor is active.")
        row = connection.execute("SELECT * FROM intersections WHERE id = ?", (intersection_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Intersection not found.")
        minimum, maximum = setting(connection, "minimum_green", 10), setting(connection, "maximum_green", 45)
        if not minimum <= request.duration_seconds <= maximum:
            raise HTTPException(status_code=422, detail=f"Green time must be between {minimum} and {maximum} seconds.")
        connection.execute("UPDATE intersections SET next_direction=?, next_green_seconds=?, phase='yellow', remaining_seconds=3, phase_started=0 WHERE id=?", (request.direction, request.duration_seconds, intersection_id))
        db.log_action(actor[0], "manual_signal_override", {"intersection": row["name"], "direction": request.direction, "duration_seconds": request.duration_seconds}, connection)
        return intersection_payload(connection, connection.execute("SELECT * FROM intersections WHERE id=?", (intersection_id,)).fetchone(), current_emergency(connection))


@app.post("/api/emergencies")
def request_emergency(request: EmergencyRequest, actor: tuple[str, str] = Depends(require_role("admin", "operator"))) -> dict[str, Any]:
    with db.connect() as connection:
        existing = current_emergency(connection)
        if existing:
            raise HTTPException(status_code=409, detail="An emergency corridor is already active.")
        cursor = connection.execute(
            "INSERT INTO emergencies (vehicle_type, origin, destination, status, eta_seconds, created_at) VALUES (?, ?, ?, 'approaching', 12, ?)",
            (request.vehicle_type, request.origin, request.destination, db.utc_now().isoformat()),
        )
        db.log_action(actor[0], "emergency_corridor_requested", request.model_dump(), connection)
        return {"id": cursor.lastrowid, "vehicle_type": request.vehicle_type, "origin": request.origin, "destination": request.destination,
                "status": "approaching", "eta_seconds": 12, "route": ["Central Square", "River Bridge", "Market Street"]}


@app.post("/api/emergencies/{emergency_id}/pass")
def emergency_passed(emergency_id: int, actor: tuple[str, str] = Depends(require_role("admin", "operator"))) -> dict[str, str]:
    with db.connect() as connection:
        cursor = connection.execute("UPDATE emergencies SET status='passed', passed_at=? WHERE id=? AND status IN ('approaching','clearing','green-corridor')", (db.utc_now().isoformat(), emergency_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Active emergency request not found.")
        connection.execute("UPDATE intersections SET phase='yellow', remaining_seconds=3 WHERE id='central-square'")
        db.log_action(actor[0], "emergency_corridor_cleared", {"emergency_id": emergency_id}, connection)
    return {"status": "passed", "signal_status": "restoring normal operation"}


@app.get("/api/analytics")
def analytics(start: str | None = None, end: str | None = None) -> dict[str, Any]:
    with db.connect() as connection:
        query = "SELECT created_at, intersection_id, total_vehicles, average_wait, total_queue, congestion FROM snapshots WHERE 1=1"
        values: list[str] = []
        if start:
            query += " AND created_at >= ?"
            values.append(start)
        if end:
            query += " AND created_at <= ?"
            values.append(end)
        rows = connection.execute(query + " ORDER BY created_at", values).fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            hour = row["created_at"][11:13] + ":00"
            entry = grouped.setdefault(hour, {"hour": hour, "vehicles": 0, "wait": 0, "queue": 0, "samples": 0})
            entry["vehicles"] += row["total_vehicles"]
            entry["wait"] += row["average_wait"]
            entry["queue"] += row["total_queue"]
            entry["samples"] += 1
        chart = [{"hour": entry["hour"], "vehicles": entry["vehicles"] // entry["samples"], "wait": entry["wait"] // entry["samples"], "queue": entry["queue"] // entry["samples"]} for entry in grouped.values()]
        daily: dict[str, dict[str, Any]] = {}
        for row in rows:
            day = row["created_at"][:10]
            entry = daily.setdefault(day, {"date": day, "vehicles": 0, "wait": 0, "samples": 0})
            entry["vehicles"] += row["total_vehicles"]
            entry["wait"] += row["average_wait"]
            entry["samples"] += 1
        daily_chart = [{"date": day, "vehicles": v["vehicles"] // v["samples"], "wait": v["wait"] // v["samples"]} for day, v in daily.items()]
        all_queues = [row["total_queue"] for row in rows]
        comparison = optimize_fixed_vs_adaptive(all_queues)
        by_intersection = connection.execute("SELECT intersection_id, ROUND(AVG(total_queue)) queue, ROUND(AVG(average_wait)) wait, ROUND(AVG(total_vehicles)) vehicles FROM snapshots GROUP BY intersection_id").fetchall()
        return {"hourly": chart[-24:], "daily": daily_chart[-14:], "comparison": comparison,
                "intersections": [{"id": r["intersection_id"], "average_queue": r["queue"], "average_wait": r["wait"], "average_vehicles": r["vehicles"]} for r in by_intersection],
                "sample_count": len(rows), "data_mode": "SIMULATION"}


@app.get("/api/reports.csv")
def report_csv(start: str | None = None, end: str | None = None) -> StreamingResponse:
    with db.connect() as connection:
        query = "SELECT created_at, intersection_id, total_vehicles, average_wait, total_queue, congestion, phase_direction FROM snapshots WHERE 1=1"
        values: list[str] = []
        if start:
            query += " AND created_at >= ?"
            values.append(start)
        if end:
            query += " AND created_at <= ?"
            values.append(end)
        rows = connection.execute(query + " ORDER BY created_at", values).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp_utc", "intersection", "vehicles", "average_wait_seconds", "queue_length", "congestion", "green_direction", "data_mode"])
    for row in rows:
        writer.writerow([row["created_at"], row["intersection_id"], row["total_vehicles"], row["average_wait"], row["total_queue"], row["congestion"], row["phase_direction"], "SIMULATION"])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=flowsync-traffic-report.csv"})


@app.get("/api/audit")
def audit_log(_: tuple[str, str] = Depends(require_role("admin"))) -> list[dict[str, Any]]:
    with db.connect() as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()]


@app.get("/api/settings")
def get_settings() -> dict[str, int]:
    with db.connect() as connection:
        return {"minimum_green": setting(connection, "minimum_green", 10), "maximum_green": setting(connection, "maximum_green", 45)}


@app.get("/api/admin/intersections")
def list_managed_intersections(_: tuple[str, str] = Depends(require_role("admin"))) -> list[dict[str, Any]]:
    with db.connect() as connection:
        return [dict(row) for row in connection.execute("SELECT id, name, enabled FROM intersections ORDER BY name").fetchall()]


@app.patch("/api/admin/intersections/{intersection_id}")
def update_intersection(intersection_id: str, request: IntersectionUpdate, actor: tuple[str, str] = Depends(require_role("admin"))) -> dict[str, Any]:
    with db.connect() as connection:
        row = connection.execute("SELECT * FROM intersections WHERE id=?", (intersection_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Intersection not found.")
        connection.execute("UPDATE intersections SET enabled=? WHERE id=?", (int(request.enabled), intersection_id))
        db.log_action(actor[0], "intersection_enabled" if request.enabled else "intersection_disabled", {"intersection": row["name"]}, connection)
        return {"id": row["id"], "name": row["name"], "enabled": request.enabled}


@app.patch("/api/settings")
def update_settings(request: SettingsRequest, actor: tuple[str, str] = Depends(require_role("admin"))) -> dict[str, int]:
    if request.minimum_green >= request.maximum_green:
        raise HTTPException(status_code=422, detail="Minimum green must be less than maximum green.")
    with db.connect() as connection:
        connection.execute("INSERT OR REPLACE INTO settings VALUES ('minimum_green', ?)", (str(request.minimum_green),))
        connection.execute("INSERT OR REPLACE INTO settings VALUES ('maximum_green', ?)", (str(request.maximum_green),))
        db.log_action(actor[0], "signal_timing_settings_updated", request.model_dump(), connection)
    return request.model_dump()


@app.post("/api/detection/upload")
async def upload_for_detection(file: UploadFile = File(...)) -> dict[str, Any]:
    suffix = os.path.splitext(file.filename or "")[1].lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".avi", ".mov"}
    if suffix not in allowed:
        raise HTTPException(status_code=415, detail="Upload a JPG, PNG, WebP, MP4, AVI, or MOV file.")
    content_type = file.content_type or ""
    is_image, is_video = content_type.startswith("image/"), content_type.startswith("video/")
    if not is_image and not is_video:
        raise HTTPException(status_code=415, detail="The file content type must be an image or video.")
    data = await file.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Media must be 20 MB or smaller.")
    from .vision import detect_media
    try:
        return detect_media(data, file.filename or "upload", content_type)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
