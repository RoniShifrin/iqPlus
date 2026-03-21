"""MongoDB connection using Motor async client"""
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "iqplus_db")

motor_client: AsyncIOMotorClient = None


def get_motor_client() -> AsyncIOMotorClient:
    return motor_client


def get_database():
    return motor_client[DB_NAME]
