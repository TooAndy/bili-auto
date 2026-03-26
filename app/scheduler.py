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
        fetcher = DynamicFetcher()
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
    logger.info("视频检测频率: 每10分钟")
    logger.info("动态检测频率: 每5分钟")
    logger.info("=" * 50)
    
    # 视频检测：每10分钟一次
    schedule.every(10).minutes.do(check_new_videos)
    
    # 动态检测：每5分钟一次（频率更高，因为动态更新快）
    schedule.every(5).minutes.do(check_new_dynamics)
    
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
