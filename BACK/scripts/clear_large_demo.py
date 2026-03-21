#!/usr/bin/env python3
"""
IQ PLUS — Large Demo Data Cleaner
===================================
Removes every document created by seed_large_demo.py.

Uses the _large_demo_registry MongoDB collection as the source of truth —
only documents explicitly tracked during seeding are deleted.
Real data, and small-demo data, are completely untouched.

Usage:
    python scripts/clear_large_demo.py
"""

import asyncio
import os
import sys
from pathlib import Path

BACK_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_DIR))

from dotenv import load_dotenv
load_dotenv(dotenv_path=BACK_DIR.parent / ".env")

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URL         = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME             = os.getenv("DB_NAME",     "iqplus_db")
REGISTRY_COLLECTION = "_large_demo_registry"


async def clear() -> None:
    print(f"\n  Connecting to {DB_NAME}...")
    client = AsyncIOMotorClient(MONGODB_URL)
    db     = client[DB_NAME]

    entries = await db[REGISTRY_COLLECTION].find({}).to_list(length=None)
    if not entries:
        print("  No large demo data found. Nothing to delete.\n")
        return

    merged: dict[str, set] = {}
    for entry in entries:
        for coll, str_ids in entry.get("collections", {}).items():
            merged.setdefault(coll, set()).update(str_ids)

    print(f"  Found {len(entries)} registry entry/entries. Deleting...\n")

    total = 0
    for coll_name, str_ids in sorted(merged.items()):
        if not str_ids:
            continue
        oids   = [ObjectId(s) for s in str_ids]
        result = await db[coll_name].delete_many({"_id": {"$in": oids}})
        n      = result.deleted_count
        total += n
        if n:
            print(f"  Deleted {n:>4}  from  {coll_name}")

    await db[REGISTRY_COLLECTION].delete_many({})

    print(f"\n  Total removed: {total} documents.")
    print("  Large demo registry cleared.")
    print("  Real data and small demo data are untouched.\n")


if __name__ == "__main__":
    asyncio.run(clear())
