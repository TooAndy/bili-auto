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
    """处理单个视频的完整流程"""
    db = get_db()
    video = db.query(Video).filter_by(bvid=bvid).first()
    if not video:
        logger.warning("视频不存在: %s", bvid)
        return

    try:
        logger.info("开始处理视频 %s | 标题: %s", bvid, video.title)
        video.status = "processing"
        db.commit()

        # 第1步：获取字幕
        logger.debug("[字幕] 尝试从B站获取...")
        subtitles = get_subtitles(bvid)
        video.has_subtitle = bool(subtitles)
        
        if subtitles:
            logger.debug("[字幕] 获取成功，长度: %d", len(subtitles))
        else:
            # 第2步：字幕失败，用Whisper转写
            logger.debug("[Whisper] 开始下载音频并识别...")
            try:
                audio_path = download_audio(bvid)
                subtitles = transcribe_audio(audio_path)
                video.has_audio = True
                video.audio_path = audio_path
                logger.debug("[Whisper] 识别完成，长度: %d", len(subtitles))
            except Exception as e:
                logger.error("[Whisper] 音频处理失败: %s", e)
                subtitles = ""
        
        # 第3步：LLM总结
        if subtitles:
            logger.debug("[LLM] 开始总结...")
            summary_data = summarize(
                text=subtitles,
                title=video.title,
                duration=0
            )
            video.summary_json = json.dumps(summary_data, ensure_ascii=False)
            logger.debug("[LLM] 总结完成")
        else:
            logger.warning("[LLM] 无字幕和音频，跳过总结")
            summary_data = {
                "summary": f"无法获取字幕或音频: {video.title}",
                "key_points": [],
                "tags": [],
                "insights": "",
                "duration_minutes": 0
            }
            video.summary_json = json.dumps(summary_data, ensure_ascii=False)

        # 第4步：推送
        logger.debug("[推送] 开始推送...")
        push_content({
            "type": "video",
            "title": video.title,
            "summary": summary_data.get("summary", ""),
            "key_points": summary_data.get("key_points", []),
            "tags": summary_data.get("tags", []),
            "insights": summary_data.get("insights", ""),
            "url": f"https://www.bilibili.com/video/{bvid}",
            "duration_minutes": summary_data.get("duration_minutes", 0),
            "timestamp": video.pub_time
        }, [])  # 空数组，因为先不推送

        video.status = "done"
        db.commit()
        logger.info("✅ 处理完成: %s", bvid)

    except Exception as e:
        logger.error("❌ 处理失败 %s: %s", bvid, e, exc_info=True)
        video.status = "failed"
        video.last_error = str(e)[:200]
        video.attempt_count += 1
        
        if video.attempt_count >= 3:
            logger.error("放弃重试: %s (已尝试3次)", bvid)
        else:
            logger.info("将重新入队: %s (第%d次)", bvid, video.attempt_count)
        
        db.commit()


def process_single_dynamic(dynamic_id: str):
    """处理单个动态的完整流程"""
    db = get_db()
    dynamic = db.query(Dynamic).filter_by(dynamic_id=dynamic_id).first()
    if not dynamic:
        logger.warning("动态不存在: %s", dynamic_id)
        return

    try:
        logger.info("开始处理动态 %s | 内容: %s...", dynamic_id, dynamic.text[:50])
        dynamic.status = "processing"
        db.commit()

        # 预过滤
        if not should_push_dynamic({"text": dynamic.text}):
            logger.info("动态不符合推送条件: %s", dynamic_id)
            dynamic.status = "filtered"
            dynamic.last_error = "预过滤过滤不符合"
            db.commit()
            return

        # 准备推送数据
        image_paths = json.loads(dynamic.images_path or "[]") if dynamic.images_path else []
        image_urls = json.loads(dynamic.image_urls or "[]") if dynamic.image_urls else []

        logger.debug("[动态数据] 文本: %d字, 图片: %d张", len(dynamic.text or ""), len(image_paths))

        # 推送（当前为占位符）
        push_content({
            "type": "dynamic",
            "text": dynamic.text,
            "images": image_paths,
            "image_urls": image_urls,
            "pub_time": str(dynamic.pub_time) if dynamic.pub_time else "",
            "url": f"https://www.bilibili.com/opus/{dynamic.dynamic_id}"
        }, [])  # 空数组，因为先不推送

        dynamic.status = "sent"
        dynamic.pushed_at = datetime.utcnow()
        db.commit()
        logger.info("✅ 动态推送完成: %s", dynamic_id)

    except Exception as e:
        logger.error("❌ 动态处理失败 %s: %s", dynamic_id, e, exc_info=True)
        dynamic.status = "failed"
        dynamic.last_error = str(e)[:200]
        dynamic.attempt_count += 1
        
        if dynamic.attempt_count >= 3:
            logger.error("放弃重试: %s (已尝试3次)", dynamic_id)
        else:
            logger.info("将重新入队: %s (第%d次)", dynamic_id, dynamic.attempt_count)
        
        db.commit()


def start_queue_worker(max_workers: int = 3):
    """启动队列处理worker，持续处理待处理任务"""
    logger.info("=" * 50)
    logger.info("队列处理线程启动，max_workers=%d", max_workers)
    logger.info("=" * 50)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop_count = 0
        while True:
            loop_count += 1
            
            try:
                db = get_db()
                
                # 优先处理动态（处理快）
                pending_dynamics = db.query(Dynamic).filter_by(
                    status="pending"
                ).order_by(Dynamic.created_at).limit(5).all()
                
                # 然后处理视频
                pending_videos = db.query(Video).filter_by(
                    status="pending"
                ).order_by(Video.created_at).limit(5).all()

                # 处理已失败但还能重试的任务
                retry_videos = db.query(Video).filter_by(
                    status="failed"
                ).filter(Video.attempt_count < 3).limit(2).all()
                
                retry_dynamics = db.query(Dynamic).filter_by(
                    status="failed"
                ).filter(Dynamic.attempt_count < 3).limit(2).all()

                total_pending = len(pending_dynamics) + len(pending_videos)
                total_retry = len(retry_videos) + len(retry_dynamics)

                if loop_count % 6 == 0:  # 每30秒（6个5秒循环）打印一次统计
                    logger.info("[定期统计] 待处理动态: %d, 待处理视频: %d, 重试队列: %d",
                                len(pending_dynamics), len(pending_videos), total_retry)

                if not pending_dynamics and not pending_videos and not retry_dynamics and not retry_videos:
                    logger.debug("暂无待处理任务，休眠...")
                    time.sleep(30)
                    continue

                # 提交动态任务
                for dyn in pending_dynamics:
                    executor.submit(process_single_dynamic, dyn.dynamic_id)
                
                # 提交已失败但可重试的动态
                for dyn in retry_dynamics:
                    logger.info("重新处理失败动态: %s (第%d次重试)", dyn.dynamic_id, dyn.attempt_count + 1)
                    executor.submit(process_single_dynamic, dyn.dynamic_id)

                # 提交视频任务
                for vid in pending_videos:
                    executor.submit(process_single_video, vid.bvid)
                
                # 提交已失败但可重试的视频
                for vid in retry_videos:
                    logger.info("重新处理失败视频: %s (第%d次重试)", vid.bvid, vid.attempt_count + 1)
                    executor.submit(process_single_video, vid.bvid)

                time.sleep(5)

            except Exception as e:
                logger.error("队列处理循环异常: %s", e, exc_info=True)
                time.sleep(10)  # 出错时休眠较长时间
