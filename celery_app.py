from celery import Celery
from celery.schedules import crontab
from config.config import Config

# Initialize Celery
celery = Celery('real_estate_ai')

# Configure Celery
celery.conf.update(
    broker_url=Config.CELERY_BROKER_URL,
    result_backend=Config.CELERY_RESULT_BACKEND,
    task_serializer=Config.CELERY_TASK_SERIALIZER,
    accept_content=Config.CELERY_ACCEPT_CONTENT,
    result_serializer=Config.CELERY_RESULT_SERIALIZER,
    timezone=Config.CELERY_TIMEZONE,
    enable_utc=Config.CELERY_ENABLE_UTC,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)

# Beat schedule for periodic tasks
celery.conf.beat_schedule = {
    # Sync MLS listings every hour
    'sync-mls-listings': {
        'task': 'app.tasks.mls_tasks.sync_mls_listings',
        'schedule': crontab(minute=0),  # Every hour on the hour
    },
    
    # Run daily nurture at 9 AM
    'daily-nurture': {
        'task': 'app.tasks.nurture_tasks.run_daily_nurture',
        'schedule': crontab(hour=9, minute=0),  # 9 AM every day
    },
    
    # Cleanup old data weekly
    'weekly-cleanup': {
        'task': 'app.tasks.maintenance_tasks.cleanup_old_data',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),  # Sunday 2 AM
    },
}
