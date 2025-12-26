from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from datetime import datetime, timedelta
from typing import Dict
import re
from .database import Database
from .keyboards import (
    get_main_keyboard, get_employee_selection_keyboard, get_schedule_edit_keyboard,
    get_date_selection_keyboard, get_slot_selection_keyboard, get_yes_no_keyboard,
    get_cancel_keyboard, get_worker_management_keyboard,
    get_period_selection_keyboard, get_period_start_date_keyboard, get_period_end_date_keyboard
)

# Conversation states
(
    WAITING_DATE_RANGE, WAITING_EVENT_DATE, WAITING_EVENT_START, WAITING_EVENT_END,
    WAITING_ASSIGN_EMPLOYEE, WAITING_DELETE_DATE, WAITING_DELETE_SLOT,
    WAITING_REPORT_EMPLOYEE, WAITING_REPORT_PERIOD, WAITING_REPORT_RATE,
    WAITING_SHIFT_DATE, WAITING_SHIFT_SLOT, WAITING_SHIFT_EMPLOYEE,
    WAITING_SALARY_PERIOD, WAITING_SCHEDULE_DATE_RANGE, WAITING_SCHEDULE_DATE,
    WAITING_FREE_TIME_DATE, WAITING_FREE_TIME_SLOTS,
    WAITING_WORKER_MENU, WAITING_WORKER_USER_ID, WAITING_WORKER_NAME, WAITING_ADMIN_USER_ID,
    WAITING_PERIOD_START, WAITING_PERIOD_END
) = range(24)


