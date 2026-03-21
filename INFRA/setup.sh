#!/bin/bash

set -e

echo "IQ PLUS Setup Script"
echo "===================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your Firebase and SMTP credentials"
fi

echo "Building and starting services..."
docker compose up --build

echo "✅ IQ PLUS is running!"
echo "   Frontend: http://localhost:5173"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
