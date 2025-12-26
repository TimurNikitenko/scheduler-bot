# Проверка доступа к репозиторию

## Возможные проблемы и решения

### 1. Репозиторий не существует или приватный

**Проверка:**
- Откройте в браузере: https://github.com/TimurNikitenko/scheduler-bot
- Если видите 404 - репозиторий не существует
- Если видите "Private" - нужна аутентификация

**Решение:**
- Создайте репозиторий на GitHub (если не создан)
- Убедитесь, что вы владелец или имеете права на запись

### 2. Нет аутентификации

**Для HTTPS:**
- Нужен Personal Access Token (не пароль!)
- Создайте токен: https://github.com/settings/tokens
- Используйте токен как пароль при `git push`

**Для SSH:**
- Нужен SSH ключ, добавленный на GitHub
- Проверьте: https://github.com/settings/keys

### 3. Репозиторий существует, но нет прав

**Проверьте:**
- Вы владелец репозитория?
- Или у вас есть права на запись (Write access)?

**Если нет прав:**
- Попросите владельца добавить вас как collaborator
- Или создайте свой репозиторий

### 4. Быстрое решение

**Создайте новый репозиторий:**
1. Перейдите: https://github.com/new
2. Название: `scheduler-bot` (или любое другое)
3. Выберите Public или Private
4. НЕ создавайте README, .gitignore, license
5. Нажмите "Create repository"

**Затем обновите remote:**
```bash
cd ~/projects
git remote set-url origin https://github.com/TimurNikitenko/scheduler-bot.git
# или если другое название:
# git remote set-url origin https://github.com/TimurNikitenko/your-repo-name.git
```

**И загрузите:**
```bash
git push -u origin main
```

### 5. Альтернатива: Использовать другой хостинг

Если проблемы с GitHub, можно использовать:
- GitLab: https://gitlab.com
- Bitbucket: https://bitbucket.org
- Или любой другой Git хостинг

Просто создайте репозиторий там и обновите remote URL.

