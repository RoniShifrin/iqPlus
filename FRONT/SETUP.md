FRONTEND_INSTALLATION_REQUIREMENTS_FOR_SETUP.md

# Frontend Setup Instructions

## Prerequisites
- Node.js 18+
- npm 9+

## Step-by-Step Setup

### 1. Install Dependencies
```bash
cd FRONT
npm install
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit with your API URL and Firebase config
```

Default values:
```env
VITE_API_URL=http://localhost:8000
```

### 3. Development Server
```bash
npm run dev
```

Visit: http://localhost:5173

### 4. Production Build
```bash
npm run build
npm run preview
```

## Docker Setup

```bash
cd INFRA
docker compose up --build
```

Frontend will start on port 5173

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| VITE_API_URL | Backend API URL | http://localhost:8000 |
| VITE_FIREBASE_CONFIG | Firebase SDK config | `{...}` |

## Troubleshooting

### Port 5173 Already in Use
```bash
npm run dev -- --port 5174
```

### API Not Responding
- Check backend is running on port 8000
- Verify VITE_API_URL in .env
- Check browser console for CORS errors

### Build Errors
```bash
rm -rf node_modules
npm install
npm run build
```

## Features Available

✅ User authentication (login/signup)
✅ Role-based dashboards
✅ Course browsing and enrollment
✅ Progress tracking
✅ Learning insights
✅ Responsive design
✅ Real-time data updates
