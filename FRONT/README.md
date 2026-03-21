# IQ PLUS - Frontend

## Quick Start

```bash
# Install dependencies
npm install

# Development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Environment Variables
Create `.env` file:
```env
VITE_API_URL=http://localhost:8000
VITE_FIREBASE_CONFIG={"apiKey":"...","authDomain":"...","projectId":"..."}
```

## Features

- User authentication with Firebase
- Role-based access control (Student, Teacher, Admin)
- Course enrollment and management
- Progress tracking with AI insights
- Responsive design with TailwindCSS
- Real-time data with TanStack Query

## Pages

- `/login` - Authentication
- `/signup` - User registration
- `/` - Dashboard (role-based)
- `/courses` - Course listing and enrollment
- `/progress` - Student progress and insights

## Project Structure

```
src/
├── pages/          # Page components
├── components/     # Reusable components
├── services/       # API client
├── contexts/       # React Context (Auth)
├── hooks/          # Custom React hooks
├── App.tsx         # Router setup
└── main.tsx        # Entry point
```
