from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class EventRegistration(Base):
    """Legacy per-anonymous-registration record (kept for backward compat)."""
    __tablename__ = "event_registrations"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, nullable=False)
    event_name = Column(String, nullable=False)
    location_name = Column(String, nullable=False)
    student_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    registered_at = Column(DateTime, default=datetime.utcnow)


class UserRegistration(Base):
    """User-scoped registration — ties a dummy user_id to a campus event."""
    __tablename__ = "user_registrations"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_user_event"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)   # e.g. "std_01"
    event_id = Column(Integer, nullable=False, index=True) # CampusEvent.id
    registered_at = Column(DateTime, default=datetime.utcnow)


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)  # "Study Area", "Gym", "Dining Hall"
    max_capacity = Column(Integer, nullable=False)
    current_count = Column(Integer, default=0)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)


class CardTap(Base):
    __tablename__ = "card_taps"

    id = Column(Integer, primary_key=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    student_hash = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    course_code = Column(String, nullable=False)
    creator_name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    open_status = Column(Boolean, default=True)
    max_participants = Column(Integer, default=10)
    current_participants = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class CampusEvent(Base):
    """Official campus events (library events, socials, etc.)."""
    __tablename__ = "campus_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    location_name = Column(String, nullable=False)
    category = Column(String, nullable=False, default="Library Event")
    description = Column(String, nullable=True)
    max_participants = Column(Integer, default=30)
    current_participants = Column(Integer, default=0)
    open_status = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