class BotHandlers:
    def __init__(self, db: Database, admin_ids: list):
        self.db = db
        self.admin_ids = admin_ids

    async def is_admin(self, user_id: int) -> bool:
        if user_id in self.admin_ids:
            return True
        return await self.db.is_admin(user_id)
    
    def is_menu_command(self, text: str) -> bool:
        """Check if text is a menu command"""
        menu_commands = [
            "1. Расписание", "2. Редактировать расписание", "3. Отчет",
            "4. Поставить смены", "5. Управление сотрудниками",
            "1. Моя зарплата", "2. Мое расписание", "3. Выставить свободное время"
        ]
        return text.strip() in menu_commands

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        is_admin = await self.is_admin(user_id)
        
        # Check if user is already in database
        existing_user = await self.db.get_user_by_id(user_id)
        is_new_user = existing_user is None
        
        try:
            await self.db.add_user(user_id, user.username, user.full_name, is_admin)
        except Exception as e:
            import logging
            logging.error(f"Error adding user to database: {e}")
        
        keyboard = get_main_keyboard(is_admin)
        
        if is_new_user and not is_admin:
            await update.message.reply_text(
                f"Привет, {user.first_name}!\n"
                f"Вы зарегистрированы как сотрудник.\n"
                f"Выберите действие:",
                reply_markup=keyboard
            )
        else:
            await update.message.reply_text(
                f"Привет, {user.first_name}! Выберите действие:",
                reply_markup=keyboard
            )
        
        # Log for debugging
        import logging
        logging.info(f"Sent keyboard to user {user_id}, is_admin: {is_admin}")

    # ========== ADMIN HANDLERS ==========
    
    async def admin_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: View schedule"""
        try:
            employees = await self.db.get_all_employees()
            if not employees:
                await update.message.reply_text(
                    "Нет сотрудников в базе.\n"
                    "Добавьте сотрудников через меню '5. Управление сотрудниками' -> 'Добавить сотрудника'"
                )
                return ConversationHandler.END
            
            keyboard = get_employee_selection_keyboard(employees)
            await update.message.reply_text(
                "Выберите сотрудника или 'Все':",
                reply_markup=keyboard
            )
            # Return a state that will handle the callback query
            # We'll use WAITING_DATE_RANGE but first handle employee selection
            return WAITING_DATE_RANGE
        except Exception as e:
            import logging
            logging.error(f"Error in admin_schedule: {e}", exc_info=True)
            try:
                await update.message.reply_text(
                    f"Произошла ошибка при получении списка сотрудников: {str(e)}\n"
                    "Попробуйте еще раз или используйте /start для перезапуска."
                )
            except:
                pass  # If we can't send message, at least log the error
            return ConversationHandler.END

    async def admin_schedule_employee_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "emp_all":
            context.user_data['schedule_employee'] = None
        else:
            emp_id = int(query.data.split("_")[1])
            context.user_data['schedule_employee'] = emp_id
        
        keyboard = get_period_selection_keyboard()
        await query.edit_message_text(
            "Выберите период:",
            reply_markup=keyboard
        )
        return WAITING_DATE_RANGE

    async def admin_schedule_period_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle period selection from keyboard"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_"):
            if query.data == "period_custom":
                # User wants custom period, ask for start date
                keyboard = get_period_start_date_keyboard()
                await query.edit_message_text(
                    "Выберите начальную дату периода:",
                    reply_markup=keyboard
                )
                return WAITING_PERIOD_START
            else:
                # Predefined period selected (format: period_YYYY-MM-DD_YYYY-MM-DD)
                _, start_date, end_date = query.data.split("_", 2)
                employee_id = context.user_data.get('schedule_employee')
                slots = await self.db.get_schedule_slots_by_range(start_date, end_date, employee_id)
                
                if not slots:
                    await query.edit_message_text("Нет слотов в этом периоде.")
                    return ConversationHandler.END
                
                schedule_text = "Расписание:\n\n"
                current_date = None
                for slot in slots:
                    slot_date = slot['date']
                    if slot_date != current_date:
                        current_date = slot_date
                        schedule_text += f"\n📅 {current_date}:\n"
                    
                    start_time = slot['start_time']
                    end_time = slot['end_time']
                    employee_name = slot.get('full_name') or "Свободно"
                    schedule_text += f"  {start_time}-{end_time}: {employee_name}\n"
                
                await query.edit_message_text(schedule_text)
                return ConversationHandler.END
        
        return WAITING_DATE_RANGE
    
    async def admin_schedule_period_start_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle start date selection for custom period"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_start_"):
            start_date = query.data.replace("period_start_", "")
            context.user_data['period_start'] = start_date
            
            keyboard = get_period_end_date_keyboard(start_date)
            await query.edit_message_text(
                f"Начальная дата: {start_date}\nВыберите конечную дату:",
                reply_markup=keyboard
            )
            return WAITING_PERIOD_END
        
        return WAITING_PERIOD_START
    
    async def admin_schedule_period_end_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle end date selection for custom period"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_end_"):
            end_date = query.data.replace("period_end_", "")
            start_date = context.user_data.get('period_start')
            
            if not start_date:
                await query.edit_message_text("Ошибка: начальная дата не найдена.")
                return ConversationHandler.END
            
            employee_id = context.user_data.get('schedule_employee')
            slots = await self.db.get_schedule_slots_by_range(start_date, end_date, employee_id)
            
            if not slots:
                await query.edit_message_text("Нет слотов в этом периоде.")
                return ConversationHandler.END
            
            schedule_text = "Расписание:\n\n"
            current_date = None
            for slot in slots:
                slot_date = slot['date']
                if slot_date != current_date:
                    current_date = slot_date
                    schedule_text += f"\n📅 {current_date}:\n"
                
                start_time = slot['start_time']
                end_time = slot['end_time']
                employee_name = slot.get('full_name') or "Свободно"
                schedule_text += f"  {start_time}-{end_time}: {employee_name}\n"
            
            await query.edit_message_text(schedule_text)
            # Clean up
            context.user_data.pop('period_start', None)
            return ConversationHandler.END
        
        return WAITING_PERIOD_END

    async def admin_schedule_date_range(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        # Check if user is trying to use a menu command
        if self.is_menu_command(text):
            # User wants to switch to another menu, end this conversation
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        try:
            start_date, end_date = text.split()
            # Validate dates
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
            
            employee_id = context.user_data.get('schedule_employee')
            slots = await self.db.get_schedule_slots_by_range(start_date, end_date, employee_id)
            
            if not slots:
                await update.message.reply_text("Нет слотов в этом периоде.")
                return ConversationHandler.END
            
            schedule_text = "Расписание:\n\n"
            current_date = None
            for slot in slots:
                slot_date = slot['date']
                if slot_date != current_date:
                    current_date = slot_date
                    schedule_text += f"\n📅 {current_date}:\n"
                
                start_time = slot['start_time']
                end_time = slot['end_time']
                employee_name = slot.get('full_name') or "Свободно"
                schedule_text += f"  {start_time}-{end_time}: {employee_name}\n"
            
            await update.message.reply_text(schedule_text)
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "Неверный формат. Введите даты в формате:\n2025-01-01 2025-01-07"
            )
            return WAITING_DATE_RANGE

    async def admin_edit_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Edit schedule"""
        keyboard = get_schedule_edit_keyboard()
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=keyboard
        )
        return WAITING_EVENT_DATE

    async def admin_add_event(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = get_date_selection_keyboard()
        await query.edit_message_text(
            "Выберите дату события:",
            reply_markup=keyboard
        )
        return WAITING_EVENT_DATE

    async def admin_event_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("date_"):
            date_str = query.data.split("_")[1]
            context.user_data['event_date'] = date_str
            await query.edit_message_text(
                f"Дата: {date_str}\nВведите время начала (формат: ЧЧ:ММ):"
            )
            return WAITING_EVENT_START
        return WAITING_EVENT_DATE

    async def admin_event_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        if re.match(r'^\d{2}:\d{2}$', text):
            context.user_data['event_start'] = text
            await update.message.reply_text("Введите время окончания (формат: ЧЧ:ММ):")
            return WAITING_EVENT_END
        else:
            await update.message.reply_text("Неверный формат. Введите время в формате ЧЧ:ММ:")
            return WAITING_EVENT_START

    async def admin_event_end(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        if re.match(r'^\d{2}:\d{2}$', text):
            event_date = context.user_data.get('event_date')
            event_start = context.user_data.get('event_start')
            
            # Validate times
            try:
                start_time = datetime.strptime(event_start, "%H:%M").time()
                end_time = datetime.strptime(text, "%H:%M").time()
                if end_time <= start_time:
                    await update.message.reply_text("Время окончания должно быть позже времени начала.")
                    return WAITING_EVENT_END
            except ValueError:
                await update.message.reply_text("Неверный формат времени.")
                return WAITING_EVENT_END
            
            context.user_data['event_end'] = text
            
            keyboard = get_yes_no_keyboard("assign")
            await update.message.reply_text(
                "Назначить сотрудника на этот слот?",
                reply_markup=keyboard
            )
            return WAITING_ASSIGN_EMPLOYEE
        else:
            await update.message.reply_text("Неверный формат. Введите время в формате ЧЧ:ММ:")
            return WAITING_EVENT_END

    async def admin_assign_employee_decision(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "assign_yes":
            employees = await self.db.get_all_employees()
            if not employees:
                await query.edit_message_text("Нет сотрудников в базе.")
                return ConversationHandler.END
            
            keyboard = get_employee_selection_keyboard(employees)
            await query.edit_message_text(
                "Выберите сотрудника:",
                reply_markup=keyboard
            )
            return WAITING_ASSIGN_EMPLOYEE
        else:
            # Just create open slot
            event_date = context.user_data.get('event_date')
            event_start = context.user_data.get('event_start')
            event_end = context.user_data.get('event_end')
            
            await self.db.add_schedule_slot(event_date, event_start, event_end, is_open=True)
            await query.edit_message_text("Слот создан и открыт для записи.")
            return ConversationHandler.END

    async def admin_assign_employee(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("emp_"):
            emp_id = int(query.data.split("_")[1])
            event_date = context.user_data.get('event_date')
            event_start = context.user_data.get('event_start')
            event_end = context.user_data.get('event_end')
            
            # Create slot and assign
            slot_id = await self.db.add_schedule_slot(event_date, event_start, event_end, is_open=False)
            try:
                await self.db.assign_shift(slot_id, emp_id)
                await query.edit_message_text(f"Событие создано и назначено сотруднику.")
            except ValueError as e:
                await query.edit_message_text(f"Ошибка: {str(e)}")
            return ConversationHandler.END
        return WAITING_ASSIGN_EMPLOYEE

    async def admin_delete_event(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = get_date_selection_keyboard()
        await query.edit_message_text(
            "Выберите дату для удаления события:",
            reply_markup=keyboard
        )
        return WAITING_DELETE_DATE

    async def admin_delete_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("date_"):
            date_str = query.data.split("_")[1]
            context.user_data['delete_date'] = date_str
            
            slots = await self.db.get_schedule_slots_by_date(date_str)
            if not slots:
                await query.edit_message_text("Нет событий на эту дату.")
                return ConversationHandler.END
            
            keyboard = get_slot_selection_keyboard(slots)
            await query.edit_message_text(
                f"Дата: {date_str}\nВыберите событие для удаления:",
                reply_markup=keyboard
            )
            return WAITING_DELETE_SLOT
        return WAITING_DELETE_DATE

    async def admin_delete_slot_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("slot_"):
            slot_id = int(query.data.split("_")[1])
            
            keyboard = get_yes_no_keyboard("confirm_delete")
            await query.edit_message_text(
                "Подтвердите удаление события:",
                reply_markup=keyboard
            )
            context.user_data['delete_slot_id'] = slot_id
            return WAITING_DELETE_SLOT
        elif query.data == "confirm_delete_yes":
            slot_id = context.user_data.get('delete_slot_id')
            await self.db.delete_schedule_slot(slot_id)
            await query.edit_message_text("Событие удалено.")
            return ConversationHandler.END
        elif query.data == "confirm_delete_no":
            await query.edit_message_text("Удаление отменено.")
            return ConversationHandler.END
        return WAITING_DELETE_SLOT

    async def admin_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Generate report"""
        employees = await self.db.get_all_employees()
        if not employees:
            await update.message.reply_text("Нет сотрудников в базе.")
            return ConversationHandler.END
        
        keyboard = get_employee_selection_keyboard(employees)
        await update.message.reply_text(
            "Выберите сотрудника для отчета:",
            reply_markup=keyboard
        )
        return WAITING_REPORT_EMPLOYEE

    async def admin_report_employee_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("emp_"):
            emp_id = int(query.data.split("_")[1])
            context.user_data['report_employee'] = emp_id
            
            keyboard = get_period_selection_keyboard()
            await query.edit_message_text(
                "Выберите период:",
                reply_markup=keyboard
            )
            return WAITING_REPORT_PERIOD

    async def admin_report_period_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle period selection for report"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_"):
            if query.data == "period_custom":
                keyboard = get_period_start_date_keyboard()
                await query.edit_message_text(
                    "Выберите начальную дату периода:",
                    reply_markup=keyboard
                )
                return WAITING_PERIOD_START
            else:
                # Predefined period
                _, start_date, end_date = query.data.split("_", 2)
                context.user_data['report_start'] = start_date
                context.user_data['report_end'] = end_date
                
                await query.edit_message_text(
                    "Введите ставку за час (например: 500):"
                )
                return WAITING_REPORT_RATE
        
        return WAITING_REPORT_PERIOD
    
    async def admin_report_period_start_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle start date for report custom period"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_start_"):
            start_date = query.data.replace("period_start_", "")
            context.user_data['report_period_start'] = start_date
            
            keyboard = get_period_end_date_keyboard(start_date)
            await query.edit_message_text(
                f"Начальная дата: {start_date}\nВыберите конечную дату:",
                reply_markup=keyboard
            )
            return WAITING_PERIOD_END
        
        return WAITING_PERIOD_START
    
    async def admin_report_period_end_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle end date for report custom period"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_end_"):
            end_date = query.data.replace("period_end_", "")
            start_date = context.user_data.get('report_period_start')
            
            if not start_date:
                await query.edit_message_text("Ошибка: начальная дата не найдена.")
                return ConversationHandler.END
            
            context.user_data['report_start'] = start_date
            context.user_data['report_end'] = end_date
            context.user_data.pop('report_period_start', None)
            
            await query.edit_message_text(
                "Введите ставку за час (например: 500):"
            )
            return WAITING_REPORT_RATE
        
        return WAITING_PERIOD_END
    
    async def admin_report_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fallback for text input (backward compatibility)"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        try:
            start_date, end_date = text.split()
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
            
            context.user_data['report_start'] = start_date
            context.user_data['report_end'] = end_date
            
            await update.message.reply_text(
                "Введите ставку за час (например: 500):"
            )
            return WAITING_REPORT_RATE
            
        except ValueError:
            keyboard = get_period_selection_keyboard()
            await update.message.reply_text(
                "Неверный формат. Используйте кнопки для выбора периода:",
                reply_markup=keyboard
            )
            return WAITING_REPORT_PERIOD

    async def admin_report_rate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        try:
            rate = float(text)
            emp_id = context.user_data.get('report_employee')
            start_date = context.user_data.get('report_start')
            end_date = context.user_data.get('report_end')
            
            salary, shifts = await self.db.calculate_salary(emp_id, start_date, end_date, rate)
            
            report_text = f"Отчет по сотруднику:\n\n"
            report_text += f"Период: {start_date} - {end_date}\n"
            report_text += f"Ставка: {rate} руб/час\n\n"
            report_text += "Смены:\n"
            
            for shift in shifts:
                report_text += f"  {shift['date']} {shift['start_time']}-{shift['end_time']}\n"
            
            report_text += f"\nИтого: {salary:.2f} руб."
            
            await update.message.reply_text(report_text)
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text("Введите число (например: 500):")
            return WAITING_REPORT_RATE

    async def admin_set_shifts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Set shifts"""
        keyboard = get_date_selection_keyboard()
        await update.message.reply_text(
            "Выберите день для постановки смен:",
            reply_markup=keyboard
        )
        return WAITING_SHIFT_DATE

    async def admin_shift_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("date_"):
            date_str = query.data.split("_")[1]
            context.user_data['shift_date'] = date_str
            
            slots = await self.db.get_schedule_slots_by_date(date_str)
            if not slots:
                await query.edit_message_text(
                    f"Нет доступных слотов на дату {date_str}.\n"
                    "Сначала создайте слоты расписания через меню '2. Редактировать расписание' -> 'Добавить событие'"
                )
                return ConversationHandler.END
            
            keyboard = get_slot_selection_keyboard(slots)
            await query.edit_message_text(
                f"Дата: {date_str}\nВыберите слот:",
                reply_markup=keyboard
            )
            return WAITING_SHIFT_SLOT
        return WAITING_SHIFT_DATE

    async def admin_shift_slot_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("slot_"):
            slot_id = int(query.data.split("_")[1])
            context.user_data['shift_slot_id'] = slot_id
            
            # Get available employees
            employees = await self.db.get_available_employees_for_slot(slot_id)
            if not employees:
                await query.edit_message_text("Нет доступных сотрудников для этого слота.")
                return ConversationHandler.END
            
            keyboard = get_employee_selection_keyboard(employees)
            await query.edit_message_text(
                "Выберите сотрудника:",
                reply_markup=keyboard
            )
            return WAITING_SHIFT_EMPLOYEE
        return WAITING_SHIFT_SLOT

    async def admin_shift_employee_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("emp_"):
            emp_id = int(query.data.split("_")[1])
            slot_id = context.user_data.get('shift_slot_id')
            
            try:
                await self.db.assign_shift(slot_id, emp_id)
                await query.edit_message_text("Смена назначена сотруднику.")
            except ValueError as e:
                await query.edit_message_text(f"Ошибка: {str(e)}")
            return ConversationHandler.END
        return WAITING_SHIFT_EMPLOYEE

    # ========== EMPLOYEE HANDLERS ==========
    
    async def employee_salary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Employee: View salary"""
        keyboard = get_period_selection_keyboard()
        await update.message.reply_text(
            "Выберите период:",
            reply_markup=keyboard
        )
        return WAITING_SALARY_PERIOD

    async def employee_salary_period_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle period selection for employee salary"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_"):
            if query.data == "period_custom":
                keyboard = get_period_start_date_keyboard()
                await query.edit_message_text(
                    "Выберите начальную дату периода:",
                    reply_markup=keyboard
                )
                return WAITING_PERIOD_START
            else:
                # Predefined period
                _, start_date, end_date = query.data.split("_", 2)
                # For employees, use default rate of 500
                rate = 500.0
                user_id = update.effective_user.id
                
                salary, shifts = await self.db.calculate_salary(user_id, start_date, end_date, rate)
                
                salary_text = f"Ваша зарплата за период {start_date} - {end_date}:\n\n"
                salary_text += f"Ставка: {rate} руб/час\n\n"
                salary_text += "Смены:\n"
                for shift in shifts:
                    salary_text += f"  {shift['date']} {shift['start_time']}-{shift['end_time']}\n"
                salary_text += f"\nИтого: {salary:.2f} руб."
                
                await query.edit_message_text(salary_text)
                return ConversationHandler.END
        
        return WAITING_SALARY_PERIOD
    
    async def employee_salary_period_start_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle start date for salary custom period"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_start_"):
            start_date = query.data.replace("period_start_", "")
            context.user_data['salary_period_start'] = start_date
            
            keyboard = get_period_end_date_keyboard(start_date)
            await query.edit_message_text(
                f"Начальная дата: {start_date}\nВыберите конечную дату:",
                reply_markup=keyboard
            )
            return WAITING_PERIOD_END
        
        return WAITING_PERIOD_START
    
    async def employee_salary_period_end_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle end date for salary custom period"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("period_end_"):
            end_date = query.data.replace("period_end_", "")
            start_date = context.user_data.get('salary_period_start')
            
            if not start_date:
                await query.edit_message_text("Ошибка: начальная дата не найдена.")
                return ConversationHandler.END
            
            # For employees, use default rate of 500
            rate = 500.0
            user_id = update.effective_user.id
            
            salary, shifts = await self.db.calculate_salary(user_id, start_date, end_date, rate)
            
            salary_text = f"Ваша зарплата за период {start_date} - {end_date}:\n\n"
            salary_text += f"Ставка: {rate} руб/час\n\n"
            salary_text += "Смены:\n"
            for shift in shifts:
                salary_text += f"  {shift['date']} {shift['start_time']}-{shift['end_time']}\n"
            salary_text += f"\nИтого: {salary:.2f} руб."
            
            await query.edit_message_text(salary_text)
            context.user_data.pop('salary_period_start', None)
            return ConversationHandler.END
        
        return WAITING_PERIOD_END
    
    async def employee_salary_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Fallback for text input (backward compatibility)"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        try:
            start_date, end_date = text.split()
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
            
            # For employees, use default rate of 500
            rate = 500.0
            user_id = update.effective_user.id
            
            salary, shifts = await self.db.calculate_salary(user_id, start_date, end_date, rate)
            
            salary_text = f"Ваша зарплата за период {start_date} - {end_date}:\n\n"
            salary_text += f"Ставка: {rate} руб/час\n\n"
            salary_text += "Смены:\n"
            for shift in shifts:
                salary_text += f"  {shift['date']} {shift['start_time']}-{shift['end_time']}\n"
            salary_text += f"\nИтого: {salary:.2f} руб."
            
            await update.message.reply_text(salary_text)
            return ConversationHandler.END
            
        except ValueError:
            keyboard = get_period_selection_keyboard()
            await update.message.reply_text(
                "Неверный формат. Используйте кнопки для выбора периода:",
                reply_markup=keyboard
            )
            return WAITING_SALARY_PERIOD

    async def employee_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Employee: View schedule"""
        keyboard = get_date_selection_keyboard()
        await update.message.reply_text(
            "Выберите дату или введите диапазон дат:",
            reply_markup=keyboard
        )

    async def employee_schedule_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("date_"):
            date_str = query.data.split("_")[1]
            user_id = update.effective_user.id
            
            slots = await self.db.get_schedule_slots_by_range(date_str, date_str, user_id)
            
            if not slots:
                await query.edit_message_text("Нет смен на эту дату.")
                return ConversationHandler.END
            
            schedule_text = f"Ваше расписание на {date_str}:\n\n"
            for slot in slots:
                if slot.get('employee_id') == user_id:  # If assigned to this employee
                    schedule_text += f"  {slot['start_time']}-{slot['end_time']}\n"
            
            await query.edit_message_text(schedule_text)
            return ConversationHandler.END
        return WAITING_SCHEDULE_DATE

    async def employee_schedule_range(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input for date range"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        try:
            start_date, end_date = text.split()
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
            
            user_id = update.effective_user.id
            slots = await self.db.get_schedule_slots_by_range(start_date, end_date, user_id)
            
            if not slots:
                await update.message.reply_text("Нет смен в этом периоде.")
                return ConversationHandler.END
            
            schedule_text = f"Ваше расписание на период {start_date} - {end_date}:\n\n"
            current_date = None
            for slot in slots:
                if slot.get('employee_id') == user_id:  # If assigned to this employee
                    slot_date = slot['date']
                    if slot_date != current_date:
                        current_date = slot_date
                        schedule_text += f"\n📅 {current_date}:\n"
                    schedule_text += f"  {slot['start_time']}-{slot['end_time']}\n"
            
            await update.message.reply_text(schedule_text)
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "Неверный формат. Введите даты в формате:\n2025-01-01 2025-01-07"
            )
            return WAITING_SCHEDULE_DATE_RANGE

    async def employee_free_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Employee: Set free time"""
        keyboard = get_date_selection_keyboard()
        await update.message.reply_text(
            "Выберите день для выставления свободного времени:",
            reply_markup=keyboard
        )

    async def employee_free_time_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("date_"):
            date_str = query.data.split("_")[1]
            context.user_data['free_time_date'] = date_str
            
            await query.edit_message_text(
                f"Дата: {date_str}\n"
                "Введите слоты в формате:\n"
                "ЧЧ:ММ ЧЧ:ММ\n"
                "ЧЧ:ММ ЧЧ:ММ\n"
                "(можно несколько слотов, каждый с новой строки)"
            )
            return WAITING_FREE_TIME_SLOTS
        return WAITING_FREE_TIME_DATE

    async def employee_free_time_slots(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        lines = text.split('\n')
        user_id = update.effective_user.id
        date_str = context.user_data.get('free_time_date')
        
        slots_added = []
        errors = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                start_time, end_time = line.split()
                if not re.match(r'^\d{2}:\d{2}$', start_time) or not re.match(r'^\d{2}:\d{2}$', end_time):
                    errors.append(f"Неверный формат: {line}")
                    continue
                
                # Validate times
                start = datetime.strptime(start_time, "%H:%M").time()
                end = datetime.strptime(end_time, "%H:%M").time()
                if end <= start:
                    errors.append(f"Неверное время: {line}")
                    continue
                
                await self.db.add_free_time_slot(user_id, date_str, start_time, end_time)
                slots_added.append(f"{start_time}-{end_time}")
            except ValueError:
                errors.append(f"Неверный формат: {line}")
        
        response = f"Свободное время на {date_str}:\n\n"
        for slot in slots_added:
            response += f"  {slot}\n"
        
        if errors:
            response += "\nОшибки:\n"
            for error in errors:
                response += f"  {error}\n"
        
        await update.message.reply_text(response)
        return ConversationHandler.END

    # ========== WORKER MANAGEMENT HANDLERS ==========
    
    async def admin_worker_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Worker management menu"""
        keyboard = get_worker_management_keyboard()
        await update.message.reply_text(
            "Управление сотрудниками:",
            reply_markup=keyboard
        )
        return WAITING_WORKER_MENU

    async def admin_add_worker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Add worker"""
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "Введите Telegram username сотрудника для добавления:\n"
            "(Например: @username)\n\n"
            "Если username скрыт от ботов, попросите сотрудника:\n"
            "1. Написать боту любое сообщение (/start)\n"
            "2. Или предоставить свой User ID (можно получить через @userinfobot)\n"
            "3. Затем используйте формат: id:123456789"
        )
        return WAITING_WORKER_USER_ID

    async def admin_add_worker_user_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle worker username input"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        try:
            # Check if it's a User ID (format: id:123456789)
            if text.lower().startswith('id:'):
                try:
                    user_id = int(text[3:].strip())
                    # Try to get user info from Telegram
                    try:
                        chat = await context.bot.get_chat(user_id)
                        username = chat.username
                        first_name = chat.first_name or ""
                        last_name = chat.last_name or ""
                        full_name = (first_name + " " + last_name).strip() if last_name else first_name.strip()
                        if not full_name:
                            full_name = None
                    except Exception as e:
                        # If we can't get info, use defaults
                        username = None
                        full_name = None
                        import logging
                        logging.warning(f"Could not get user info for {user_id}: {e}")
                except ValueError:
                    await update.message.reply_text(
                        "Неверный формат User ID. Используйте формат: id:123456789\n"
                        "Или введите username (например: @username):"
                    )
                    return WAITING_WORKER_USER_ID
            # Check if it's a username (must start with @)
            elif text.startswith('@'):
                username = text[1:]  # Remove @
                
                try:
                    # Try to get user by username
                    chat = await context.bot.get_chat(f"@{username}")
                    user_id = chat.id
                    full_name = chat.first_name or ""
                    if chat.last_name:
                        full_name += f" {chat.last_name}"
                    full_name = full_name.strip() if full_name else None
                    username = chat.username  # Get actual username from chat
                except Exception as e:
                    await update.message.reply_text(
                        f"❌ Не удалось найти пользователя @{username}.\n\n"
                        f"Возможные причины:\n"
                        f"• Username скрыт от ботов (настройки приватности)\n"
                        f"• Пользователь не существует\n"
                        f"• Бот не может видеть пользователя\n\n"
                        f"💡 Решение:\n"
                        f"1. Попросите сотрудника написать боту /start\n"
                        f"2. Или используйте User ID: id:123456789\n"
                        f"   (User ID можно получить через @userinfobot)\n\n"
                        f"Введите username или id:"
                    )
                    return WAITING_WORKER_USER_ID
            else:
                await update.message.reply_text(
                    "Неверный формат. Используйте:\n"
                    "• Username: @username\n"
                    "• Или User ID: id:123456789\n\n"
                    "Введите username или id:"
                )
                return WAITING_WORKER_USER_ID
            
            # Check if user already exists
            existing_user = await self.db.get_user_by_id(user_id)
            if existing_user:
                if existing_user.get('is_admin'):
                    await update.message.reply_text(
                        f"Пользователь уже существует и является администратором.\n"
                        f"ID: {user_id}\n"
                        f"Имя: {existing_user.get('full_name') or 'Не указано'}\n"
                        f"Для снятия статуса администратора используйте меню управления сотрудниками."
                    )
                    return ConversationHandler.END
                else:
                    # User exists as employee
                    # If we don't have a name, ask for it
                    if full_name is None or (isinstance(full_name, str) and not full_name.strip()):
                        context.user_data['new_worker_id'] = user_id
                        context.user_data['new_worker_username'] = username
                        display_username = f"@{username}" if username else f"ID: {user_id}"
                        await update.message.reply_text(
                            f"Пользователь уже существует:\n"
                            f"{display_username}\n"
                            f"\nВведите имя для сотрудника:"
                        )
                        return WAITING_WORKER_NAME
                    # Update info with new name
                    await self.db.add_user(user_id, username, full_name, is_admin=False)
                    display_username = f"@{username}" if username else f"ID: {user_id}"
                    await update.message.reply_text(
                        f"✅ Информация о сотруднике обновлена:\n"
                        f"{display_username}\n"
                        f"Имя: {full_name}"
                    )
                    return ConversationHandler.END
            
            # Store user info in context for potential name input
            context.user_data['new_worker_id'] = user_id
            context.user_data['new_worker_username'] = username
            
            # If we don't have a name (couldn't get from Telegram or name is empty), ask for it
            if full_name is None or (isinstance(full_name, str) and not full_name.strip()):
                display_username = f"@{username}" if username else f"ID: {user_id}"
                await update.message.reply_text(
                    f"Пользователь найден:\n"
                    f"{display_username}\n"
                    f"\nВведите имя для сотрудника:"
                )
                return WAITING_WORKER_NAME
            
            # We have a name, add user immediately
            await self.db.add_user(user_id, username, full_name, is_admin=False)
            
            display_username = f"@{username}" if username else f"ID: {user_id}"
            await update.message.reply_text(
                f"✅ Сотрудник добавлен:\n"
                f"{display_username}\n"
                f"Имя: {full_name}"
            )
            return ConversationHandler.END
            
        except Exception as e:
            import logging
            logging.error(f"Error adding worker: {e}", exc_info=True)
            await update.message.reply_text(
                f"Ошибка при добавлении сотрудника: {str(e)}\n"
                "Попробуйте еще раз или используйте /start для перезапуска."
            )
            return ConversationHandler.END
    
    async def admin_add_worker_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle worker name input after adding by ID"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        user_id = context.user_data.get('new_worker_id')
        username = context.user_data.get('new_worker_username')
        full_name = text
        
        if not user_id:
            await update.message.reply_text("Ошибка: данные пользователя не найдены. Попробуйте добавить сотрудника заново.")
            return ConversationHandler.END
        
        if not full_name or len(full_name.strip()) == 0:
            await update.message.reply_text("Имя не может быть пустым. Введите имя сотрудника:")
            return WAITING_WORKER_NAME
        
        # Add user with provided name
        await self.db.add_user(user_id, username, full_name, is_admin=False)
        
        display_username = f"@{username}" if username else f"ID: {user_id}"
        await update.message.reply_text(
            f"✅ Сотрудник добавлен:\n"
            f"{display_username}\n"
            f"Имя: {full_name}"
        )
        
        # Clean up context
        context.user_data.pop('new_worker_id', None)
        context.user_data.pop('new_worker_username', None)
        
        return ConversationHandler.END

    async def admin_remove_worker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Remove worker"""
        query = update.callback_query
        await query.answer()
        
        employees = await self.db.get_all_employees()
        if not employees:
            keyboard = get_worker_management_keyboard()
            await query.edit_message_text("Нет сотрудников для удаления.", reply_markup=keyboard)
            return WAITING_WORKER_MENU
        
        keyboard = get_employee_selection_keyboard(employees)
        await query.edit_message_text(
            "Выберите сотрудника для удаления:",
            reply_markup=keyboard
        )
        return WAITING_WORKER_MENU

    async def admin_remove_worker_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle worker removal"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("emp_"):
            emp_id = int(query.data.split("_")[1])
            
            try:
                user = await self.db.get_user_by_id(emp_id)
                if not user:
                    keyboard = get_worker_management_keyboard()
                    await query.edit_message_text("Сотрудник не найден.", reply_markup=keyboard)
                    return WAITING_WORKER_MENU
                
                keyboard = get_yes_no_keyboard("confirm_remove")
                context.user_data['remove_worker_id'] = emp_id
                await query.edit_message_text(
                    f"Подтвердите удаление сотрудника:\n"
                    f"ID: {emp_id}\n"
                    f"Имя: {user.get('full_name') or 'Не указано'}\n"
                    f"Username: @{user.get('username') or 'не указан'}",
                    reply_markup=keyboard
                )
                return WAITING_WORKER_MENU
            except Exception as e:
                keyboard = get_worker_management_keyboard()
                await query.edit_message_text(f"Ошибка: {str(e)}", reply_markup=keyboard)
                return WAITING_WORKER_MENU
        return WAITING_WORKER_MENU

    async def admin_confirm_remove_worker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm worker removal"""
        query = update.callback_query
        await query.answer()
        
        keyboard = get_worker_management_keyboard()
        if query.data == "confirm_remove_yes":
            emp_id = context.user_data.get('remove_worker_id')
            try:
                await self.db.remove_user(emp_id)
                await query.edit_message_text("Сотрудник удален.", reply_markup=keyboard)
            except ValueError as e:
                await query.edit_message_text(f"Ошибка: {str(e)}", reply_markup=keyboard)
            except Exception as e:
                await query.edit_message_text(f"Ошибка при удалении: {str(e)}", reply_markup=keyboard)
            return WAITING_WORKER_MENU
        else:
            await query.edit_message_text("Удаление отменено.", reply_markup=keyboard)
            return WAITING_WORKER_MENU

    async def admin_list_workers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: List all workers"""
        query = update.callback_query
        await query.answer()
        
        users = await self.db.get_all_users()
        if not users:
            await query.edit_message_text("Нет сотрудников в базе.")
            return WAITING_WORKER_MENU
        
        text = "Список всех пользователей:\n\n"
        for user in users:
            role = "Админ" if user['is_admin'] else "Сотрудник"
            user_id = user['user_id']
            full_name = user.get('full_name') or f'User {user_id}'
            text += f"• {full_name}\n"
            text += f"  ID: {user_id}\n"
            if user.get('username'):
                text += f"  @{user['username']}\n"
            text += f"  Роль: {role}\n\n"
        
        keyboard = get_worker_management_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard)
        return WAITING_WORKER_MENU

    async def admin_make_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Make user admin"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "Введите Telegram User ID пользователя для назначения администратором:\n"
            "(Можно получить через @userinfobot)"
        )
        return WAITING_ADMIN_USER_ID

    async def admin_make_admin_user_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin user ID input"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        try:
            user_id = int(text)
            
            # Check if user exists, if not add them
            user = await self.db.get_user_by_id(user_id)
            if not user:
                # Try to get user info from Telegram
                try:
                    chat_member = await context.bot.get_chat(user_id)
                    username = chat_member.username
                    full_name = chat_member.first_name
                    if chat_member.last_name:
                        full_name += f" {chat_member.last_name}"
                except Exception:
                    username = None
                    full_name = f"User {user_id}"
                
                await self.db.add_user(user_id, username, full_name, is_admin=True)
            else:
                await self.db.set_admin_status(user_id, True)
            
            await update.message.reply_text(
                f"Пользователь назначен администратором:\n"
                f"ID: {user_id}"
            )
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "Неверный формат. Введите числовой User ID:"
            )
            return WAITING_ADMIN_USER_ID
        except Exception as e:
            await update.message.reply_text(
                f"Ошибка: {str(e)}"
            )
            return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Операция отменена.")
        return ConversationHandler.END
    
    async def handle_menu_command_in_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu commands that interrupt a conversation"""
        # Just end the conversation silently - the menu command will be handled by its entry point handler
        # This prevents the "Операция отменена" message from appearing
        return ConversationHandler.END

