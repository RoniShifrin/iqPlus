# Backend Setup Instructions

## Prerequisites
- Python 3.11+
- MongoDB Atlas account (cluster: &lt;your-cluster&gt;.mongodb.net)
- pip/venv

## Step-by-Step Setup

### 1. Virtual Environment
```bash
cd BACK
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env and set your MONGODB_URL with the real password
```

### 4. Seed Database (create admin user)
```bash
python ../INFRA/scripts/seed_database.py
```

### 5. Run Backend
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Visit: http://localhost:8000/docs

## Docker Setup (Recommended)

```bash
cd INFRA
cp .env.example .env
# Set MONGODB_URL in .env
docker compose up --build
```

Services will start:
- Backend on 8000
- Frontend on 5173

## Troubleshooting

### MongoDB Connection Error
- Verify `MONGODB_URL` in `.env` has the correct password
- Check that your IP is whitelisted in MongoDB Atlas Network Access
- Ensure the cluster name is `&lt;your-cluster&gt;.mongodb.net`

### Firebase Auth Issues
- Ensure FIREBASE_PRIVATE_KEY has correct format
- Check Firebase project settings in console
- For development, set `ENVIRONMENT=development` to bypass auth
