# Загрузка кода с Personal Access Token

## Проблема
VSCode credential helper не работает. Используем альтернативные методы.

## Метод 1: Использовать токен в URL (быстро)

**1. Создайте Personal Access Token:**
- https://github.com/settings/tokens
- Generate new token (classic)
- Права: `repo`
- Скопируйте токен

**2. Используйте токен в URL:**
```bash
cd ~/projects
git remote set-url origin https://<ВАШ_ТОКЕН>@github.com/TimurNikitenko/scheduler-bot.git
git push -u origin main
```

**Пример:**
```bash
git remote set-url origin https://ghp_xxxxxxxxxxxxxxxxxxxx@github.com/TimurNikitenko/scheduler-bot.git
git push -u origin main
```

⚠️ **Внимание**: Токен будет виден в `git remote -v`. После успешной загрузки можно вернуть обычный URL.

## Метод 2: Использовать GIT_ASKPASS

**1. Создайте скрипт:**
```bash
cat > ~/git-askpass.sh << 'EOF'
#!/bin/bash
echo "$GIT_TOKEN"
EOF
chmod +x ~/git-askpass.sh
```

**2. Используйте:**
```bash
export GIT_TOKEN="ваш_токен_здесь"
export GIT_ASKPASS=~/git-askpass.sh
git push -u origin main
```

## Метод 3: Ввести токен вручную

```bash
git push -u origin main
```

Когда попросит:
- Username: `TimurNikitenko`
- Password: вставьте токен

Если не работает, попробуйте:
```bash
GIT_TERMINAL_PROMPT=1 git push -u origin main
```

## Метод 4: Использовать GitHub CLI

Если установлен `gh`:
```bash
gh auth login
git push -u origin main
```

## После успешной загрузки

Верните обычный URL (без токена):
```bash
git remote set-url origin https://github.com/TimurNikitenko/scheduler-bot.git
```

Токен уже будет сохранен в `~/.git-credentials`.

