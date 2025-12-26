# Telegram Bot - Schedule Management System

A Telegram bot for managing employee schedules, shifts, and salary calculations.

## Features

### Admin Features
1. **Расписание (Schedule)** - View schedules for all employees or a specific employee
2. **Редактировать расписание (Edit Schedule)** - Add or delete schedule events
3. **Отчет (Report)** - Generate salary reports for employees
4. **Поставить смены (Set Shifts)** - Assign employees to schedule slots

### Employee Features
1. **Моя зарплата (My Salary)** - View salary for a specific period
2. **Мое расписание (My Schedule)** - View personal schedule for a date or date range
3. **Выставить свободное время (Set Free Time)** - Add available time slots

## Setup

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd telegram-bot
   ```

2. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```

2. **Configure `.env`:**
   - `BOT_TOKEN`: Your Telegram bot token (get it from [@BotFather](https://t.me/BotFather))
   - `ADMIN_IDS`: Comma-separated list of Telegram user IDs who should have admin access
   - `DATABASE_URL`: PostgreSQL connection string (optional, defaults to docker-compose settings)

   Example:
   ```
   BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ADMIN_IDS=123456789,987654321
   DATABASE_URL=postgresql://postgres:postgres@postgres:5432/telegram_bot
   ```

3. **Start services with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **View logs:**
   ```bash
   docker-compose logs -f bot
   ```

### Manual Setup

1. **Start PostgreSQL database:**
   ```bash
   docker-compose up -d postgres
   ```
   Or use your own PostgreSQL instance.

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file:**
   ```bash
   cp .env.example .env
   ```

4. **Configure `.env`:**
   - `BOT_TOKEN`: Your Telegram bot token (get it from [@BotFather](https://t.me/BotFather))
   - `ADMIN_IDS`: Comma-separated list of Telegram user IDs who should have admin access
   - `DATABASE_URL`: PostgreSQL connection string

   Example:
   ```
   BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ADMIN_IDS=123456789,987654321
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/telegram_bot
   ```

5. **Run the bot:**
   ```bash
   python main.py
   ```

## Usage

1. Start the bot by sending `/start` command
2. Use the keyboard buttons to navigate through features
3. Follow the prompts to complete actions

## Database

The bot uses PostgreSQL database to store:
- Users (employees and admins)
- Schedule slots
- Shifts (assigned employees)
- Free time slots

The database is automatically initialized on first run. When using Docker Compose, PostgreSQL is automatically set up and the bot will connect to it.

### Clearing Database

To clear the database (useful for removing old test data):

```bash
python clear_database.py
```

Options:
- **Clear all data**: Deletes all users, shifts, slots, and free time slots
- **Clear employees only**: Deletes only employees (keeps admins) and their related data

⚠️ **WARNING**: This operation cannot be undone! Make sure to backup your data if needed.

## Notes

- Date format: `YYYY-MM-DD` (e.g., `2025-01-01`)
- Time format: `HH:MM` (e.g., `09:00`)
- Date ranges: Enter as `date_start date_end` (e.g., `2025-01-01 2025-01-07`)

