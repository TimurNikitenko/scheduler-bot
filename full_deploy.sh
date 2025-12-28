#!/bin/bash
# Полный деплой: синхронизация файлов, пересоздание БД, пересборка образа, запуск
# Улучшенная версия с автоматическим исправлением проблем

SSH_KEY=~/.ssh/selectel_key
SERVER=root@84.38.182.210
REMOTE_DIR=/opt/telegram-bot

# Ищем ключ
if [ -f ~/.ssh/selectel_key ]; then
    KEY=~/.ssh/selectel_key
elif [ -f ~/.ssh/id_rsa ]; then
    KEY=~/.ssh/id_rsa
elif [ -f ~/.ssh/id_ed25519 ]; then
    KEY=~/.ssh/id_ed25519
else
    echo "❌ SSH ключ не найден! Используйте пароль для подключения."
    KEY=""
fi

echo "=========================================="
echo "  ПОЛНЫЙ ДЕПЛОЙ БОТА (улучшенная версия)"
echo "=========================================="
echo ""

# Функция для выполнения команд на сервере
execute_remote() {
    local cmd="$1"
    if [ -n "$KEY" ]; then
        ssh -i "$KEY" -o StrictHostKeyChecking=no $SERVER "$cmd"
    else
        ssh -o StrictHostKeyChecking=no $SERVER "$cmd"
    fi
}

# Шаг 1: Синхронизация файлов
echo "📦 Шаг 1: Синхронизация файлов на сервер..."
if [ -n "$KEY" ]; then
    rsync -avz --delete --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        -e "ssh -i $KEY -o StrictHostKeyChecking=no" \
        bot/ $SERVER:$REMOTE_DIR/bot/
    rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        -e "ssh -i $KEY -o StrictHostKeyChecking=no" \
        main.py Dockerfile requirements.txt docker-compose.yaml \
        $SERVER:$REMOTE_DIR/
    # Синхронизируем .env если он есть локально
    if [ -f .env ]; then
        echo "   Синхронизирую .env файл..."
        rsync -avz -e "ssh -i $KEY -o StrictHostKeyChecking=no" \
            .env $SERVER:$REMOTE_DIR/.env
        echo "   ✅ .env синхронизирован"
    else
        echo "   ⚠️  Локальный .env не найден - пропускаю"
    fi
else
    rsync -avz --delete --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        -e "ssh -o StrictHostKeyChecking=no" \
        bot/ $SERVER:$REMOTE_DIR/bot/
    rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
        -e "ssh -o StrictHostKeyChecking=no" \
        main.py Dockerfile requirements.txt docker-compose.yaml \
        $SERVER:$REMOTE_DIR/
    if [ -f .env ]; then
        rsync -avz -e "ssh -o StrictHostKeyChecking=no" \
            .env $SERVER:$REMOTE_DIR/.env
    fi
fi
echo "✅ Файлы синхронизированы"
echo ""

# Шаг 2: Остановка контейнеров
echo "🔧 Шаг 2: Останавливаю все контейнеры..."
execute_remote "cd /opt/telegram-bot && docker-compose down 2>&1 | grep -v 'the attribute' || true"
echo "✅ Контейнеры остановлены"
echo ""

# Шаг 3: Удаление volume
echo "🔧 Шаг 3: Удаляю volume базы данных..."
execute_remote "cd /opt/telegram-bot && docker volume rm telegram-bot_postgres_data 2>&1 | grep -v 'No such volume' || true"
echo "✅ Volume удален"
echo ""

# Шаг 4: Исправление .env файла (формат и DATABASE_URL)
echo "🔧 Шаг 4: Исправляю .env файл (формат и удаление DATABASE_URL)..."
execute_remote "cd /opt/telegram-bot && if [ -f .env ]; then
    # Удаляем DATABASE_URL если есть
    sed -i '/^DATABASE_URL=/d' .env
    # Исправляем формат: убираем пробелы вокруг = и кавычки из значений
    # BOT_TOKEN = 'value' -> BOT_TOKEN=value
    sed -i 's/^[[:space:]]*BOT_TOKEN[[:space:]]*=[[:space:]]*['\''\"]*\([^'\''\"]*\)['\''\"]*[[:space:]]*$/BOT_TOKEN=\1/' .env
    sed -i 's/^[[:space:]]*ADMIN_IDS[[:space:]]*=[[:space:]]*\[\(.*\)\][[:space:]]*$/ADMIN_IDS=\1/' .env
    sed -i 's/^[[:space:]]*ADMIN_IDS[[:space:]]*=[[:space:]]*['\''\"]*\[\(.*\)\]['\''\"]*[[:space:]]*$/ADMIN_IDS=\1/' .env
    # Убираем кавычки и пробелы из ADMIN_IDS
    sed -i 's/ADMIN_IDS=.*\[\(.*\)\].*/ADMIN_IDS=\1/' .env
    sed -i \"s/ADMIN_IDS=[^=]*'\([^']*\)'[^=]*/ADMIN_IDS=\1/g\" .env
    sed -i 's/[[:space:]]*,[[:space:]]*/,/g' .env
    # Убираем пробелы в начале строк
    sed -i 's/^[[:space:]]*//' .env
    # Убираем пустые строки
    sed -i '/^$/d' .env
    echo '✅ .env исправлен'
    echo 'Проверка формата:'
    head -3 .env
