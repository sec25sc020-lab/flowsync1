import tempfile
import unittest
import os
import secrets
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import db
from app.main import TOKENS, app


class FlowSyncApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "flowsync-test.db"
        self.db_patcher = patch.object(db, "DB_PATH", self.db_path)
        self.db_patcher.start()
        self.passwords = {"admin": secrets.token_urlsafe(), "operator": secrets.token_urlsafe()}
        self.credentials_patcher = patch.dict(os.environ, {
            "FLOWSYNC_ADMIN_PASSWORD": self.passwords["admin"],
            "FLOWSYNC_OPERATOR_PASSWORD": self.passwords["operator"],
        })
        self.credentials_patcher.start()
        TOKENS.clear()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        TOKENS.clear()
        self.credentials_patcher.stop()
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def sign_in(self, role="admin"):
        password = self.passwords[role]
        response = self.client.post("/api/auth/login", json={"username": "test-user", "password": password, "role": role})
        self.assertEqual(response.status_code, 200, response.text)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_login_is_rejected_when_role_password_is_not_configured(self):
        with patch.dict(os.environ, {"FLOWSYNC_ADMIN_PASSWORD": ""}):
            response = self.client.post(
                "/api/auth/login",
                json={"username": "test-user", "password": self.passwords["admin"], "role": "admin"},
            )
        self.assertEqual(response.status_code, 401)

    def test_dashboard_is_simulation_data_with_one_green_per_intersection(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        dashboard = response.json()
        self.assertEqual(dashboard["data_mode"], "SIMULATION")
        self.assertEqual(len(dashboard["intersections"]), 3)
        for intersection in dashboard["intersections"]:
            self.assertEqual(sum(road["signal"] == "green" for road in intersection["roads"]), 1)

    def test_localhost_and_loopback_frontend_origins_pass_cors(self):
        response = self.client.options(
            "/api/dashboard",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://127.0.0.1:5173")

    def test_override_has_clearance_then_applies_requested_direction_and_duration(self):
        headers = self.sign_in()
        response = self.client.post("/api/signals/central-square/override", headers=headers, json={"direction": "West", "duration_seconds": 18})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["phase"], "yellow")
        self.client.post("/api/simulation/tick")
        self.client.post("/api/simulation/tick")
        result = self.client.post("/api/simulation/tick").json()
        central = next(item for item in result["intersections"] if item["id"] == "central-square")
        self.assertEqual(central["phase"], "green")
        self.assertEqual(central["phase_direction"], "West")
        self.assertEqual(central["remaining_seconds"], 18)

    def test_emergency_advances_through_clearance_and_corridor_green_safely(self):
        headers = self.sign_in("operator")
        created = self.client.post("/api/emergencies", headers=headers, json={
            "vehicle_type": "Ambulance", "origin": "North", "destination": "Market Street",
        })
        self.assertEqual(created.status_code, 200, created.text)
        first_tick = self.client.post("/api/simulation/tick").json()
        central = next(item for item in first_tick["intersections"] if item["id"] == "central-square")
        self.assertEqual(central["phase"], "yellow")
        self.client.post("/api/simulation/tick")
        corridor = self.client.post("/api/simulation/tick").json()
        self.assertEqual(corridor["emergency"]["status"], "green-corridor")
        for intersection in corridor["intersections"]:
            self.assertLessEqual(sum(road["signal"] == "green" for road in intersection["roads"]), 1)

    def test_manual_override_is_rejected_during_an_active_emergency(self):
        headers = self.sign_in("operator")
        self.client.post("/api/emergencies", headers=headers, json={
            "vehicle_type": "Fire engine", "origin": "West", "destination": "Central Square",
        })
        response = self.client.post(
            "/api/signals/central-square/override", headers=headers,
            json={"direction": "East", "duration_seconds": 20},
        )
        self.assertEqual(response.status_code, 409)

    def test_operator_cannot_change_admin_timing_policy(self):
        response = self.client.patch(
            "/api/settings", headers=self.sign_in("operator"),
            json={"minimum_green": 12, "maximum_green": 40},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_pause_intersection_and_operator_cannot_manage_it(self):
        response = self.client.patch(
            "/api/admin/intersections/river-bridge", headers=self.sign_in("operator"),
            json={"enabled": False},
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.patch(
            "/api/admin/intersections/river-bridge", headers=self.sign_in("admin"),
            json={"enabled": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        dashboard = self.client.get("/api/dashboard").json()
        self.assertNotIn("river-bridge", [intersection["id"] for intersection in dashboard["intersections"]])

    def test_tick_persists_analytics_and_csv_marks_simulation(self):
        self.client.post("/api/simulation/tick")
        analytics = self.client.get("/api/analytics").json()
        self.assertGreater(analytics["sample_count"], 0)
        report = self.client.get("/api/reports.csv")
        self.assertEqual(report.status_code, 200)
        self.assertIn("SIMULATION", report.text)

    def test_seed_populates_two_weeks_of_hourly_analytics(self):
        analytics = self.client.get("/api/analytics").json()
        self.assertEqual(analytics["sample_count"], 14 * 24 * 3)
        self.assertEqual(len(analytics["hourly"]), 24)
        self.assertEqual(len(analytics["daily"]), 14)

    def test_media_upload_validates_type_and_does_not_fake_missing_vision(self):
        invalid = self.client.post(
            "/api/detection/upload",
            files={"file": ("notes.txt", b"not media", "text/plain")},
        )
        self.assertEqual(invalid.status_code, 415)
        with patch.dict(os.environ, {"YOLO_MODEL_PATH": ""}):
            unavailable = self.client.post(
                "/api/detection/upload",
                files={"file": ("traffic.jpg", b"image bytes", "image/jpeg")},
            )
        self.assertEqual(unavailable.status_code, 503)
        self.assertIn("YOLO_MODEL_PATH is not configured", unavailable.json()["detail"])


if __name__ == "__main__":
    unittest.main()
