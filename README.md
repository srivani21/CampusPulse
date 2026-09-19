# CampusPulse

> A single unified web application that fixes fragmented campus life — built for hackathon.

## Stack
- **Backend**: FastAPI (Python) + SQLAlchemy + SQLite
- **Frontend**: React 18 (CDN, no build step) + Tailwind CSS (CDN)
- **Real-time**: WebSockets (`/ws/live-map`)

## Features
| Feature | Description |
|---|---|
| 🗺️ Live Campus Heatmap | Real-time color-coded occupancy for 8 campus locations |
| 🔴🟡🟢 Crowd Status | Green/Yellow/Red badges with live % bar |
| 🪪 Simulate ID Tap | Check-in/out buttons update heatmap live for judges |
| 🎓 Study Matchmaker | Browse, filter, join open study sessions |
| ＋ Host Session | Modal to create a study group with course, room, seats |
| 📡 WebSocket Feed | Live notification ticker across all tabs |

## Quick Start

### Prerequisites
- Python 3.9+

### Windows (PowerShell)
```powershell
.\start.ps1
```

### Linux / macOS / WSL
```bash
chmod +x start.sh
./start.sh
```

### Manual steps
```bash
cd backend
pip install -r requirements.txt
python seed_db.py
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** in your browser.

API docs available at **http://localhost:8000/docs**

## Project Structure
```
campuspulse/
├── backend/
│   ├── main.py          ← FastAPI app + all endpoints + WebSocket
│   ├── models.py        ← SQLAlchemy ORM models
│   ├── database.py      ← DB engine + session
│   ├── seed_db.py       ← Seed script (8 locations + 4 study sessions)
│   └── requirements.txt
├── frontend/
│   └── index.html       ← Self-contained React + Tailwind UI
├── start.ps1            ← Windows quick-start
├── start.sh             ← Linux/macOS quick-start
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/heatmap` | All locations with crowd % and status |
| POST | `/api/tap` | Simulate ID card scan (check_in / check_out) |
| GET | `/api/study-groups` | List study sessions (filterable) |
| POST | `/api/study-groups` | Create a new study session |
| POST | `/api/study-groups/join` | Join a study session |
| POST | `/api/study-groups/toggle` | Toggle open/closed status |
| GET | `/api/locations` | List all locations |
| WS | `/ws/live-map` | WebSocket live updates feed |
