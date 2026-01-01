import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration"""
    # Project paths
    BASE_DIR = Path(__file__).resolve().parent
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Celery
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'America/Chicago'
    CELERY_ENABLE_UTC = True
    
    # AI Services
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    
    # Email
    SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
    FROM_EMAIL = os.getenv('FROM_EMAIL', 'noreply@yourdomain.com')
    FROM_NAME = os.getenv('FROM_NAME', 'Real Estate AI')
    
    # SMS
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    
    # MLS API
    MLS_API_KEY = os.getenv('MLS_API_KEY')
    MLS_API_SECRET = os.getenv('MLS_API_SECRET')
    MLS_API_URL = os.getenv('MLS_API_URL', 'https://api.simplyrets.com')
    
    # CRM API
    CRM_API_KEY = os.getenv('CRM_API_KEY')
    CRM_API_URL = os.getenv('CRM_API_URL')
    
    # Application
    APP_DOMAIN = os.getenv('APP_DOMAIN', 'http://localhost:5000')
    MATCH_SCORE_THRESHOLD = int(os.getenv('MATCH_SCORE_THRESHOLD', 60))
    EMAIL_OPEN_TRACKING = os.getenv('EMAIL_OPEN_TRACKING', 'true').lower() == 'true'


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