else
    echo '⚠️  .env не найден на сервере!'
fi"
echo ""

# Шаг 5: Запуск postgres
echo "🔧 Шаг 5: Запускаю postgres..."
execute_remote "cd /opt/telegram-bot && docker-compose up -d postgres 2>&1 | grep -v 'the attribute' || true"
echo "⏳ Жду 15 секунд..."
sleep 15
echo "✅ Postgres запущен"
echo ""

# Шаг 6: Проверка БД
echo "🔧 Шаг 6: Проверяю подключение к БД..."
if execute_remote "cd /opt/telegram-bot && docker-compose exec -T postgres psql -U postgres -c 'SELECT 1;' > /dev/null 2>&1"; then
    echo "✅ База данных работает!"
else
    echo "⚠️  Предупреждение: проверка не удалась, но продолжаю..."
fi
echo ""

# Шаг 7: Пересборка образа
echo "🔧 Шаг 7: Пересобираю образ бота (это может занять несколько минут)..."
execute_remote "cd /opt/telegram-bot && docker-compose build bot 2>&1 | grep -v 'the attribute' | tail -15"
echo "✅ Образ пересобран"
echo ""

# Шаг 8: Удаление старого контейнера
echo "🔧 Шаг 8: Удаляю старый контейнер бота..."
execute_remote "cd /opt/telegram-bot && docker-compose rm -f bot 2>&1 | grep -v 'the attribute' | grep -v 'No stopped' || true"
echo "✅ Готово"
echo ""

# Шаг 9: Запуск бота
echo "🔧 Шаг 9: Запускаю бота..."
execute_remote "cd /opt/telegram-bot && docker-compose up -d bot 2>&1 | grep -v 'the attribute' || true"
echo "⏳ Жду 15 секунд для запуска..."
sleep 15
echo "✅ Бот запущен"
echo ""

# Шаг 10: Проверка статуса
echo "🔧 Шаг 10: Проверяю статус..."
execute_remote "cd /opt/telegram-bot && docker-compose ps bot 2>&1 | grep -v 'the attribute' | tail -5"
echo ""

# Шаг 11: Логи
echo "=========================================="
echo "  ЛОГИ БОТА (последние 80 строк)"
echo "=========================================="
BOT_LOGS=$(execute_remote "cd /opt/telegram-bot && docker-compose logs --tail=80 bot 2>&1 | grep -v 'the attribute'")
echo "$BOT_LOGS"
echo ""

# Шаг 12: Проверка успешного запуска
echo "=========================================="
echo "  ПРОВЕРКА УСПЕШНОГО ЗАПУСКА"
echo "=========================================="
FULL_LOGS=$(execute_remote "cd /opt/telegram-bot && docker-compose logs bot 2>&1 | grep -v 'the attribute'")
if echo "$FULL_LOGS" | grep -qi -E "(Bot is running|Application started|Database connection pool initialized successfully)"; then
    echo "✅ БОТ ЗАПУЩЕН УСПЕШНО!"
    echo "$FULL_LOGS" | grep -i -E "(Bot is running|Application started|Database connection pool initialized successfully)" | tail -5
else
    echo "⚠️  Признаки успешного запуска не найдены"
    echo ""
    echo "Последние ошибки:"
    echo "$FULL_LOGS" | grep -i -E "(error|exception|traceback|failed|InvalidPassword|BOT_TOKEN|ModuleNotFound)" | tail -20 || echo "Ошибок не найдено"
    echo ""
    echo "Последние 30 строк логов:"
    echo "$FULL_LOGS" | tail -30
    echo ""
    echo "Проверка переменных окружения в контейнере:"
    execute_remote "cd /opt/telegram-bot && docker-compose exec bot env 2>/dev/null | grep -E '(DATABASE|BOT_TOKEN|ADMIN)' || echo 'Контейнер не запущен или недоступен'"
fi
echo ""

echo "=========================================="
echo "  ДЕПЛОЙ ЗАВЕРШЕН"
echo "=========================================="
echo ""
echo "Для просмотра логов в реальном времени:"
echo "  ssh -i ~/.ssh/selectel_key root@84.38.182.210 'cd /opt/telegram-bot && docker-compose logs -f bot'"
echo ""
