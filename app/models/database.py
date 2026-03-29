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
    """UP主订阅表"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    mid = Column(String, unique=True, nullable=False)  # UP主UID
    name = Column(String, nullable=False)  # UP主名字
    last_video_bvid = Column(String, nullable=True)  # 最后检测的视频BVID
    last_dynamic_id = Column(String, nullable=True)  # 最后检测的动态ID
    last_check_time = Column(DateTime, nullable=True)  # 最后检测时间
    is_active = Column(Boolean, default=True)  # 是否激活
    notes = Column(Text, nullable=True)  # 备注
    created_at = Column(DateTime, default=datetime.utcnow)


class Video(Base):
    """视频表"""
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    bvid = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)
    mid = Column(String, nullable=False)
    pub_time = Column(Integer, nullable=True)  # 发布时间戳
    has_subtitle = Column(Boolean, default=False)  # 是否有字幕
    has_video = Column(Boolean, default=False)  # 是否成功下载视频
    has_audio = Column(Boolean, default=False)  # 是否成功下载音频
    subtitle_path = Column(String, nullable=True)  # 字幕文件路径
    video_path = Column(String, nullable=True)  # 视频文件路径
    audio_path = Column(String, nullable=True)  # 音频文件路径
    status = Column(String, default="pending")  # pending|processing|done|failed
    attempt_count = Column(Integer, default=0)  # 处理尝试次数
    last_error = Column(Text, nullable=True)  # 最后错误信息
    summary_json = Column(Text, nullable=True)  # 总结结果JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Dynamic(Base):
    """动态表"""
    __tablename__ = "dynamics"

    id = Column(Integer, primary_key=True)
    dynamic_id = Column(String, unique=True, nullable=False)
    mid = Column(String, nullable=False)
    type = Column(Integer, nullable=True)  # 256=图文, 2=视频等
    text = Column(Text, nullable=True)  # 动态文本内容
    image_count = Column(Integer, default=0)  # 图片数量
    images_path = Column(Text, nullable=True)  # 本地图片路径 JSON
    image_urls = Column(Text, nullable=True)  # 原始图片URLs JSON
    status = Column(String, default="pending")  # pending|processing|sent|filtered|failed
    push_status = Column(String, default="pending")  # 推送状态
    pub_time = Column(DateTime, nullable=True)  # 发布时间
    pushed_at = Column(DateTime, nullable=True)  # 推送时间
    attempt_count = Column(Integer, default=0)  # 处理尝试次数
    last_error = Column(Text, nullable=True)  # 最后错误信息
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Summary(Base):
    """总结结果表（不再直接使用，改为存在Video中）"""
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True)
    bvid = Column(String, unique=True, nullable=False)
    summary_json = Column(Text, nullable=False)
    push_status = Column(String, default="pending")
    pushed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Log(Base):
    """日志表（可选，用于监控）"""
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    level = Column(String)  # INFO|WARN|ERROR
    message = Column(Text)
    context = Column(Text)  # JSON格式的额外信息
    created_at = Column(DateTime, default=datetime.utcnow)


engine = create_engine(
    Config.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in Config.DATABASE_URL else {}
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(engine)
    print("✓ 数据库初始化完成")


def get_db():
    """获取数据库连接"""
    session = SessionLocal()
    return session
