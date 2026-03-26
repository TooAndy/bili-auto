from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    JSON,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

from config import Config

Base = declarative_base()


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    mid = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    last_video_bvid = Column(String, nullable=True)
    last_dynamic_id = Column(String, nullable=True)
    last_check_time = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    bvid = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    mid = Column(String, nullable=False)
    pub_time = Column(Integer, nullable=True)
    has_subtitle = Column(Boolean, default=False)
    has_audio = Column(Boolean, default=False)
    subtitle_path = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    status = Column(String, default="pending")
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Dynamic(Base):
    __tablename__ = "dynamics"

    id = Column(Integer, primary_key=True)
    dynamic_id = Column(String, unique=True, nullable=False)
    mid = Column(String, nullable=False)
    type = Column(Integer, nullable=True)
    text = Column(Text, nullable=True)
    image_count = Column(Integer, default=0)
    images_path = Column(Text, nullable=True)
    image_urls = Column(Text, nullable=True)
    status = Column(String, default="pending")
    push_status = Column(String, default="pending")
    pub_time = Column(DateTime, nullable=True)
    pushed_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True)
    bvid = Column(String, unique=True, nullable=False)
    summary_json = Column(Text, nullable=False)
    push_status = Column(String, default="pending")
    pushed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    level = Column(String)
    message = Column(Text)
    context = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


engine = create_engine(Config.DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)


def get_db():
    session = SessionLocal()
    return session
