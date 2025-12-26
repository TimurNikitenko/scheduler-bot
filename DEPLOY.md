# Инструкция по деплою бота на Selectel VDS

## Подготовка

1. **Убедитесь, что у вас есть:**
   - SSH доступ к VDS серверу
   - Приватный SSH ключ для доступа
   - Файл `.env` с настройками бота

2. **Проверьте содержимое `.env`:**
   ```bash
   BOT_TOKEN=ваш_токен_бота
   ADMIN_IDS=ваш_telegram_id
   DATABASE_URL=postgresql://postgres:postgres@postgres:5432/telegram_bot
   ```

## Деплой

### Вариант 1: Автоматический деплой (рекомендуется)

1. **Сделайте скрипт исполняемым:**
   ```bash
   chmod +x deploy.sh
   ```

2. **Запустите деплой:**
   ```bash
   ./deploy.sh user@your-server-ip
   ```
   
   Например:
   ```bash
   ./deploy.sh root@123.45.67.89
   ```

3. **Скрипт автоматически:**
   - Скопирует все файлы на сервер
   - Установит Docker и Docker Compose (если не установлены)
   - Соберет и запустит контейнеры
   - Покажет статус сервисов

### Вариант 2: Ручной деплой

1. **Подключитесь к серверу:**
   ```bash
   ssh user@your-server-ip
   ```

2. **Установите Docker и Docker Compose** (если не установлены):
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   systemctl enable docker
   systemctl start docker
   
   curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   chmod +x /usr/local/bin/docker-compose
   ```

3. **Создайте директорию и скопируйте файлы:**
   ```bash
   mkdir -p /opt/telegram-bot
   # Скопируйте все файлы проекта (кроме .git, .venv, __pycache__)
   ```

4. **Создайте `.env` файл на сервере:**
   ```bash
   cd /opt/telegram-bot
   nano .env
   ```
   
   Добавьте:
   ```
   BOT_TOKEN=ваш_токен_бота
   ADMIN_IDS=ваш_telegram_id
   DATABASE_URL=postgresql://postgres:postgres@postgres:5432/telegram_bot
   ```

5. **Запустите сервисы:**
   ```bash
   docker-compose up -d
   ```

## Управление ботом

### Просмотр логов
```bash
ssh user@server 'cd /opt/telegram-bot && docker-compose logs -f bot'
```

### Остановка бота
```bash
ssh user@server 'cd /opt/telegram-bot && docker-compose stop bot'
```

### Перезапуск бота
```bash
ssh user@server 'cd /opt/telegram-bot && docker-compose restart bot'
```

### Просмотр статуса
```bash
ssh user@server 'cd /opt/telegram-bot && docker-compose ps'
```

### Обновление бота
```bash
# На локальной машине
./deploy.sh user@server

# Или вручную на сервере
cd /opt/telegram-bot
git pull  # если используете git
docker-compose build
docker-compose up -d
```

## Проверка работы

1. **Проверьте логи:**
   ```bash
   ssh user@server 'cd /opt/telegram-bot && docker-compose logs bot | tail -50'
   ```

2. **Проверьте статус контейнеров:**
   ```bash
   ssh user@server 'cd /opt/telegram-bot && docker-compose ps'
   ```

3. **Отправьте команду `/start` боту в Telegram**

## Решение проблем

### Бот не отвечает
- Проверьте логи: `docker-compose logs bot`
- Убедитесь, что `BOT_TOKEN` правильный
- Проверьте, что бот запущен: `docker-compose ps`

### Ошибки подключения к базе данных
- Убедитесь, что PostgreSQL контейнер запущен: `docker-compose ps postgres`
- Проверьте `DATABASE_URL` в `.env`
- Проверьте логи PostgreSQL: `docker-compose logs postgres`

### Проблемы с правами
- Убедитесь, что у пользователя есть права на Docker: `sudo usermod -aG docker $USER`

## Безопасность

1. **Не коммитьте `.env` файл в git** (он уже в `.gitignore`)
2. **Используйте сильные пароли** для PostgreSQL в продакшене
3. **Настройте firewall** на VDS для ограничения доступа
4. **Регулярно обновляйте** зависимости и систему

## Автозапуск при перезагрузке

Docker Compose автоматически запускает контейнеры при перезагрузке сервера благодаря `restart: unless-stopped` в `docker-compose.yaml`.

