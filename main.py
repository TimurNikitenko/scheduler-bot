import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
from bot.database import Database
from bot.handlers import BotHandlers

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token and admin IDs
BOT_TOKEN = os.getenv('BOT_TOKEN')
admin_ids_str = os.getenv('ADMIN_IDS', '')
# Handle different formats: "123,456" or "['123', '456']" or "[123, 456]"
if admin_ids_str:
    # Remove brackets and quotes if present
    admin_ids_str = admin_ids_str.strip().strip('[]').strip("'\"")
    # Split by comma and clean up
    ADMIN_IDS = [int(id.strip().strip("'\"\"")) for id in admin_ids_str.split(',') if id.strip()]
else:
    ADMIN_IDS = []

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables")

# Database will be initialized in main()
db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')

# Import conversation states
from bot.handlers import (
    WAITING_DATE_RANGE, WAITING_EVENT_DATE, WAITING_EVENT_START, WAITING_EVENT_END,
    WAITING_ASSIGN_EMPLOYEE, WAITING_DELETE_DATE, WAITING_DELETE_SLOT,
    WAITING_REPORT_EMPLOYEE, WAITING_REPORT_PERIOD, WAITING_REPORT_RATE,
    WAITING_SHIFT_DATE, WAITING_SHIFT_SLOT, WAITING_SHIFT_EMPLOYEE,
    WAITING_SALARY_PERIOD, WAITING_SCHEDULE_DATE_RANGE, WAITING_SCHEDULE_DATE,
    WAITING_FREE_TIME_DATE, WAITING_FREE_TIME_SLOTS,
    WAITING_WORKER_MENU, WAITING_WORKER_USER_ID, WAITING_WORKER_NAME, WAITING_ADMIN_USER_ID,
    WAITING_PERIOD_START, WAITING_PERIOD_END
)


