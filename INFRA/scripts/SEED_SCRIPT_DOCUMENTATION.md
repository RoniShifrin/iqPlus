# Seed Script Documentation

## Overview

`seed_database.py` connects to MongoDB Atlas and creates the initial admin user.

**What it does:**
- Connects to MongoDB Atlas via Motor async client
- Initializes Beanie ODM with all document models
- Checks if admin user already exists
- Creates admin user document if not present

## Prerequisites

- Python 3.11+
- Dependencies installed: `pip install -r BACK/requirements.txt`
- `MONGODB_URL` environment variable set

## Usage

```bash
# Set MongoDB URL
export MONGODB_URL="mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority"

# Run the script
python INFRA/scripts/seed_database.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGODB_URL` | MongoDB Atlas connection string | `mongodb://localhost:27017` |
| `DB_NAME` | Database name | `iqplus_db` |

## Admin Credentials Created

```
Email:    admin@iqplus.com
Password: Admin123!
Role:     admin
```

## Safe to Run Multiple Times

The script checks for existing admin before inserting. Running it twice will not create duplicates.

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `ServerSelectionTimeoutError` | Cannot reach MongoDB | Check `MONGODB_URL` and Atlas IP whitelist |
| `Authentication failed` | Wrong password in URL | Verify Atlas credentials |
| `ModuleNotFoundError` | Missing packages | `pip install -r BACK/requirements.txt` |

## CI/CD Integration

```yaml
# GitHub Actions example
- name: Seed Database
  run: python INFRA/scripts/seed_database.py
  env:
    MONGODB_URL: ${{ secrets.MONGODB_URL }}
    DB_NAME: iqplus_db
```

---

**Last Updated:** March 4, 2026
