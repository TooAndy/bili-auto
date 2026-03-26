import time
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from app.utils.logger import get_logger
from app.models.database import get_db, Video, Dynamic
from app.modules.subtitle import get_subtitles
from app.modules.downloader import download_audio
from app.modules.whisper_ai import transcribe_audio
from app.modules.llm import summarize
from app.modules.push import push_content
from app.modules.dynamic import should_push_dynamic

logger = get_logger("queue_worker")


def process_single_video(bvid: str):
    db = get_db()
    video = db.query(Video).filter_by(bvid=bvid).first()
    if not video:
        logger.warning("视频不存在: %s", bvid)
        return

    try:
        logger.info("开始处理视频 %s", bvid)
        video.status = "processing"
        db.commit()

        subtitles = get_subtitles(bvid)
        video.has_subtitle = bool(subtitles)

        if not subtitles:
            audio_path = download_audio(bvid)
            subtitles = transcribe_audio(audio_path)
            video.has_audio = True
            video.audio_path = audio_path

        summary_data = summarize(subtitles, title=video.title, duration=0)
        video.summary_json = json.dumps(summary_data, ensure_ascii=False)

        push_content({
            "type": "video",
            "title": video.title,
            "summary": summary_data.get("summary", ""),
            "key_points": summary_data.get("key_points", []),
            "tags": summary_data.get("tags", []),
            "url": f"https://www.bilibili.com/video/{bvid}",
            "duration_minutes": summary_data.get("duration_minutes", 0),
            "timestamp": video.pub_time
        }, ["feishu", "telegram", "wechat"])

        video.status = "done"
        db.commit()
        logger.info("处理完成视频 %s", bvid)

    except Exception as e:
        logger.error("处理视频失败 %s: %s", bvid, e, exc_info=True)
        video.status = "failed"
        video.last_error = str(e)
        video.attempt_count += 1
        db.commit()


def process_single_dynamic(dynamic_id: str):
    db = get_db()
    dynamic = db.query(Dynamic).filter_by(dynamic_id=dynamic_id).first()
    if not dynamic:
        logger.warning("动态不存在: %s", dynamic_id)
        return

    try:
        logger.info("开始处理动态 %s", dynamic_id)
        dynamic.status = "processing"
        db.commit()

        image_paths = json.loads(dynamic.images_path or "[]")
        image_urls = json.loads(dynamic.image_urls or "[]")

        push_content({
            "type": "dynamic",
            "text": dynamic.text,
            "images": image_paths,
            "image_urls": image_urls,
            "pub_time": dynamic.pub_time,
            "url": f"https://www.bilibili.com/opus/{dynamic.dynamic_id}"
        }, ["feishu", "telegram", "wechat"])

        dynamic.status = "sent"
        dynamic.pushed_at = datetime.utcnow()
        db.commit()
        logger.info("处理完成动态 %s", dynamic_id)

    except Exception as e:
        logger.error("处理动态失败 %s: %s", dynamic_id, e, exc_info=True)
        dynamic.status = "failed"
        dynamic.last_error = str(e)
        dynamic.attempt_count += 1
        db.commit()


def start_queue_worker(max_workers: int = 3):
    logger.info("队列工作线程启动")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while True:
            db = get_db()
            pending_dynamics = db.query(Dynamic).filter_by(status="pending").limit(5).all()
            pending_videos = db.query(Video).filter_by(status="pending").limit(5).all()

            if not pending_dynamics and not pending_videos:
                time.sleep(10)
                continue

            for dyn in pending_dynamics:
                if not should_push_dynamic({"text": dyn.text}):
                    dyn.status = "failed"
                    dyn.last_error = "预过滤不符合"
                    db.commit()
                else:
                    executor.submit(process_single_dynamic, dyn.dynamic_id)

            for vid in pending_videos:
                executor.submit(process_single_video, vid.bvid)

            time.sleep(5)
