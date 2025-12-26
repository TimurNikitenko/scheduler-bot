# Настройка аутентификации для GitHub

## Репозиторий существует ✅
- URL: https://github.com/TimurNikitenko/scheduler-bot
- Статус: Публичный (Public)
- Проблема: Нет аутентификации

## Решение 1: Personal Access Token (Самый простой)

### Шаг 1: Создайте токен
1. Перейдите: https://github.com/settings/tokens
2. Нажмите "Generate new token" → "Generate new token (classic)"
3. Название: `scheduler-bot-deploy`
4. Срок действия: выберите нужный (например, 90 дней)
5. Права доступа: отметьте `repo` (полный доступ к репозиториям)
6. Нажмите "Generate token"
7. **ВАЖНО**: Скопируйте токен сразу (он показывается только один раз!)

### Шаг 2: Используйте токен
```bash
cd ~/projects
git push -u origin main
```

Когда попросит:
- **Username**: `TimurNikitenko` (ваш GitHub username)
- **Password**: вставьте Personal Access Token (НЕ пароль от GitHub!)

### Шаг 3: Сохранение токена (опционально)
Git может сохранить токен, чтобы не вводить каждый раз.

## Решение 2: Настроить SSH ключ

### Шаг 1: Проверьте существующие ключи
```bash
ls -la ~/.ssh/id_*.pub
```

### Шаг 2: Если ключа нет, создайте
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
# Нажмите Enter для всех вопросов (можно оставить пароль пустым)
```

### Шаг 3: Скопируйте публичный ключ
```bash
cat ~/.ssh/id_ed25519.pub
# Скопируйте весь вывод
```

### Шаг 4: Добавьте ключ на GitHub
1. Перейдите: https://github.com/settings/keys
2. Нажмите "New SSH key"
3. Title: `My Computer` (или любое название)
4. Key: вставьте скопированный ключ
5. Нажмите "Add SSH key"

### Шаг 5: Переключите на SSH
```bash
cd ~/projects
git remote set-url origin git@github.com:TimurNikitenko/scheduler-bot.git
git push -u origin main
```

## Решение 3: GitHub CLI (если установлен)

```bash
gh auth login
git push -u origin main
```

## Проверка после настройки

После успешной настройки проверьте:
```bash
git push -u origin main
```

Должно загрузиться без ошибок!

## Если ничего не помогает

Можно использовать веб-интерфейс GitHub:
1. Создайте файлы через веб-интерфейс
2. Или используйте GitHub Desktop
3. Или попросите кого-то с доступом помочь загрузить

