#!/bin/bash

# Automatic deployment script for Telegram Bot
# This script quickly deploys changes to the server without full rebuild
# Usage: ./auto_deploy.sh [user@host] [--rebuild] [--no-logs]
#
# Options:
#   --rebuild    Rebuild Docker images (slower but ensures fresh build)
#   --no-logs    Don't show logs after deployment

set -e

# Load deployment config if exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/deploy_config.sh" ]; then
    source "$SCRIPT_DIR/deploy_config.sh"
fi

# Configuration (can be overridden by environment variables or arguments)
REMOTE_HOST="${DEPLOY_HOST:-root@84.35.184.210}"
REMOTE_DIR="${DEPLOY_DIR:-/opt/telegram-bot}"
LOCAL_DIR="$(pwd)"
REBUILD="${DEPLOY_REBUILD:-false}"
SHOW_LOGS="${DEPLOY_SHOW_LOGS:-true}"

# Parse command line arguments
REMOTE_HOST_OVERRIDE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --rebuild)
            REBUILD="true"
            shift
            ;;
        --no-logs)
            SHOW_LOGS="false"
            shift
            ;;
        *)
            if [ -z "$REMOTE_HOST_OVERRIDE" ]; then
                REMOTE_HOST_OVERRIDE="$1"
            fi
            shift
            ;;
    esac
done

# Override with command line argument if provided
if [ -n "$REMOTE_HOST_OVERRIDE" ]; then
    REMOTE_HOST="$REMOTE_HOST_OVERRIDE"
fi

# Detect SSH key
SSH_KEY=""
SSH_KEY_PATH="${DEPLOY_SSH_KEY:-$HOME/.ssh/selectel_key}"
# Expand ~ if present
if [[ "$SSH_KEY_PATH" == ~* ]]; then
    SSH_KEY_PATH="${SSH_KEY_PATH/#\~/$HOME}"
fi
if [ -f "$SSH_KEY_PATH" ]; then
    SSH_KEY="-i $SSH_KEY_PATH"
    echo "🔑 Using SSH key: $SSH_KEY_PATH"
else
    echo "⚠️  SSH key not found at $SSH_KEY_PATH"
    echo "   Will try to connect without key (may prompt for password)"
fi

echo "🚀 Starting automatic deployment to $REMOTE_HOST..."
echo "📁 Remote directory: $REMOTE_DIR"
echo ""

# Check if .env file exists locally
if [ ! -f ".env" ]; then
    echo "⚠️  WARNING: .env file not found locally!"
    echo "   The script will continue, but make sure .env exists on the server."
else
    echo "✅ Found .env file"
fi

# Create remote directory if it doesn't exist
echo "📁 Ensuring remote directory exists..."
if [ -n "$SSH_KEY" ]; then
    ssh $SSH_KEY "$REMOTE_HOST" "mkdir -p $REMOTE_DIR" || {
        echo "❌ Failed to create remote directory"
        exit 1
    }
else
    ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR" || {
        echo "❌ Failed to create remote directory"
        exit 1
    }
fi

# Copy files (excluding unnecessary files)
echo "📦 Copying files to server..."
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
        --exclude 'node_modules' \
        --exclude '.idea' \
        --exclude '.vscode' \
        "$LOCAL_DIR/" "$REMOTE_HOST:$REMOTE_DIR/" || {
        echo "❌ Failed to copy files"
        exit 1
    }
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
        --exclude 'node_modules' \
        --exclude '.idea' \
        --exclude '.vscode' \
        "$LOCAL_DIR/" "$REMOTE_HOST:$REMOTE_DIR/" || {
        echo "❌ Failed to copy files"
        exit 1
    }
fi

echo "✅ Files copied successfully"
echo ""

# Check if docker-compose is available on remote
echo "🐳 Checking Docker Compose..."
if [ -n "$SSH_KEY" ]; then
    if ! ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && command -v docker-compose >/dev/null 2>&1"; then
        echo "❌ Docker Compose not found on remote server"
        echo "   Please run the full deploy.sh script first to set up the environment"
        exit 1
    fi
