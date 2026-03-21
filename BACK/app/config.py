"""Production-ready configuration"""
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MongoDB
    MONGODB_URL: str = os.getenv('MONGODB_URL', 'mongodb://localhost:27017')
    DB_NAME: str = os.getenv('DB_NAME', 'iqplus_db')
    
    # Environment
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'production')
    DEBUG: bool = ENVIRONMENT == 'development'
    
    # Firebase
    FIREBASE_PROJECT_ID: str = os.getenv('FIREBASE_PROJECT_ID', '')
    FIREBASE_PRIVATE_KEY: str = os.getenv('FIREBASE_PRIVATE_KEY', '')
    FIREBASE_CLIENT_EMAIL: str = os.getenv('FIREBASE_CLIENT_EMAIL', '')
    
    # SMTP
    SMTP_HOST: str = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT: int = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER: str = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD: str = os.getenv('SMTP_PASSWORD', '')
    
    # API
    API_TITLE: str = 'IQ PLUS API'
    API_VERSION: str = '1.0.0'
    
    class Config:
        env_file = '.env'

settings = Settings()