async def main():
    # Initialize database pool
    db = Database(db_url=db_url)
    try:
        logger.info("Initializing database connection pool...")
        await db.init_pool()
        logger.info("Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise
    
    # Initialize handlers
    handlers = BotHandlers(db, ADMIN_IDS)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Start command
    application.add_handler(CommandHandler("start", handlers.start))
    
    # Test command to verify bot is working
    async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Бот работает! Используйте /start для получения клавиатуры.")
    application.add_handler(CommandHandler("test", test_command))

    # Admin: Schedule viewing
    admin_schedule_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^1\. Расписание$"), handlers.admin_schedule)],
        states={
            WAITING_DATE_RANGE: [
                CallbackQueryHandler(handlers.admin_schedule_employee_selected, pattern="^emp_"),
                CallbackQueryHandler(handlers.admin_schedule_period_selected, pattern="^period_"),
                CallbackQueryHandler(handlers.admin_schedule_period_start_selected, pattern="^period_start_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_schedule_date_range)
            ],
            WAITING_PERIOD_START: [
                CallbackQueryHandler(handlers.admin_schedule_period_start_selected, pattern="^period_start_")
            ],
            WAITING_PERIOD_END: [
                CallbackQueryHandler(handlers.admin_schedule_period_end_selected, pattern="^period_end_")
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            MessageHandler(filters.Regex("^(1\. Расписание|2\. Редактировать расписание|3\. Отчет|4\. Поставить смены|5\. Управление сотрудниками|1\. Моя зарплата|2\. Мое расписание|3\. Выставить свободное время)$"), handlers.handle_menu_command_in_conversation)
        ]
    )
    application.add_handler(admin_schedule_conv)

    # Admin: Edit schedule
    admin_edit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^2\. Редактировать расписание$"), handlers.admin_edit_schedule)],
        states={
            WAITING_EVENT_DATE: [
                CallbackQueryHandler(handlers.admin_add_event, pattern="^add_event$"),
                CallbackQueryHandler(handlers.admin_delete_event, pattern="^delete_event$"),
                CallbackQueryHandler(handlers.admin_event_date_selected, pattern="^date_"),
            ],
            WAITING_EVENT_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_event_start)
            ],
            WAITING_EVENT_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_event_end)
            ],
            WAITING_ASSIGN_EMPLOYEE: [
                CallbackQueryHandler(handlers.admin_assign_employee_decision, pattern="^assign_"),
                CallbackQueryHandler(handlers.admin_assign_employee, pattern="^emp_")
            ],
            WAITING_DELETE_DATE: [
                CallbackQueryHandler(handlers.admin_delete_date_selected, pattern="^date_")
            ],
            WAITING_DELETE_SLOT: [
                CallbackQueryHandler(handlers.admin_delete_slot_selected, pattern="^(slot_|confirm_delete_)")
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            MessageHandler(filters.Regex("^(1\. Расписание|2\. Редактировать расписание|3\. Отчет|4\. Поставить смены|5\. Управление сотрудниками|1\. Моя зарплата|2\. Мое расписание|3\. Выставить свободное время)$"), handlers.handle_menu_command_in_conversation)
        ]
    )
    application.add_handler(admin_edit_conv)

    # Admin: Report
    admin_report_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^3\. Отчет$"), handlers.admin_report)],
        states={
            WAITING_REPORT_EMPLOYEE: [
                CallbackQueryHandler(handlers.admin_report_employee_selected, pattern="^emp_")
            ],
            WAITING_REPORT_PERIOD: [
                CallbackQueryHandler(handlers.admin_report_period_selected, pattern="^period_"),
                CallbackQueryHandler(handlers.admin_report_period_start_selected, pattern="^period_start_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_report_period)
            ],
            WAITING_PERIOD_START: [
                CallbackQueryHandler(handlers.admin_report_period_start_selected, pattern="^period_start_")
            ],
            WAITING_PERIOD_END: [
                CallbackQueryHandler(handlers.admin_report_period_end_selected, pattern="^period_end_")
            ],
            WAITING_REPORT_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_report_rate)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            MessageHandler(filters.Regex("^(1\. Расписание|2\. Редактировать расписание|3\. Отчет|4\. Поставить смены|5\. Управление сотрудниками|1\. Моя зарплата|2\. Мое расписание|3\. Выставить свободное время)$"), handlers.handle_menu_command_in_conversation)
        ]
    )
    application.add_handler(admin_report_conv)

    # Admin: Set shifts
    admin_shifts_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^4\. Поставить смены$"), handlers.admin_set_shifts)],
        states={
            WAITING_SHIFT_DATE: [
                CallbackQueryHandler(handlers.admin_shift_date_selected, pattern="^date_")
            ],
            WAITING_SHIFT_SLOT: [
                CallbackQueryHandler(handlers.admin_shift_slot_selected, pattern="^slot_")
            ],
            WAITING_SHIFT_EMPLOYEE: [
                CallbackQueryHandler(handlers.admin_shift_employee_selected, pattern="^emp_")
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            MessageHandler(filters.Regex("^(1\. Расписание|2\. Редактировать расписание|3\. Отчет|4\. Поставить смены|5\. Управление сотрудниками|1\. Моя зарплата|2\. Мое расписание|3\. Выставить свободное время)$"), handlers.handle_menu_command_in_conversation)
        ]
    )
    application.add_handler(admin_shifts_conv)

    # Employee: Salary
    employee_salary_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^1\. Моя зарплата$"), handlers.employee_salary)],
        states={
            WAITING_SALARY_PERIOD: [
                CallbackQueryHandler(handlers.employee_salary_period_selected, pattern="^period_"),
                CallbackQueryHandler(handlers.employee_salary_period_start_selected, pattern="^period_start_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.employee_salary_period)
            ],
            WAITING_PERIOD_START: [
                CallbackQueryHandler(handlers.employee_salary_period_start_selected, pattern="^period_start_")
            ],
            WAITING_PERIOD_END: [
                CallbackQueryHandler(handlers.employee_salary_period_end_selected, pattern="^period_end_")
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            MessageHandler(filters.Regex("^(1\. Расписание|2\. Редактировать расписание|3\. Отчет|4\. Поставить смены|5\. Управление сотрудниками|1\. Моя зарплата|2\. Мое расписание|3\. Выставить свободное время)$"), handlers.handle_menu_command_in_conversation)
        ]
    )
    application.add_handler(employee_salary_conv)

    # Employee: Schedule
    employee_schedule_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^2\. Мое расписание$"), handlers.employee_schedule)],
        states={
            WAITING_SCHEDULE_DATE: [
                CallbackQueryHandler(handlers.employee_schedule_date_selected, pattern="^date_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.employee_schedule_range)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            MessageHandler(filters.Regex("^(1\. Расписание|2\. Редактировать расписание|3\. Отчет|4\. Поставить смены|5\. Управление сотрудниками|1\. Моя зарплата|2\. Мое расписание|3\. Выставить свободное время)$"), handlers.handle_menu_command_in_conversation)
        ]
    )
    application.add_handler(employee_schedule_conv)

    # Employee: Free time
    employee_free_time_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^3\. Выставить свободное время$"), handlers.employee_free_time)],
        states={
            WAITING_FREE_TIME_DATE: [
                CallbackQueryHandler(handlers.employee_free_time_date_selected, pattern="^date_")
            ],
            WAITING_FREE_TIME_SLOTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.employee_free_time_slots)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            MessageHandler(filters.Regex("^(1\. Расписание|2\. Редактировать расписание|3\. Отчет|4\. Поставить смены|5\. Управление сотрудниками|1\. Моя зарплата|2\. Мое расписание|3\. Выставить свободное время)$"), handlers.handle_menu_command_in_conversation)
        ]
    )
    application.add_handler(employee_free_time_conv)

    # Admin: Worker Management
    admin_worker_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^5\. Управление сотрудниками$"), handlers.admin_worker_management)],
        states={
            WAITING_WORKER_MENU: [
                CallbackQueryHandler(handlers.admin_add_worker, pattern="^add_worker$"),
                CallbackQueryHandler(handlers.admin_remove_worker, pattern="^remove_worker$"),
                CallbackQueryHandler(handlers.admin_list_workers, pattern="^list_workers$"),
                CallbackQueryHandler(handlers.admin_make_admin, pattern="^make_admin$"),
                CallbackQueryHandler(handlers.admin_remove_worker_selected, pattern="^emp_"),
                CallbackQueryHandler(handlers.admin_confirm_remove_worker, pattern="^confirm_remove_")
            ],
            WAITING_WORKER_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_add_worker_user_id)
            ],
            WAITING_WORKER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_add_worker_name)
            ],
            WAITING_ADMIN_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.admin_make_admin_user_id)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", handlers.cancel),
            MessageHandler(filters.Regex("^(1\. Расписание|2\. Редактировать расписание|3\. Отчет|4\. Поставить смены|5\. Управление сотрудниками|1\. Моя зарплата|2\. Мое расписание|3\. Выставить свободное время)$"), handlers.handle_menu_command_in_conversation)
        ]
    )
    application.add_handler(admin_worker_conv)

    # Add error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log the error and send a telegram message to notify the developer."""
        logger.error("Exception while handling an update:", exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "Произошла ошибка. Попробуйте еще раз или используйте /start для перезапуска."
            )

    application.add_error_handler(error_handler)

    # Run bot
    logger.info("Bot starting...")
    try:
        # application.run_polling() handles async internally
        await application.initialize()
        await application.start()
        await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        logger.info("Bot is running. Press Ctrl+C to stop.")
        # Keep the bot running until interrupted
        stop_event = asyncio.Event()
        try:
            await stop_event.wait()
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await db.close_pool()
        logger.info("Bot shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())
