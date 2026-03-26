import schedule
import time
import json
from datetime import datetime
from app.utils.logger import get_logger
from app.models.database import get_db, Subscription, Video, Dynamic
from app.modules.bilibili import fetch_channel_videos
from app.modules.dynamic import DynamicFetcher

logger = get_logger("scheduler")


def check_new_videos():
    logger.info("[检测] 开始检查新视频...")
    db = get_db()
    subs = db.query(Subscription).filter_by(is_active=True).all()

    for sub in subs:
        try:
            videos = fetch_channel_videos(sub.mid, limit=10)
            for v in videos:
                exists = db.query(Video).filter_by(bvid=v["bvid"]).first()
                if exists:
                    continue
                new_video = Video(
                    bvid=v["bvid"],
                    title=v["title"],
                    mid=sub.mid,
                    pub_time=v.get("pubdate"),
                    status="pending"
                )
                db.add(new_video)
                logger.info("新增视频任务: %s", v["bvid"])
            sub.last_video_bvid = videos[0]["bvid"] if videos else sub.last_video_bvid
            sub.last_check_time = datetime.utcnow()
            db.commit()
        except Exception as e:
            logger.error("检查新视频异常: %s", e, exc_info=True)


def check_new_dynamics():
    logger.info("[检测] 开始检查新动态...")
    db = get_db()
    subs = db.query(Subscription).filter_by(is_active=True).all()
    fetcher = DynamicFetcher()

    for sub in subs:
        try:
            dynamics = fetcher.fetch_dynamic(sub.mid)
            for dyn in dynamics:
                exists = db.query(Dynamic).filter_by(dynamic_id=dyn["dynamic_id"]).first()
                if exists:
                    continue
                if not fetcher.should_push_dynamic(dyn):
                    continue
                dyn = fetcher.download_images(dyn)
                new_dyn = Dynamic(
                    dynamic_id=dyn["dynamic_id"],
                    mid=sub.mid,
                    type=dyn["type"],
                    text=dyn["text"],
                    image_count=len(dyn.get("images", [])),
                    images_path=json.dumps(dyn.get("images", []), ensure_ascii=False),
                    image_urls=json.dumps(dyn.get("image_urls", []), ensure_ascii=False),
                    status="pending",
                    pub_time=dyn.get("pub_time")
                )
                db.add(new_dyn)
                logger.info("新增动态任务: %s", dyn["dynamic_id"])

            sub.last_dynamic_id = dynamics[0]["dynamic_id"] if dynamics else sub.last_dynamic_id
            sub.last_check_time = datetime.utcnow()
            db.commit()

        except Exception as e:
            logger.error("检查动态异常: %s", e, exc_info=True)


def start_scheduler():
    schedule.every(10).minutes.do(check_new_videos)
    schedule.every(5).minutes.do(check_new_dynamics)
    logger.info("定时任务已启动")

    while True:
        schedule.run_pending()
        time.sleep(30)
