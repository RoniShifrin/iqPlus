# INFRA/scripts - Database & System Scripts

## Scripts

### `seed_database.py` (Main Script)

**Purpose:** Connect to MongoDB Atlas and create the default admin user

**Credentials Created:**
```
Email:    admin@iqplus.com
Password: Admin123!
Role:     Admin
```

**Usage:**
```bash
# Set your MongoDB URL first
export MONGODB_URL="mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority"

# From INFRA/scripts directory
python seed_database.py

# Or from Docker
docker compose exec backend python INFRA/scripts/seed_database.py
```

## Environment Variables

```env
MONGODB_URL=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
DB_NAME=iqplus_db
```

## What Gets Created

### MongoDB Collections (auto-created by Beanie)
- users
- courses
- enrollments
- grades
- attendance
- feedback
- learning_insights

### Admin User Document
```python
User(
    firebase_uid='admin@iqplus.com',
    email='admin@iqplus.com',
    first_name='Admin',
    last_name='User',
    role='admin',
    is_active=True
)
```

## Safe to Run Multiple Times

The script checks if `admin@iqplus.com` already exists before inserting.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection error | Check MONGODB_URL is set and Atlas IP whitelist includes your IP |
| ModuleNotFoundError | Run `pip install -r BACK/requirements.txt` |
| Authentication failed | Verify MongoDB Atlas credentials |

---

**Last Updated:** March 4, 2026
