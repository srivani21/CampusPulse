#!/usr/bin/env bash
# CampusPulse — Quick Start Script (Linux/macOS/WSL)
set -e

echo "🎓 CampusPulse — Starting up..."

cd backend

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

echo "🌱 Seeding database..."
python seed_db.py

echo "🚀 Launching CampusPulse at http://localhost:8000"
echo "   API Docs at http://localhost:8000/docs"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
