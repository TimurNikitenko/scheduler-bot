#!/bin/bash

# Deploy script for Telegram Bot to Selectel VDS
# Usage: ./deploy.sh user@host

set -e

if [ -z "$1" ]; then
    echo "Usage: ./deploy.sh user@host"
    echo "Example: ./deploy.sh root@123.45.67.89"
    exit 1
fi

REMOTE_HOST="$1"
REMOTE_DIR="/opt/telegram-bot"
LOCAL_DIR="$(pwd)"

# Detect SSH key
SSH_KEY=""
if [ -f ~/.ssh/selectel_key ]; then
    SSH_KEY="-i ~/.ssh/selectel_key"
    echo "🔑 Using SSH key: ~/.ssh/selectel_key"
fi

echo "🚀 Starting deployment to $REMOTE_HOST..."

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create .env file with BOT_TOKEN, ADMIN_IDS, and DATABASE_URL"
    exit 1
fi

# Create remote directory
echo "📁 Creating remote directory..."
ssh $SSH_KEY "$REMOTE_HOST" "mkdir -p $REMOTE_DIR"

# Copy files (excluding .env, .git, venv, etc.)
echo "📦 Copying files..."
if [ -n "$SSH_KEY" ]; then
    rsync -avz --progress -e "ssh $SSH_KEY" \
        --exclude '.git' \
        --exclude '.venv' \
        --exclude 'venv' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude 'postgres_data' \
        --exclude '.pgdata' \
        --exclude '*.log' \
        "$LOCAL_DIR/" "$REMOTE_HOST:$REMOTE_DIR/"
else
    rsync -avz --progress \
        --exclude '.git' \
        --exclude '.venv' \
        --exclude 'venv' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude '.env' \
        --exclude 'postgres_data' \
        --exclude '.pgdata' \
        --exclude '*.log' \
        "$LOCAL_DIR/" "$REMOTE_HOST:$REMOTE_DIR/"
fi

# Copy .env file to server (required)
echo ""
echo "📋 Copying .env file to server..."
if [ -f ".env" ]; then
    scp $SSH_KEY .env "$REMOTE_HOST:$REMOTE_DIR/.env"
    echo "✅ .env file copied"
else
    echo "⚠️  WARNING: .env file not found locally!"
    echo "   You'll need to create it on the server manually."
    echo "   Create file at: $REMOTE_DIR/.env"
    echo "   With content:"
    echo "     BOT_TOKEN=your_bot_token"
    echo "     ADMIN_IDS=your_telegram_id"
    echo "     DATABASE_URL=postgresql://postgres:postgres@postgres:5432/telegram_bot"
fi

# Install Docker and Docker Compose if not installed
echo "🐳 Checking Docker installation..."
ssh $SSH_KEY "$REMOTE_HOST" "command -v docker >/dev/null 2>&1 || {
    echo 'Installing Docker...'
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    systemctl enable docker
    systemctl start docker
}"

ssh $SSH_KEY "$REMOTE_HOST" "command -v docker-compose >/dev/null 2>&1 || {
    echo 'Installing Docker Compose...'
    curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-\$(uname -s)-\$(uname -m)\" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
}"

# Update docker-compose.yaml for production (use postgres hostname)
echo "🔧 Updating docker-compose.yaml for production..."
ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && sed -i 's|@localhost:5432|@postgres:5432|g' docker-compose.yaml || true"

# Build and start services
echo "🏗️  Building and starting services..."
ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose down || true"
ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose build"
ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose up -d"

# Show status
echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Checking service status..."
ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose ps"

echo ""
echo "📝 Useful commands:"
if [ -n "$SSH_KEY" ]; then
    echo "  View logs: ssh $SSH_KEY $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose logs -f bot'"
    echo "  Stop bot: ssh $SSH_KEY $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose stop bot'"
    echo "  Restart bot: ssh $SSH_KEY $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose restart bot'"
    echo "  View all logs: ssh $SSH_KEY $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose logs -f'"
else
    echo "  View logs: ssh $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose logs -f bot'"
    echo "  Stop bot: ssh $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose stop bot'"
    echo "  Restart bot: ssh $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose restart bot'"
    echo "  View all logs: ssh $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose logs -f'"
fi
