# CampusPulse — Quick Start Script (Windows PowerShell)
# Run: .\start.ps1

Write-Host "🎓 CampusPulse — Starting up..." -ForegroundColor Cyan

Set-Location backend

# Install Python dependencies
Write-Host "`n📦 Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Seed the database
Write-Host "`n🌱 Seeding database..." -ForegroundColor Yellow
python seed_db.py

# Launch FastAPI
Write-Host "`n🚀 Launching CampusPulse at http://localhost:8000" -ForegroundColor Green
Write-Host "   API Docs at http://localhost:8000/docs" -ForegroundColor Gray
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
