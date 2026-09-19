"""
seed_db.py — Populates CampusPulse with authentic UAH campus facilities,
realistic mock check-in data, and active study sessions using UAH course codes.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import engine, SessionLocal
from models import Base, Location, CardTap, StudySession, CampusEvent, UserRegistration, EventRegistration
from datetime import datetime, timedelta
import hashlib
import random

Base.metadata.create_all(bind=engine)

db = SessionLocal()

# ── Clear existing data ────────────────────────────────────────────────────────
db.query(CardTap).delete()
db.query(StudySession).delete()
db.query(Location).delete()
db.query(CampusEvent).delete()
db.query(UserRegistration).delete()
db.query(EventRegistration).delete()
db.commit()

# ── 8 UAH Campus Locations ─────────────────────────────────────────────────────
# Coordinates are accurate UAH campus positions (Huntsville, AL)
locations_data = [
    {
        "name": "M. Louis Salmon Library - Floor 1",
        "category": "Study Area",
        "max_capacity": 150,
        "current_count": 47,
        "latitude": 34.72476,
        "longitude": -86.64065,
    },
    {
        "name": "M. Louis Salmon Library - Quiet Floor 3",
        "category": "Study Area",
        "max_capacity": 80,
        "current_count": 68,
        "latitude": 34.72480,
        "longitude": -86.64060,
    },
    {
        "name": "Charger Union (CGU) Food Court",
        "category": "Dining Hall",
        "max_capacity": 250,
        "current_count": 183,
        "latitude": 34.72398,
        "longitude": -86.63956,
    },
    {
        "name": "University Fitness Center (UFC)",
        "category": "Gym",
        "max_capacity": 120,
        "current_count": 97,
        "latitude": 34.72318,
        "longitude": -86.64120,
    },
    {
        "name": "Morton Hall Study Lounge",
        "category": "Study Area",
        "max_capacity": 60,
        "current_count": 18,
        "latitude": 34.72551,
        "longitude": -86.64001,
    },
    {
        "name": "Olin B. King Technology Hall (OKT) Lab",
        "category": "Study Area",
        "max_capacity": 90,
        "current_count": 54,
        "latitude": 34.72440,
        "longitude": -86.63870,
    },
    {
        "name": "Shelby Center for Science & Tech (SST)",
        "category": "Study Area",
        "max_capacity": 110,
        "current_count": 29,
        "latitude": 34.72370,
        "longitude": -86.63780,
    },
    {
        "name": "Charger Village Food Court",
        "category": "Dining Hall",
        "max_capacity": 180,
        "current_count": 142,
        "latitude": 34.72210,
        "longitude": -86.63990,
    },
]

locations = []
for loc_data in locations_data:
    loc = Location(**loc_data)
    db.add(loc)
    locations.append(loc)

db.commit()
for loc in locations:
    db.refresh(loc)

print(f"[OK] Inserted {len(locations)} UAH locations.")

# ── Mock CardTap history ───────────────────────────────────────────────────────
now = datetime.utcnow()
taps = []
for loc in locations:
    for i in range(loc.current_count):
        student_id = f"charger_{random.randint(1000, 9999)}_{i}"
        student_hash = hashlib.sha256(student_id.encode()).hexdigest()[:16]
        tap_time = now - timedelta(minutes=random.randint(5, 180))
        taps.append(CardTap(
            location_id=loc.id,
            student_hash=student_hash,
            timestamp=tap_time,
        ))

db.bulk_save_objects(taps)
db.commit()
print(f"[OK] Inserted {len(taps)} card tap records.")

# ── 4 Active UAH Study Sessions ────────────────────────────────────────────────
loc_by_name = {loc.name: loc for loc in locations}

study_sessions_data = [
    {
        "room_id": loc_by_name["M. Louis Salmon Library - Quiet Floor 3"].id,
        "course_code": "MA 172",
        "creator_name": "Jordan Hayes",
        "description": "Calculus II — integrals, sequences & series. Exam 2 prep. Bring your notes!",
        "open_status": True,
        "max_participants": 8,
        "current_participants": 4,
    },
    {
        "room_id": loc_by_name["Olin B. King Technology Hall (OKT) Lab"].id,
        "course_code": "CS 121",
        "creator_name": "Priya Nair",
        "description": "CS I — Python functions, loops, and debugging. All skill levels welcome.",
        "open_status": True,
        "max_participants": 10,
        "current_participants": 3,
    },
    {
        "room_id": loc_by_name["Shelby Center for Science & Tech (SST)"].id,
        "course_code": "PH 111",
        "creator_name": "Marcus Webb",
        "description": "General Physics I — kinematics and Newton's laws. Working through problem sets.",
        "open_status": True,
        "max_participants": 6,
        "current_participants": 5,
    },
    {
        "room_id": loc_by_name["Morton Hall Study Lounge"].id,
        "course_code": "BY 119",
        "creator_name": "Aisha Coleman",
        "description": "Principles of Biology — cell structure & metabolism. Quiz review session.",
        "open_status": True,
        "max_participants": 7,
        "current_participants": 2,
    },
]

sessions = []
for sdata in study_sessions_data:
    session = StudySession(**sdata)
    db.add(session)
    sessions.append(session)

db.commit()
print(f"[OK] Inserted {len(sessions)} UAH study sessions.")

# ── UAH Campus Events ──────────────────────────────────────────────────────────
# created_at set slightly in the future so it sorts to the TOP of the feed
campus_events_data = [
    {
        "title": "UAH Salmon Library Crafting Circle & Study Break",
        "location_name": "M. Louis Salmon Library - 1st Floor Lounge",
        "category": "Library Event",
        "description": "Join fellow Chargers for a relaxation study break! Crafts, coffee, and free snacks provided. All majors welcome — no sign-up required, just show up!",
        "max_participants": 30,
        "current_participants": 12,
        "open_status": True,
        "created_at": datetime.utcnow() + timedelta(seconds=10),  # pins to top
    },
]

events = []
for edata in campus_events_data:
    ev = CampusEvent(**edata)
    db.add(ev)
    events.append(ev)

db.commit()
print(f"[OK] Inserted {len(events)} campus events.")

db.close()
print("UAH CampusPulse database seeded successfully!")
