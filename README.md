# FlowSync — Urban Mobility Intelligence

FlowSync is a full-stack, locally runnable smart-city traffic management prototype. It combines a React dashboard with a FastAPI service, a persisted SQLite traffic simulator, safe single-approach signal phases, emergency-corridor coordination, CSV analytics, demo role-based controls, and optional YOLO computer vision.

> **Data integrity:** the included network is a simulation. No real city sensors, camera streams, or real-world measurements are connected. The interface and API label simulated data. Media inference is only reported when a compatible YOLO model is configured; otherwise the upload returns an explicit setup error rather than sample detections.

## Project layout

```text
backend/
  app/
    db.py                 SQLite schema and reproducible demo seed
    engine.py             Transparent queue/wait/fairness signal rules
    main.py               FastAPI routes, simulation, auth, analytics and reports
    vision.py             Optional YOLO image/video inference
  tests/
    test_engine.py        Rule-level tests
    test_api.py           API, authorization and simulation integration tests
  requirements.txt
  requirements-dev.txt
  requirements-vision.txt
frontend/
  src/
    main.jsx
    ui/App.jsx            Responsive screens and REST API integration
    ui/api.js
    ui/styles.css
  package.json
  index.html
```

## Windows setup and run

Use two PowerShell terminals from the project root. Python 3.10+ and Node.js 18+ are recommended.

### Stage 1 — API and SQLite simulation

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The service runs at `http://localhost:8000`; interactive API docs are at `http://localhost:8000/docs`. The SQLite database is created and seeded as `backend/flowsync.db` on first startup. To use a different database, set `FLOWSYNC_DB` before starting the API.

Before starting the API, set unique, non-empty `FLOWSYNC_ADMIN_PASSWORD` and `FLOWSYNC_OPERATOR_PASSWORD` values in the current shell environment. Authentication is disabled for a role when its password is not configured. Keep real passwords in your local environment; do not put them in source files or commit them.

### Stage 2 — Dashboard

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`). The dashboard needs the API running. To use another API URL, copy `frontend/.env.example` to `frontend/.env.local`, change `VITE_API_URL`, and restart Vite.

The frontend advances the simulation by one simulated second every four seconds while **Live updates** is enabled. **Run simulation** advances an additional single tick. Pause automatic updates with the Live updates control.

### Stage 3 — Tests and production bundle

From `backend` in an activated virtual environment:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

From `frontend`:

```powershell
npm run build
```

## Demonstration scenario

1. Open the overview. Observe the seeded intersections, rolling simulation samples, alerts, network heatmap, and the persistent `SIMULATION MODE` indicator.
2. Open **Live traffic**. Observe the approaches and queues update from the simulator. Uploading is limited to media; a real camera feed is not connected.
3. Open **Emergency corridor**, choose an ambulance/fire engine and cardinal approach, and submit a request. Tick progression first clears the active intersection with yellow, then coordinates one corridor direction green across the separate simulated intersections. Confirm passage to restore normal yellow-clearance scheduling.
4. Open **Signal control**, sign in as an operator, and apply a manual direction override. It uses a yellow clearance before the requested green, and respects configured timing bounds.
5. Open **Analytics** to inspect persisted hourly/daily data, compare the transparent illustrative fixed/adaptive wait estimates, filter by date, and download a CSV that explicitly marks every row as simulated.
6. Open **Settings** and sign in as an administrator to change green timing bounds, pause/enable simulated intersections, and review the audit log.

Sign in with any non-empty username and the administrator or operator password configured in the API's environment. Role restrictions guard manual controls, emergency requests, settings changes, and audit-log access. This lightweight demo auth is not production-grade: tokens are in-memory; the allowed frontend origins are configurable with `FLOWSYNC_CORS_ORIGINS`.

## Optional computer vision

The default install deliberately avoids pulling the large model/runtime stack. Configure a compatible YOLO weights file that recognizes the desired classes, then install optional dependencies:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-vision.txt
$env:YOLO_MODEL_PATH = "C:\models\traffic-vehicles.pt"
uvicorn app.main:app --reload
```

The upload endpoint accepts JPG, JPEG, PNG, WebP, MP4, AVI, and MOV media up to 20 MB. It returns vehicle counts and source-image bounding boxes for classes recognized by the configured model. Video is sampled at up to eight frames, so its counts are detections across sampled frames, not unique vehicles. For best results, provide custom weights trained to distinguish emergency vehicles; general pretrained weights may not have ambulance/fire-engine classes. An unset/unavailable model produces a visible `503` setup error, not invented computer-vision output. Uploaded files are processed in a temporary local file and removed afterward.

## Signal and analytics behavior

- Each intersection has four approaches and only one green approach at a time. Yellow clearance is a separate phase before normal scheduler transitions and manual overrides.
- Adaptive green uses queue length and waiting time, bounded by administrator-configured limits (default 10–45 seconds).
- Direction choice scores queue, waiting time, and accumulated waiting age to balance demand and reduce starvation. Pedestrian crossing phases are **not** implemented in this prototype and must be added before real-world use.
- Emergency requests transition through `approaching` → `clearing` → `green-corridor` → `passed`. The route is simulated over three connected intersections. During corridor green, only the same requested cardinal approach is green at each junction; other approaches remain red. Operator confirmation clears the request early.
- SQLite stores road state, snapshots, emergency history, settings, and audit entries. Seeded analytics include two weeks of hourly, explicitly simulated demo history. Fixed/adaptive comparisons are formula-based estimates over stored queue samples, not measured production/control outcomes.
- The heatmap is a schematic visualization of simulated congestion, not a geographic basemap.

## API overview

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | API readiness |
| `POST /api/auth/login` | Demo operator/admin sign-in |
| `GET /api/dashboard` | Current intersection and KPI state |
| `POST /api/simulation/tick` | Advance and persist one simulated tick |
| `POST /api/signals/{id}/override` | Role-protected, clearance-safe override |
| `POST /api/emergencies` | Start a simulated emergency corridor |
| `POST /api/emergencies/{id}/pass` | Mark emergency vehicle as passed |
| `GET /api/analytics` | Stored hourly/daily patterns and comparisons |
| `GET /api/reports.csv` | Downloadable timestamped CSV |
| `GET/PATCH /api/settings` | Read or admin-update signal bounds |
| `GET /api/admin/intersections` | Administrator-only simulated intersection list |
| `PATCH /api/admin/intersections/{id}` | Administrator-only enable/pause action |
| `GET /api/audit` | Administrator-only audit history |
| `POST /api/detection/upload` | Validated optional image/video inference |

## Limitations and next steps

- No live cameras, city basemap/Leaflet integration, field sensors, SUMO connection, or real dispatch verification are included.
- Prototype passwords, in-memory bearer tokens, and permissive local development are unsuitable for production. Add identity-provider integration, persistent hashed credentials, token expiry/revocation, TLS, rate limits, and deployment secrets.
- Emergency routes currently follow a fixed three-intersection demo path and use a simulated operator confirmation; real deployments need authenticated vehicle telemetry, route planning, signal-controller integration, conflict analysis, and fail-safe validation.
- Pedestrian push buttons, accessibility timing, crosswalk conflict logic, transit priority, weather, lane geometry, and vehicle tracking/deduplication need dedicated design and testing.
- The rule-based optimizer is intentionally explainable; calibrate against local traffic counts and safety constraints before considering SUMO/reinforcement-learning experimentation.
- Analytics seed rows are demo history; strategy comparisons are illustrative estimates, not empirical fixed-vs-adaptive trials.
- Add persistence-backed auth, migrations, observability, load testing, and hardware-in-the-loop testing before operational deployment.
