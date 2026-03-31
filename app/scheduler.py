import schedule
import time
import json
import asyncio
from datetime import datetime
from app.utils.logger import get_logger
from app.models.database import get_db, Subscription, Video, Dynamic
from app.modules.bilibili import fetch_channel_videos
from app.modules.dynamic import DynamicFetcher
from app.modules.bilibili_auth import get_auth_manager
from config import Config

logger = get_logger("scheduler")


def check_and_refresh_cookie():
    """
    检查并刷新 Cookie（同步封装）

    Returns:
        如果刷新了返回新的 Cookie，否则返回 None
    """
    if not Config.BILIBILI_COOKIE:
        logger.warning("未配置 BILIBILI_COOKIE，跳过 Cookie 刷新检查")
        return None

    auth = get_auth_manager()
    refresh_token = auth.get_refresh_token()

    if not refresh_token:
        logger.info("未配置 refresh_token，跳过 Cookie 自动刷新")
        logger.info("如需启用自动刷新，请运行: python scripts/set_refresh_token.py")
        return None

    logger.info("开始检查 Cookie 是否需要刷新...")

    # 创建事件循环来运行异步代码
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        new_cookie, refreshed = loop.run_until_complete(
            auth.auto_refresh_if_needed(Config.BILIBILI_COOKIE)
        )
        if refreshed:
            logger.info("Cookie 已刷新！")
            # 更新 Config 中的 Cookie（当前进程）
            Config.BILIBILI_COOKIE = new_cookie
            return new_cookie
        else:
            logger.info("Cookie 无需刷新")
            return None
    except Exception as e:
        logger.error(f"Cookie 刷新过程出错: {e}", exc_info=True)
        return None


def check_new_videos():
    """定时检测所有UP主的新视频"""
    logger.info("[检测] 开始检查新视频...")
    
    try:
        db = get_db()
        subscriptions = db.query(Subscription).filter_by(is_active=True).all()
        
        if not subscriptions:
            logger.warning("[检测] 未配置任何UP主订阅")
            return
        
        new_count = 0
        error_count = 0
        
        for sub in subscriptions:
            try:
                videos = fetch_channel_videos(sub.mid, limit=10)
                logger.debug("[检测] 用户 %s(%s) 获得 %d 个视频", 
                            sub.name, sub.mid, len(videos))
                
                for v in videos:
                    # 检查是否已存在
                    existing = db.query(Video).filter_by(bvid=v["bvid"]).first()
                    if existing:
                        logger.debug("[检测] 视频已存在: %s", v["bvid"])
                        continue
                    
                    # 新视频，添加到数据库
                    new_video = Video(
                        bvid=v["bvid"],
                        title=v["title"],
                        mid=sub.mid,
                        pub_time=v.get("pubdate", 0),
                        status="pending"
                    )
                    db.add(new_video)
                    new_count += 1
                    logger.info("[新视频] %s | %s (%s)", 
                               sub.name, v["title"], v["bvid"])
                
                sub.last_check_time = datetime.utcnow()
                
            except Exception as e:
                error_count += 1
                logger.error("[检测] 检查用户 %s(%s) 失败: %s", 
                           sub.mid, sub.name, e, exc_info=True)
        
        db.commit()
        logger.info("[检测完成] 发现 %d 个新视频，%d 个错误", new_count, error_count)
        
    except Exception as e:
        logger.error("[检测] 异常: %s", e, exc_info=True)


def check_new_dynamics():
    """定时检测所有UP主的新动态"""
    logger.info("[检测] 开始检查新动态...")

    try:
        db = get_db()
        # 使用上下文管理器确保 Session 正确关闭
        with DynamicFetcher() as fetcher:
            subscriptions = db.query(Subscription).filter_by(is_active=True).all()

            if not subscriptions:
                logger.warning("[检测] 未配置任何UP主订阅")
                return

            new_count = 0
            error_count = 0

            for sub in subscriptions:
                try:
                    dynamics = fetcher.fetch_dynamic(sub.mid)
                    logger.debug("[检测] 用户 %s(%s) 获得 %d 个动态",
                                sub.name, sub.mid, len(dynamics))

                    for dyn in dynamics:
                        # 检查是否已存在
                        existing = db.query(Dynamic).filter_by(
                            dynamic_id=dyn["dynamic_id"]
                        ).first()
                        if existing:
                            logger.debug("[检测] 动态已存在: %s", dyn["dynamic_id"])
                            continue

                        # 下载图片
                        dyn = fetcher.download_images(dyn)

                        # 新动态，添加到数据库
                        new_dynamic = Dynamic(
                            dynamic_id=dyn["dynamic_id"],
                            mid=sub.mid,
                            type=dyn.get("type", 0),
                            text=dyn.get("text", ""),
                            image_count=len(dyn.get("images", [])),
                            images_path=json.dumps(dyn.get("images", []), ensure_ascii=False),
                            image_urls=json.dumps(dyn.get("image_urls", []), ensure_ascii=False),
                            pub_time=dyn.get("pub_time"),
                            status="pending"
                        )
                        db.add(new_dynamic)
                        new_count += 1
                        text_preview = (dyn.get("text", "") or "")[:60]
                        logger.info("[新动态] %s | %s...", sub.name, text_preview)

                    sub.last_check_time = datetime.utcnow()

                except Exception as e:
                    error_count += 1
                    logger.error("[检测] 检查用户 %s(%s) 动态失败: %s",
                               sub.mid, sub.name, e, exc_info=True)

            db.commit()
            logger.info("[检测完成] 发现 %d 个新动态，%d 个错误", new_count, error_count)

    except Exception as e:
        logger.error("[检测] 异常: %s", e, exc_info=True)


def start_scheduler():
    """启动定时任务调度"""
    logger.info("=" * 50)
    logger.info("定时任务调度启动")

    video_interval = Config.VIDEO_CHECK_INTERVAL
    dynamic_interval = Config.DYNAMIC_CHECK_INTERVAL

    # 视频检测
    if video_interval > 0:
        logger.info("视频检测频率: 每%d分钟", video_interval)
        schedule.every(video_interval).minutes.do(check_new_videos)
    else:
        logger.info("视频检测: 已禁用 (VIDEO_CHECK_INTERVAL=%d)", video_interval)

    # 动态检测
    if dynamic_interval > 0:
        logger.info("动态检测频率: 每%d分钟", dynamic_interval)
        schedule.every(dynamic_interval).minutes.do(check_new_dynamics)
    else:
        logger.info("动态检测: 已禁用 (DYNAMIC_CHECK_INTERVAL=%d)", dynamic_interval)

    logger.info("=" * 50)
    
    loop_count = 0
    while True:
        try:
            loop_count += 1
            schedule.run_pending()
            
            # 每分钟打印一次心跳
            if loop_count % 6 == 0:
                logger.debug("[调度] 心跳正常，已运行 %d 分钟", loop_count // 6 * 10)
            
            time.sleep(10)  # 每10秒检查一次是否有任务需要执行
            
        except Exception as e:
            logger.error("[调度] 异常: %s", e, exc_info=True)
            time.sleep(30)
