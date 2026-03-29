"""
系统初始化模块
处理程序启动和关闭时的清理工作
"""
from app.utils.logger import get_logger
from app.models.database import get_db, Video, Dynamic

logger = get_logger("init")


def reset_stuck_tasks():
    """
    重置卡住的任务

    将所有状态为 'processing' 的任务重置为 'pending'，
    这样程序重启后可以重新处理这些任务。
    """
    db = get_db()
    try:
        # 重置视频任务
        stuck_videos = db.query(Video).filter_by(status="processing").all()
        if stuck_videos:
            for video in stuck_videos:
                logger.warning("重置卡住的视频任务: %s | %s", video.bvid, video.title)
                video.status = "pending"
                video.attempt_count += 1
            db.commit()
            logger.info("已重置 %d 个卡住的视频任务", len(stuck_videos))

        # 重置动态任务
        stuck_dynamics = db.query(Dynamic).filter_by(status="processing").all()
        if stuck_dynamics:
            for dynamic in stuck_dynamics:
                logger.warning("重置卡住的动态任务: %s", dynamic.dynamic_id)
                dynamic.status = "pending"
                dynamic.attempt_count += 1
            db.commit()
            logger.info("已重置 %d 个卡住的动态任务", len(stuck_dynamics))

    except Exception as e:
        logger.error("重置卡住任务时出错: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()


def graceful_shutdown():
    """
    优雅关闭

    尝试将当前正在处理的任务状态进行适当处理。
    注意：由于线程可能已经在处理中，这里只能做最好的尝试。
    """
    logger.info("执行优雅关闭...")
    # 注意：由于多线程环境，这里很难精确知道哪些任务正在处理
    # 主要依靠 reset_stuck_tasks() 在下次启动时重置
    logger.info("优雅关闭完成，下次启动时将重置卡住的任务")
