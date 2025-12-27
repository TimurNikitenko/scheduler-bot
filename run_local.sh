#!/bin/bash

# Script to run bot locally for debugging
# Usage: ./run_local.sh

set -e

echo "🚀 Starting bot locally for debugging..."
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with BOT_TOKEN, ADMIN_IDS, and DATABASE_URL"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

# Check if PostgreSQL is running locally
echo "🐘 Checking PostgreSQL connection..."
if docker ps | grep -q telegram_bot_postgres; then
    echo "✅ PostgreSQL container is running"
    DB_URL="postgresql://postgres:postgres@localhost:5432/telegram_bot"
elif pg_isready -h localhost -p 5432 -U postgres >/dev/null 2>&1; then
    echo "✅ PostgreSQL is running locally"
    DB_URL="postgresql://postgres:postgres@localhost:5432/telegram_bot"
else
    echo "⚠️  PostgreSQL not found. Starting with Docker Compose..."
    docker-compose up -d postgres
    echo "⏳ Waiting for PostgreSQL to be ready..."
    sleep 5
    DB_URL="postgresql://postgres:postgres@localhost:5432/telegram_bot"
fi

# Update .env if needed (for local run)
if ! grep -q "DATABASE_URL.*localhost" .env; then
    echo "📝 Updating DATABASE_URL in .env for local run..."
    sed -i.bak 's|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:postgres@localhost:5432/telegram_bot|' .env
fi

echo ""
echo "✅ Starting bot..."
echo "📋 Logs will be displayed below. Press Ctrl+C to stop."
echo ""

# Run the bot
python main.py

