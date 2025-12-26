# Настройка SSH ключа для доступа к VDS

## Шаг 1: Сохраните ключ

Если вам дали файл с ключом (например, `id_rsa` или `key.pem`), выполните:

```bash
# Создайте директорию .ssh если её нет
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Скопируйте ключ в .ssh директорию
# Если файл называется, например, "selectel_key" или "key.pem":
cp /путь/к/вашему/файлу/с/ключом ~/.ssh/selectel_key

# Или если файл уже в текущей директории:
cp selectel_key ~/.ssh/selectel_key

# Установите правильные права доступа (ОБЯЗАТЕЛЬНО!)
chmod 600 ~/.ssh/selectel_key
```

## Шаг 2: Проверьте подключение

```bash
# Попробуйте подключиться
ssh -i ~/.ssh/selectel_key root@84.35.184.210
```

Если подключение работает, переходите к шагу 3.

## Шаг 3: Настройте SSH config (опционально, но удобно)

Создайте или отредактируйте файл `~/.ssh/config`:

```bash
nano ~/.ssh/config
```

Добавьте туда:

```
Host selectel
    HostName 84.35.184.210
    User root
    IdentityFile ~/.ssh/selectel_key
    IdentitiesOnly yes
```

Сохраните файл и установите права:
```bash
chmod 600 ~/.ssh/config
```

Теперь можно подключаться просто:
```bash
ssh selectel
```

## Шаг 4: Проверьте подключение для деплоя

После настройки ключа, проверьте что деплой скрипт сможет подключиться:

```bash
# Если используете config:
ssh selectel "echo 'Connection OK'"

# Или напрямую:
ssh -i ~/.ssh/selectel_key root@84.35.184.210 "echo 'Connection OK'"
```

## Шаг 5: Запустите деплой

После успешной проверки подключения:

```bash
# Если настроили config:
./deploy.sh selectel

# Или напрямую:
./deploy.sh root@84.35.184.210
```

## Решение проблем

### Ошибка "Permission denied (publickey)"
- Убедитесь, что права на ключ правильные: `chmod 600 ~/.ssh/selectel_key`
- Проверьте, что используете правильный ключ: `ssh -i ~/.ssh/selectel_key root@84.35.184.210`

### Ошибка "WARNING: UNPROTECTED PRIVATE KEY FILE!"
- Установите правильные права: `chmod 600 ~/.ssh/selectel_key`

### Ключ в неправильном формате
- Если ключ в формате OpenSSH (начинается с `-----BEGIN OPENSSH PRIVATE KEY-----`), используйте как есть
- Если ключ в формате PEM (начинается с `-----BEGIN RSA PRIVATE KEY-----`), тоже используйте как есть
- Если ключ в другом формате, может потребоваться конвертация

