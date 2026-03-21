"""Admin Demo Data Controls.

Provides read-only status and safe cleanup of demo datasets via the API.
Seeding must be run via CLI (seed scripts spawn long async operations that
are not suitable for a synchronous HTTP request context).

Endpoints:
    GET  /api/admin/demo/status  — registry summary for both demo datasets
    POST /api/admin/demo/clear   — delete one or both demo datasets
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os

from app.models import User, RoleEnum
from app.security import get_current_user

router = APIRouter(prefix="/api/admin/demo", tags=["admin-demo"])

_SMALL_REG = "_demo_registry"
_LARGE_REG = "_large_demo_registry"

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DB_NAME     = os.getenv("DB_NAME",     "iqplus_db")


def _require_admin(current_user: User) -> None:
    if current_user.role != RoleEnum.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


async def _get_db():
    client = AsyncIOMotorClient(MONGODB_URL)
    return client[DB_NAME]


async def _registry_summary(db, collection: str) -> dict:
    entries = await db[collection].find({}).to_list(length=None)
    if not entries:
        return {"seeded": False, "entries": 0, "collections": {}, "total_documents": 0}
    merged: dict[str, set] = {}
    for e in entries:
        for coll, ids in e.get("collections", {}).items():
            merged.setdefault(coll, set()).update(ids)
    totals = {coll: len(ids) for coll, ids in merged.items()}
    return {
        "seeded":          True,
        "entries":         len(entries),
        "collections":     totals,
        "total_documents": sum(totals.values()),
    }


async def _clear_registry(db, collection: str) -> int:
    entries = await db[collection].find({}).to_list(length=None)
    if not entries:
        return 0
    merged: dict[str, set] = {}
    for e in entries:
        for coll, ids in e.get("collections", {}).items():
            merged.setdefault(coll, set()).update(ids)
    total = 0
    for coll_name, str_ids in merged.items():
        if not str_ids:
            continue
        oids   = [ObjectId(s) for s in str_ids]
        result = await db[coll_name].delete_many({"_id": {"$in": oids}})
        total += result.deleted_count
    await db[collection].delete_many({})
    return total


@router.get("/status")
async def demo_status(current_user: User = Depends(get_current_user)):
    """Return registry status for both demo datasets."""
    _require_admin(current_user)
    db = await _get_db()
    small = await _registry_summary(db, _SMALL_REG)
    large = await _registry_summary(db, _LARGE_REG)
    return {
        "small_demo": {"domain": "@demo.iqplus.dev",  **small},
        "large_demo": {"domain": "@large.iqplus.dev", **large},
        "note": "To seed demo data run: python scripts/seed_demo_data.py  OR  python scripts/seed_large_demo.py",
    }


@router.post("/clear")
async def demo_clear(
    dataset: str = Query(default="all", description="Which dataset to clear: small | large | all"),
    current_user: User = Depends(get_current_user),
):
    """Delete demo-tagged data tracked in the registry. Real data is never touched."""
    _require_admin(current_user)

    if dataset not in ("small", "large", "all"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="dataset must be one of: small | large | all",
        )

    db = await _get_db()
    removed: dict[str, int] = {}

    if dataset in ("small", "all"):
        n = await _clear_registry(db, _SMALL_REG)
        removed["small_demo"] = n

    if dataset in ("large", "all"):
        n = await _clear_registry(db, _LARGE_REG)
        removed["large_demo"] = n

    total = sum(removed.values())
    return {
        "cleared":          removed,
        "total_removed":    total,
        "real_data_safe":   True,
        "message":          f"{total} demo documents removed. To reseed run: python scripts/reseed_demo.py",
    }
