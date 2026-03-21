"""
MongoDB collection setup script for IQ PLUS
Beanie (ODM) handles collection creation automatically on app startup.
This script creates indexes explicitly for performance.
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../BACK'))

from app.models import ALL_DOCUMENTS

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "iqplus_db")


async def create_indexes():
    """Initialize Beanie and create all collection indexes"""
    print("\n" + "="*60)
    print("IQ PLUS MongoDB Collection Setup")
    print("="*60)

    client = AsyncIOMotorClient(MONGODB_URL)
    db = client[DB_NAME]

    print(f"\nConnecting to: {DB_NAME}")
    await init_beanie(database=db, document_models=ALL_DOCUMENTS)

    print("✅ Collections and indexes created:")
    for doc in ALL_DOCUMENTS:
        print(f"   • {doc.Settings.name}")

    # Additional compound indexes for query performance
    await db["enrollments"].create_index(
        [("student_id", 1), ("course_id", 1)], unique=True, name="unique_student_course"
    )
    await db["grades"].create_index(
        [("student_id", 1), ("course_id", 1), ("recorded_at", -1)], name="idx_grades_lookup"
    )
    await db["attendance"].create_index(
        [("student_id", 1), ("course_id", 1), ("date", -1)], name="idx_attendance_lookup"
    )
    await db["learning_insights"].create_index(
        [("student_id", 1), ("created_at", -1)], name="idx_insights_student"
    )

    print("\n✅ Compound indexes created")
    print("="*60 + "\n")
    client.close()


if __name__ == "__main__":
    asyncio.run(create_indexes())
