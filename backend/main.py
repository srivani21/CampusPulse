"""
main.py — CampusPulse FastAPI application
REST + WebSocket endpoints for live heatmap, study group matchmaker,
and SMS / in-app event registration.
Serves frontend/index.html at root.
"""
import json
import hashlib
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import engine, get_db
from models import Base, Location, CardTap, StudySession, EventRegistration, UserRegistration, CampusEvent

logger = logging.getLogger("campuspulse")

# ── Dummy user profiles (demo login — no real auth needed) ────────────────────
DUMMY_USERS = {
    "std_01": {"user_id": "std_01", "name": "Alex Charger", "email": "alex@uah.edu",  "phone": "+12565550199"},
    "std_02": {"user_id": "std_02", "name": "Maya Lin",     "email": "maya@uah.edu",  "phone": "+12565550288"},
}

# ── App init & DB setup ────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CampusPulse API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── WebSocket connection manager ───────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception:
                dead.append(connection)
        for conn in dead:
            self.disconnect(conn)


manager = ConnectionManager()


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class TapRequest(BaseModel):
    location_id: int
    action: str  # "check_in" or "check_out"


class StudyGroupCreate(BaseModel):
    room_id: int
    course_code: str
    creator_name: str
    description: Optional[str] = ""
    max_participants: int = 10


class StudyGroupToggle(BaseModel):
    session_id: int
    open_status: bool


class StudyGroupJoin(BaseModel):
    session_id: int


class EventRegisterRequest(BaseModel):
    phone_number: str
    student_name: str


class UserEventRegisterRequest(BaseModel):
    user_id: str   # "std_01" or "std_02"


# ── Twilio SMS helper ──────────────────────────────────────────────────────────
def send_sms(to_number: str, body: str) -> None:
    """Send an SMS via Twilio if credentials are present, else mock to console."""
    sid   = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")

    if sid and token and from_number:
        try:
            from twilio.rest import Client
            Client(sid, token).messages.create(
                body=body,
                from_=from_number,
                to=to_number,
            )
            logger.info("SMS sent to %s", to_number)
        except Exception as exc:
            logger.error("Twilio send failed: %s", exc)
    else:
        # Graceful mock — no credentials required for demo
        logger.info("[MOCK SMS] To: %s | Body: %s", to_number, body)
        print(f"\n[MOCK SMS] To: {to_number}\n[MOCK SMS] Body: {body}\n")


# ── Helpers ────────────────────────────────────────────────────────────────────
def crowd_status(pct: float) -> str:
    if pct < 40:
        return "Quiet"
    elif pct <= 75:
        return "Moderate"
    return "Crowded"


def location_to_dict(loc: Location) -> dict:
    pct = round((loc.current_count / loc.max_capacity) * 100, 1) if loc.max_capacity else 0
    return {
        "id": loc.id,
        "name": loc.name,
        "category": loc.category,
        "max_capacity": loc.max_capacity,
        "current_count": loc.current_count,
        "latitude": loc.latitude,
        "longitude": loc.longitude,
        "crowd_percentage": pct,
        "status": crowd_status(pct),
    }


def session_to_dict(s: StudySession, db: Session) -> dict:
    loc = db.query(Location).filter(Location.id == s.room_id).first()
    return {
        "id": s.id,
        "room_id": s.room_id,
        "room_name": loc.name if loc else "Unknown",
        "course_code": s.course_code,
        "creator_name": s.creator_name,
        "description": s.description,
        "open_status": s.open_status,
        "max_participants": s.max_participants,
        "current_participants": s.current_participants,
        "created_at": s.created_at.isoformat(),
    }


def campus_event_to_dict(ev: CampusEvent, user_id: Optional[str] = None, db: Optional[Session] = None) -> dict:
    registered = False
    if user_id and db:
        registered = db.query(UserRegistration).filter(
            UserRegistration.user_id == user_id,
            UserRegistration.event_id == ev.id,
        ).first() is not None
    return {
        "id": ev.id,
        "title": ev.title,
        "location_name": ev.location_name,
        "category": ev.category,
        "description": ev.description,
        "max_participants": ev.max_participants,
        "current_participants": ev.current_participants,
        "open_status": ev.open_status,
        "created_at": ev.created_at.isoformat(),
        "registered": registered,
    }


