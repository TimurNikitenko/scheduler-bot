# Инструкция по загрузке кода в GitHub

## Текущее состояние

✅ Git репозиторий инициализирован
✅ Коммит создан
✅ Remote добавлен: `https://github.com/TimurNikitenko/scheduler-bot.git`

## Вариант 1: Использовать Personal Access Token (рекомендуется)

1. **Создайте Personal Access Token на GitHub:**
   - Перейдите: https://github.com/settings/tokens
   - Нажмите "Generate new token" → "Generate new token (classic)"
   - Выберите срок действия и права доступа (нужен `repo`)
   - Скопируйте токен

2. **Загрузите код:**
   ```bash
   cd ~/projects
   git push -u origin main
   ```
   
   Когда попросит:
   - **Username**: ваш GitHub username
   - **Password**: вставьте Personal Access Token (не пароль!)

## Вариант 2: Настроить SSH ключ для GitHub

1. **Проверьте, есть ли SSH ключ:**
   ```bash
   ls -la ~/.ssh/id_*.pub
   ```

2. **Если ключа нет, создайте:**
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   # Нажмите Enter для всех вопросов
   ```

3. **Скопируйте публичный ключ:**
   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```

4. **Добавьте ключ на GitHub:**
   - Перейдите: https://github.com/settings/keys
   - Нажмите "New SSH key"
   - Вставьте содержимое `~/.ssh/id_ed25519.pub`
   - Сохраните

5. **Измените remote на SSH:**
   ```bash
   cd ~/projects
   git remote set-url origin git@github.com:TimurNikitenko/scheduler-bot.git
   git push -u origin main
   ```

## Вариант 3: Использовать GitHub CLI

Если установлен `gh`:
```bash
gh auth login
git push -u origin main
```

## Быстрая команда для загрузки

После настройки аутентификации:

```bash
cd ~/projects
git push -u origin main
```

## Проверка

После успешной загрузки проверьте на GitHub:
- https://github.com/TimurNikitenko/scheduler-bot

Все файлы должны быть там (кроме `.env`, который в `.gitignore`).