else
    if ! ssh "$REMOTE_HOST" "cd $REMOTE_DIR && command -v docker-compose >/dev/null 2>&1"; then
        echo "❌ Docker Compose not found on remote server"
        echo "   Please run the full deploy.sh script first to set up the environment"
        exit 1
    fi
fi

# Rebuild and restart if needed
if [ "$REBUILD" = "true" ]; then
    echo "🏗️  Rebuilding Docker images..."
    if [ -n "$SSH_KEY" ]; then
        ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose build bot" || {
            echo "❌ Failed to build Docker image"
            exit 1
        }
    else
        ssh "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose build bot" || {
            echo "❌ Failed to build Docker image"
            exit 1
        }
    fi
    echo "✅ Docker images rebuilt"
    echo ""
fi

# Verify files were copied
echo "🔍 Verifying files on server..."
if [ -n "$SSH_KEY" ]; then
    ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && ls -la bot/handlers.py bot/database.py && head -5 bot/handlers.py | grep -q 'DEBUG' && echo '✅ Files updated' || echo '⚠️  Files may not be updated'"
else
    ssh "$REMOTE_HOST" "cd $REMOTE_DIR && ls -la bot/handlers.py bot/database.py && head -5 bot/handlers.py | grep -q 'DEBUG' && echo '✅ Files updated' || echo '⚠️  Files may not be updated'"
fi

# Restart bot service (this will pick up code changes)
echo "🔄 Restarting bot service..."
if [ -n "$SSH_KEY" ]; then
    # Stop, remove, and recreate container to ensure fresh start
    # Also clear Python cache
    ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true && find . -name '*.pyc' -delete 2>/dev/null || true && docker-compose stop bot && docker-compose rm -f bot && docker-compose up -d bot" || {
        echo "⚠️  Failed to recreate bot, trying simple restart..."
        ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose restart bot" || {
            echo "❌ Failed to restart bot"
            exit 1
        }
    }
else
    ssh "$REMOTE_HOST" "cd $REMOTE_DIR && find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true && find . -name '*.pyc' -delete 2>/dev/null || true && docker-compose stop bot && docker-compose rm -f bot && docker-compose up -d bot" || {
        echo "⚠️  Failed to recreate bot, trying simple restart..."
        ssh "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose restart bot" || {
            echo "❌ Failed to restart bot"
            exit 1
        }
    }
fi

echo "✅ Bot service restarted"
echo ""

# Wait a moment for the service to start
echo "⏳ Waiting for service to start..."
sleep 3

# Check service status
echo "📊 Service status:"
if [ -n "$SSH_KEY" ]; then
    ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose ps"
else
    ssh "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose ps"
fi

# Show logs if requested
if [ "$SHOW_LOGS" = "true" ]; then
    echo ""
    echo "📝 Recent bot logs (last 20 lines):"
    if [ -n "$SSH_KEY" ]; then
        ssh $SSH_KEY "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose logs --tail=20 bot"
    else
        ssh "$REMOTE_HOST" "cd $REMOTE_DIR && docker-compose logs --tail=20 bot"
    fi
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "💡 Useful commands:"
if [ -n "$SSH_KEY" ]; then
    echo "  View logs: ssh $SSH_KEY $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose logs -f bot'"
    echo "  View all logs: ssh $SSH_KEY $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose logs -f'"
    echo "  Restart bot: ssh $SSH_KEY $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose restart bot'"
    echo "  Stop bot: ssh $SSH_KEY $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose stop bot'"
else
    echo "  View logs: ssh $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose logs -f bot'"
    echo "  View all logs: ssh $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose logs -f'"
    echo "  Restart bot: ssh $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose restart bot'"
    echo "  Stop bot: ssh $REMOTE_HOST 'cd $REMOTE_DIR && docker-compose stop bot'"
fi

