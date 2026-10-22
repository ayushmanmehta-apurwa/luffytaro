"""SQLAlchemy tables. Six tables are enough for the whole system."""
from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, Integer, LargeBinary, String, Text)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Ticket(Base):
    __tablename__ = 'tickets'
    id = Column(Integer, primary_key=True)
    workspace = Column(String, index=True, nullable=False)
    state = Column(String, default='NEW', index=True)
    issue_type = Column(String)
    department = Column(String, nullable=True)
    urgency = Column(String, default='medium')
    building = Column(String, nullable=True)          # campus location chosen from the list
    location_text = Column(String, nullable=True)     # building + free-text detail
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    summary = Column(Text)
    original_text = Column(Text, nullable=True)       # deleted by the privacy control
    language = Column(String, default='en')
    safety_hazard = Column(Boolean, default=False)
    missing_info = Column(JSON, default=list)
    followup_question = Column(String, nullable=True)
    confidence = Column(Float, default=0.0)
    needs_human = Column(Boolean, default=False)
    report_count = Column(Integer, default=1)
    reporter_ids = Column(JSON, default=list)
    ai_source = Column(String, default='demo')        # 'live' (NVIDIA models) or 'demo' (deterministic rules)
    synthetic = Column(Boolean, default=False)        # True for seeded sample data
    due_at = Column(DateTime, nullable=True)
    escalation_level = Column(Integer, default=0)
    last_verdict = Column(String, nullable=True)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, index=True)
    seq = Column(Integer)
    ts = Column(String)
    actor = Column(String)
    type = Column(String)
    payload = Column(JSON, nullable=True)             # can be deleted for privacy
    payload_sha256 = Column(String)                   # stays in the chain after deletion
    prev_hash = Column(String)
    hash = Column(String)


class Image(Base):
    __tablename__ = 'images'
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, index=True)
    workspace = Column(String, index=True)
    kind = Column(String)                             # 'report' or 'after'
    data = Column(LargeBinary)                        # resized JPEG (EXIF is read before resizing)
    sha256 = Column(String)                           # hash of the ORIGINAL upload
    phash = Column(String, nullable=True)
    exif_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime)


class Setting(Base):
    __tablename__ = 'settings'
    key = Column(String, primary_key=True)
    value = Column(String)


class Hotspot(Base):
    __tablename__ = 'hotspots'
    id = Column(Integer, primary_key=True)
    workspace = Column(String, index=True)
    created_at = Column(DateTime)
    source = Column(String)                           # 'job' | 'inline-live' | 'inline-demo'
    data = Column(JSON)


class Usage(Base):
    __tablename__ = 'usage'
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime, index=True)
    workspace = Column(String, index=True)
    step = Column(String)
    model = Column(String)
    total_tokens = Column(Integer, nullable=True)
    latency_s = Column(Float)
    ok = Column(Boolean, default=True)