# ── Frontend Serve ─────────────────────────────────────────────────────────────
@app.get("/")
def serve_frontend():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "CampusPulse API is live 🎓 — frontend not found"}


# ── REST Endpoints ─────────────────────────────────────────────────────────────
@app.get("/api/heatmap")
def get_heatmap(db: Session = Depends(get_db)):
    """Returns all locations with crowd_percentage and status."""
    locations = db.query(Location).all()
    return [location_to_dict(loc) for loc in locations]


@app.post("/api/tap")
async def card_tap(req: TapRequest, db: Session = Depends(get_db)):
    """Simulate a physical ID card scan. Broadcasts update via WebSocket."""
    loc = db.query(Location).filter(Location.id == req.location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if req.action == "check_in":
        if loc.current_count >= loc.max_capacity:
            raise HTTPException(status_code=400, detail="Location is at full capacity")
        loc.current_count += 1
    elif req.action == "check_out":
        if loc.current_count > 0:
            loc.current_count -= 1
    else:
        raise HTTPException(status_code=400, detail="action must be 'check_in' or 'check_out'")

    # Record the tap
    student_hash = hashlib.sha256(
        f"demo_{random.randint(1000, 9999)}_{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:16]
    tap = CardTap(location_id=loc.id, student_hash=student_hash, timestamp=datetime.utcnow())
    db.add(tap)
    db.commit()
    db.refresh(loc)

    loc_data = location_to_dict(loc)

    # Broadcast to all WebSocket clients
    await manager.broadcast({"type": "tap_update", "location": loc_data})

    # Notification
    pct = loc_data["crowd_percentage"]
    if pct >= 85:
        notif = f"⚠️ {loc.name} reached {pct}% capacity"
    elif req.action == "check_in":
        notif = f"📍 Someone checked into {loc.name} ({loc.current_count}/{loc.max_capacity})"
    else:
        notif = f"👋 Someone checked out of {loc.name} ({loc.current_count}/{loc.max_capacity})"

    await manager.broadcast({"type": "notification", "message": notif})
    return loc_data


@app.get("/api/study-groups")
def list_study_groups(
    course_code: Optional[str] = None,
    open_only: bool = False,
    db: Session = Depends(get_db),
):
    """Lists study sessions, optionally filtered by course_code or open_status."""
    query = db.query(StudySession)
    if course_code:
        query = query.filter(StudySession.course_code.ilike(f"%{course_code}%"))
    if open_only:
        query = query.filter(StudySession.open_status == True)
    sessions = query.order_by(StudySession.created_at.desc()).all()
    return [session_to_dict(s, db) for s in sessions]


@app.post("/api/study-groups")
async def create_study_group(req: StudyGroupCreate, db: Session = Depends(get_db)):
    """Creates a new study session and broadcasts it."""
    loc = db.query(Location).filter(Location.id == req.room_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Room/Location not found")

    session = StudySession(
        room_id=req.room_id,
        course_code=req.course_code.upper(),
        creator_name=req.creator_name,
        description=req.description,
        open_status=True,
        max_participants=req.max_participants,
        current_participants=1,
        created_at=datetime.utcnow(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    sdata = session_to_dict(session, db)

    await manager.broadcast({"type": "study_group_created", "session": sdata})
    await manager.broadcast({
        "type": "notification",
        "message": f"🔥 {req.course_code.upper()} Study Group formed in {loc.name}",
    })
    return sdata


@app.post("/api/study-groups/toggle")
async def toggle_study_group(req: StudyGroupToggle, db: Session = Depends(get_db)):
    """Toggle open/closed status of a study session."""
    session = db.query(StudySession).filter(StudySession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")

    session.open_status = req.open_status
    db.commit()
    db.refresh(session)

    sdata = session_to_dict(session, db)
    await manager.broadcast({"type": "study_group_updated", "session": sdata})
    return sdata


@app.post("/api/study-groups/join")
async def join_study_group(req: StudyGroupJoin, db: Session = Depends(get_db)):
    """Join a study session — increments current_participants."""
    session = db.query(StudySession).filter(StudySession.id == req.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Study session not found")
    if not session.open_status:
        raise HTTPException(status_code=400, detail="This session is closed")
    if session.current_participants >= session.max_participants:
        raise HTTPException(status_code=400, detail="Session is full")

    session.current_participants += 1
    db.commit()
    db.refresh(session)

    sdata = session_to_dict(session, db)
    await manager.broadcast({"type": "study_group_updated", "session": sdata})
    await manager.broadcast({
        "type": "notification",
        "message": f"👋 Someone joined {session.course_code} study group ({session.current_participants}/{session.max_participants})",
    })
    return sdata


@app.get("/api/locations")
def get_locations(db: Session = Depends(get_db)):
    """Returns all locations (for study group room picker)."""
    locations = db.query(Location).all()
    return [{"id": loc.id, "name": loc.name, "category": loc.category} for loc in locations]


# ── Event Registration ─────────────────────────────────────────────────────────
@app.post("/api/events/{event_id}/register")
async def register_for_event(
    event_id: int,
    req: EventRegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a student for a study session event.
    Sends an SMS via Twilio (or mocks to console) and broadcasts a WS alert.
    """
    session = db.query(StudySession).filter(StudySession.id == event_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Event / study session not found")

    loc = db.query(Location).filter(Location.id == session.room_id).first()
    location_name = loc.name if loc else "Campus"
    event_name = f"{session.course_code} Study Group"

    # Persist registration
    reg = EventRegistration(
        event_id=event_id,
        event_name=event_name,
        location_name=location_name,
        student_name=req.student_name,
        phone_number=req.phone_number,
        registered_at=datetime.utcnow(),
    )
    db.add(reg)
    db.commit()
    db.refresh(reg)

    # SMS (real or mocked)
    sms_body = (
        f"UAH CampusPulse: Hi {req.student_name}! "
        f"You are registered for {event_name} at {location_name}. "
        f"See you there! Go Chargers!"
    )
    send_sms(req.phone_number, sms_body)

    # Mask phone for public broadcast — show only last 4 digits
    digits = re.sub(r"\D", "", req.phone_number)[-4:] or "xxxx"
    masked_phone = f"+1 xxx-xxx-{digits}"

    # WebSocket broadcast
    await manager.broadcast({
        "type": "REGISTRATION_ALERT",
        "message": f"🔔 {req.student_name} registered for {event_name}!",
        "student_name": req.student_name,
        "event_name": event_name,
        "location_name": location_name,
        "phone_masked": masked_phone,
    })

    return {
        "success": True,
        "registration_id": reg.id,
        "event_name": event_name,
        "location_name": location_name,
        "student_name": req.student_name,
        "phone_masked": masked_phone,
        "sms_sent": bool(
            os.environ.get("TWILIO_ACCOUNT_SID")
            and os.environ.get("TWILIO_AUTH_TOKEN")
            and os.environ.get("TWILIO_PHONE_NUMBER")
        ),
    }


# ── Campus Events ──────────────────────────────────────────────────────────────
@app.get("/api/campus-events")
def list_campus_events(
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Return all campus events, newest first. Marks registered=True if user_id given."""
    events = db.query(CampusEvent).order_by(CampusEvent.created_at.desc()).all()
    return [campus_event_to_dict(ev, user_id, db) for ev in events]


@app.post("/api/campus-events/{event_id}/register")
async def register_campus_event(
    event_id: int,
    req: UserEventRegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a dummy user for a campus event. Sends SMS + WS broadcast."""
    user = DUMMY_USERS.get(req.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ev = db.query(CampusEvent).filter(CampusEvent.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Campus event not found")
    if not ev.open_status:
        raise HTTPException(status_code=400, detail="Event registration is closed")
    if ev.current_participants >= ev.max_participants:
        raise HTTPException(status_code=400, detail="Event is at full capacity")

    # Idempotent — ignore duplicate registrations
    existing = db.query(UserRegistration).filter(
        UserRegistration.user_id == req.user_id,
        UserRegistration.event_id == event_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Already registered for this event")

    # Persist
    ureg = UserRegistration(user_id=req.user_id, event_id=event_id)
    db.add(ureg)
    ev.current_participants += 1
    db.commit()
    db.refresh(ureg)
    db.refresh(ev)

    # SMS
    sms_body = (
        f"UAH CampusPulse: Hi {user['name']}! "
        f"You're registered for \"{ev.title}\" at {ev.location_name}. "
        f"See you there! Go Chargers! \U0001f4d8"
    )
    send_sms(user["phone"], sms_body)

    digits = re.sub(r"\D", "", user["phone"])[-4:] or "xxxx"
    masked_phone = f"+1 xxx-xxx-{digits}"

    # WS broadcast — push updated event + registration alert
    ev_data = campus_event_to_dict(ev, req.user_id, db)
    await manager.broadcast({"type": "campus_event_updated", "event": ev_data})
    await manager.broadcast({
        "type": "REGISTRATION_ALERT",
        "message": f"🔔 {user['name']} registered for \"{ev.title}\"!",
        "student_name": user["name"],
        "event_name": ev.title,
        "location_name": ev.location_name,
        "phone_masked": masked_phone,
    })

    return {
        "success": True,
        "event": ev_data,
        "student_name": user["name"],
        "phone_masked": masked_phone,
        "sms_sent": bool(
            os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN")
        ),
    }


@app.delete("/api/campus-events/{event_id}/register/{user_id}")
async def cancel_campus_event(
    event_id: int,
    user_id: str,
    db: Session = Depends(get_db),
):
    """Cancel / remove a user's registration from a campus event."""
    ureg = db.query(UserRegistration).filter(
        UserRegistration.user_id == user_id,
        UserRegistration.event_id == event_id,
    ).first()
    if not ureg:
        raise HTTPException(status_code=404, detail="Registration not found")

    ev = db.query(CampusEvent).filter(CampusEvent.id == event_id).first()
    if ev and ev.current_participants > 0:
        ev.current_participants -= 1

    db.delete(ureg)
    db.commit()

    if ev:
        ev_data = campus_event_to_dict(ev, user_id, db)
        await manager.broadcast({"type": "campus_event_updated", "event": ev_data})

    user = DUMMY_USERS.get(user_id, {})
    return {"success": True, "message": f"Registration cancelled for {user.get('name', user_id)}"}


# ── My Events (user profile hub) ───────────────────────────────────────────────
@app.get("/api/users/{user_id}/my-events")
def get_my_events(user_id: str, db: Session = Depends(get_db)):
    """Return all campus events this user has registered for."""
    if user_id not in DUMMY_USERS:
        raise HTTPException(status_code=404, detail="User not found")

    regs = (
        db.query(UserRegistration)
        .filter(UserRegistration.user_id == user_id)
        .order_by(UserRegistration.registered_at.desc())
        .all()
    )
    results = []
    for reg in regs:
        ev = db.query(CampusEvent).filter(CampusEvent.id == reg.event_id).first()
        if ev:
            d = campus_event_to_dict(ev, user_id, db)
            d["registered_at"] = reg.registered_at.isoformat()
            results.append(d)
    return results


@app.get("/api/users/{user_id}/profile")
def get_user_profile(user_id: str):
    """Return dummy user profile."""
    user = DUMMY_USERS.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── WebSocket ──────────────────────────────────────────────────────────────────
@app.websocket("/ws/live-map")
async def websocket_live_map(websocket: WebSocket, db: Session = Depends(get_db)):
    await manager.connect(websocket)
    # Send initial full state on connect
    locations = db.query(Location).all()
    await websocket.send_text(json.dumps({
        "type": "initial_state",
        "locations": [location_to_dict(loc) for loc in locations],
    }))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
