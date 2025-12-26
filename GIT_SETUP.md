# Инструкция по загрузке в Git репозиторий

## Текущее состояние

✅ Git репозиторий инициализирован
✅ Все файлы подготовлены к коммиту
✅ `.env.example` создан
✅ `.gitignore` настроен правильно

## Шаги для загрузки в новый репозиторий

### 1. Создайте репозиторий на GitHub/GitLab/Bitbucket

Создайте новый пустой репозиторий (без README, без .gitignore).

### 2. Сделайте первый коммит

```bash
cd ~/projects
git add .
git commit -m "Initial commit: Telegram bot for schedule management

- Full async implementation with asyncpg
- Admin features: schedule viewing, editing, reports, shift assignment, worker management
- Employee features: salary calculation, schedule viewing, free time management
- Docker Compose setup for easy deployment
- PostgreSQL database with connection pooling
- Interactive date period selection with keyboards
- Worker management: add/remove/list/make admin
- Support for adding workers by username or User ID"
```

### 3. Добавьте remote и загрузите

```bash
# Замените <repository-url> на URL вашего репозитория
# Например: https://github.com/username/telegram-bot.git
# Или: git@github.com:username/telegram-bot.git

git remote add origin <repository-url>
git branch -M main  # Переименовать master в main (если нужно)
git push -u origin main
```

### 4. Если репозиторий уже существует и не пустой

Если в репозитории уже есть файлы (например, README), сначала получите их:

```bash
git remote add origin <repository-url>
git branch -M main
git pull origin main --allow-unrelated-histories
# Разрешите конфликты, если они есть
git push -u origin main
```

## Проверка

После загрузки проверьте, что все файлы на месте:

```bash
git ls-files
```

## Важные файлы, которые НЕ должны попасть в репозиторий

Следующие файлы автоматически игнорируются (благодаря `.gitignore`):
- `.env` - содержит секретные данные (токен бота)
- `__pycache__/` - кеш Python
- `*.log` - логи
- `venv/`, `.venv/` - виртуальные окружения
- `postgres_data/` - данные базы данных

## Что будет в репозитории

✅ Все исходные файлы проекта
✅ `.env.example` - пример конфигурации
✅ `README.md` - документация
✅ `DEPLOY.md` - инструкция по деплою
✅ `SSH_SETUP.md` - инструкция по настройке SSH
✅ `deploy.sh` - скрипт автоматического деплоя
✅ `docker-compose.yaml` - конфигурация Docker
✅ `requirements.txt` - зависимости Python

