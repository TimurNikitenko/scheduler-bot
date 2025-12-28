from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.error import BadRequest
from datetime import datetime, timedelta
from typing import Dict
import re
from .database import Database
from .keyboards import (
    get_main_keyboard, get_employee_selection_keyboard, get_schedule_edit_keyboard,
    get_date_selection_keyboard, get_slot_selection_keyboard, get_yes_no_keyboard,
    get_cancel_keyboard, get_worker_management_keyboard,
    get_period_selection_keyboard, get_period_start_date_keyboard, get_period_end_date_keyboard,
    get_back_keyboard, get_employees_count_keyboard, get_free_time_slots_keyboard
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
    WAITING_PERIOD_START, WAITING_PERIOD_END,
    WAITING_EVENT_ADDRESS, WAITING_EMPLOYEE_SLOT_SELECTION,
    WAITING_FREE_TIME_EMPLOYEE, WAITING_EVENT_EMPLOYEES_COUNT,
    WAITING_FREE_TIME_DELETE_DATE, WAITING_FREE_TIME_DELETE_SLOT,
    WAITING_EDIT_NAME_EMPLOYEE, WAITING_EDIT_NAME_INPUT
) = range(32)


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
            "4. Поставить смены", "5. Управление сотрудниками", "6. Сотрудник свободен в",
            "1. Моя зарплата", "2. Мое расписание", "3. Доступные слоты", 
            "4. Указать свободное время", "3. Выставить свободное время"
        ]
        return text.strip() in menu_commands

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        import logging
        logger = logging.getLogger(__name__)
        
        user = update.effective_user
        user_id = user.id
        is_admin = await self.is_admin(user_id)
        
        logger.info(f"Start command from user {user_id}, is_admin: {is_admin}")
        
        # Check if user is already in database
        existing_user = await self.db.get_user_by_id(user_id)
        is_new_user = existing_user is None
        
        try:
            await self.db.add_user(user_id, user.username, user.full_name, is_admin)
        except Exception as e:
            logger.error(f"Error adding user to database: {e}")
        
        try:
            keyboard = get_main_keyboard(is_admin)
            logger.info(f"Keyboard created: {keyboard}, buttons: {keyboard.keyboard if hasattr(keyboard, 'keyboard') else 'N/A'}")
        except Exception as e:
            logger.error(f"Error creating keyboard: {e}", exc_info=True)
            # Send message without keyboard if keyboard creation fails
            await update.message.reply_text(
                f"Привет, {user.first_name}! Произошла ошибка при создании клавиатуры. Попробуйте еще раз."
            )
            return
        
        try:
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
            logger.info(f"Sent keyboard to user {user_id}, is_admin: {is_admin}")
        except Exception as e:
            logger.error(f"Error sending message with keyboard: {e}", exc_info=True)
            # Try to send message without keyboard
            try:
                await update.message.reply_text(
                    f"Привет, {user.first_name}! Произошла ошибка при отправке клавиатуры."
                )
            except Exception as e2:
                logger.error(f"Error sending fallback message: {e2}", exc_info=True)

    # ========== ADMIN HANDLERS ==========
    
    async def admin_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: View schedule"""
        try:
            # Always show all slots (no employee selection)
            context.user_data['schedule_employee'] = None
            keyboard = get_period_selection_keyboard(show_back=False)
            await update.message.reply_text(
                "Выберите период для просмотра расписания:",
                reply_markup=keyboard
            )
            return WAITING_DATE_RANGE
        except Exception as e:
            import logging
            logging.error(f"Error in admin_schedule: {e}", exc_info=True)
            try:
                await update.message.reply_text(
                    f"Произошла ошибка: {str(e)}\n"
                    "Попробуйте еще раз или используйте /start для перезапуска."
                )
            except:
                pass
            return ConversationHandler.END


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
                employee_id = None  # Always show all slots
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
                    required = slot.get('required_employees', 1)
                    schedule_text += f"  {start_time}-{end_time}: {employee_name}"
                    if slot.get('address'):
                        schedule_text += f"\n    📍 {slot['address']}"
                    schedule_text += f"\n    👥 Нужно: {required} чел.\n"
                
                await query.edit_message_text(schedule_text)
                return ConversationHandler.END
        
        return WAITING_DATE_RANGE
    
    async def admin_schedule_period_start_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle start date selection for custom period"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to period selection
            keyboard = get_period_selection_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите период для просмотра расписания:",
                reply_markup=keyboard
            )
            return WAITING_DATE_RANGE
        
        if query.data.startswith("period_start_"):
            start_date = query.data.replace("period_start_", "")
            context.user_data['period_start'] = start_date
            
            keyboard = get_period_end_date_keyboard(start_date, show_back=True)
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
            
            employee_id = None  # Always show all slots
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
                required = slot.get('required_employees', 1)
                schedule_text += f"  {start_time}-{end_time}: {employee_name}"
                if slot.get('address'):
                    schedule_text += f"\n    📍 {slot['address']}"
                schedule_text += f"\n    👥 Нужно: {required} чел.\n"
            
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
        keyboard = get_schedule_edit_keyboard(show_back=True)
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=keyboard
        )
        return WAITING_EVENT_DATE

    async def admin_add_event(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = get_date_selection_keyboard(show_back=True)
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
            keyboard = get_back_keyboard()
            await query.edit_message_text(
                f"Дата: {date_str}\nВведите время начала (формат: ЧЧ:ММ):",
                reply_markup=keyboard
            )
            return WAITING_EVENT_START
        elif query.data == "back":
            # Go back to event menu
            keyboard = get_schedule_edit_keyboard(show_back=True)
            try:
                await query.edit_message_text(
                    "Выберите действие:",
                    reply_markup=keyboard
                )
            except BadRequest:
                await query.message.reply_text(
                    "Выберите действие:",
                    reply_markup=keyboard
                )
            return WAITING_EVENT_DATE
        return WAITING_EVENT_DATE

    async def admin_event_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        if re.match(r'^\d{2}:\d{2}$', text):
            context.user_data['event_start'] = text
            keyboard = get_back_keyboard()
            await update.message.reply_text(
                "Введите время окончания (формат: ЧЧ:ММ):",
                reply_markup=keyboard
            )
            return WAITING_EVENT_END
        else:
            keyboard = get_back_keyboard()
            await update.message.reply_text(
                "Неверный формат. Введите время в формате ЧЧ:ММ:",
                reply_markup=keyboard
            )
            return WAITING_EVENT_START
    
    async def admin_event_start_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button from event end to event start"""
        query = update.callback_query
        await query.answer()
        
        date_str = context.user_data.get('event_date', '')
        keyboard = get_back_keyboard()
        await query.edit_message_text(
            f"Дата: {date_str}\nВведите время начала (формат: ЧЧ:ММ):",
            reply_markup=keyboard
        )
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
            
            # Check if any employees have free time at this time
            event_date = context.user_data.get('event_date')
            event_start = context.user_data.get('event_start')
            employees_with_free_time = await self.db.get_employees_with_free_time(event_date, event_start, text)
            
            if employees_with_free_time:
                # Store employees for later use
                context.user_data['employees_with_free_time'] = employees_with_free_time
                
                text_msg = f"✅ Время: {event_start}-{text}\n\n"
                text_msg += "💡 Сотрудники со свободным временем на это время:\n\n"
                for emp in employees_with_free_time:
                    emp_name = emp.get('full_name') or emp.get('username') or f"ID: {emp['user_id']}"
                    free_start = emp.get('free_start')
                    free_end = emp.get('free_end')
                    text_msg += f"• {emp_name}\n"
                    if free_start and free_end:
                        text_msg += f"  Свободен: {free_start}-{free_end}\n"
                text_msg += "\nВы сможете назначить их после создания события.\n\n"
                text_msg += "Введите адрес работы (улица, дом):\n"
                text_msg += "Например: ул. Геолокации, д. 4"
                
                keyboard = get_back_keyboard()
                await update.message.reply_text(text_msg, reply_markup=keyboard)
            else:
                keyboard = get_back_keyboard()
                await update.message.reply_text(
                    "Введите адрес работы (улица, дом):\n"
                    "Например: ул. Геолокации, д. 4",
                    reply_markup=keyboard
                )
            return WAITING_EVENT_ADDRESS
        else:
            await update.message.reply_text("Неверный формат. Введите время в формате ЧЧ:ММ:")
            return WAITING_EVENT_END

    async def admin_event_address(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle address input"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        # Check for back button
        if text == "◀️ Назад" or text.lower() == "назад":
            keyboard = get_back_keyboard()
            await update.message.reply_text(
                "Введите время окончания (формат: ЧЧ:ММ):",
                reply_markup=keyboard
            )
            return WAITING_EVENT_END
        
        context.user_data['event_address'] = text
        
        # Ask for employees count
        keyboard = get_employees_count_keyboard(show_back=True)
        await update.message.reply_text(
            f"Адрес: {text}\n\n"
            "Сколько человек нужно для этого события?",
            reply_markup=keyboard
        )
        return WAITING_EVENT_EMPLOYEES_COUNT
    
    async def admin_event_address_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button from employees count to address input"""
        query = update.callback_query
        await query.answer()
        
        keyboard = get_back_keyboard()
        await query.edit_message_text(
            "Введите адрес работы (улица, дом):\n"
            "Например: ул. Геолокации, д. 4",
            reply_markup=keyboard
        )
        return WAITING_EVENT_ADDRESS
    
    async def admin_event_employees_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle employees count selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("count_"):
            count = int(query.data.split("_")[1])
            context.user_data['event_employees_count'] = count
            
            # Create slot with all info
            await self._create_slot_from_context(context, query)
            return WAITING_ASSIGN_EMPLOYEE
        elif query.data == "back":
            # Go back to address input
            keyboard = get_back_keyboard()
            await query.edit_message_text(
                "Введите адрес работы (улица, дом):\n"
                "Например: ул. Геолокации, д. 4",
                reply_markup=keyboard
            )
            return WAITING_EVENT_ADDRESS
        
        return WAITING_EVENT_EMPLOYEES_COUNT
    
    async def _create_slot_from_context(self, context: Dict, message_or_query):
        """Helper to create slot from context and ask about assignment"""
        event_date = context.user_data.get('event_date')
        event_start = context.user_data.get('event_start')
        event_end = context.user_data.get('event_end')
        address = context.user_data.get('event_address')
        required_employees = context.user_data.get('event_employees_count', 1)
        
        # Create slot (will be assigned later if needed)
        slot_id = await self.db.add_schedule_slot(
            event_date, event_start, event_end,
            address=address,
            location_latitude=None,
            location_longitude=None,
            required_employees=required_employees,
            is_open=True
        )
        context.user_data['created_slot_id'] = slot_id
        
        keyboard = get_yes_no_keyboard("assign")
        text = f"✅ Слот создан:\n"
        text += f"Дата: {event_date}\n"
        text += f"Время: {event_start}-{event_end}\n"
        text += f"Адрес: {address}\n"
        text += f"Нужно человек: {required_employees}\n"
        text += f"\nНазначить сотрудника сейчас?"
        
        if hasattr(message_or_query, 'edit_message_text'):
            await message_or_query.edit_message_text(text, reply_markup=keyboard)
        else:
            await message_or_query.reply_text(text, reply_markup=keyboard)
    
    async def admin_assign_employee_decision(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to slot selection or event creation
            slot_id = context.user_data.get('created_slot_id')
            if slot_id:
                # Go back to event creation summary
                date_str = context.user_data.get('event_date', '')
                keyboard = get_yes_no_keyboard("assign", show_back=True)
                await query.edit_message_text(
                    f"Событие создано!\n\n"
                    f"Дата: {date_str}\n"
                    f"Время: {context.user_data.get('event_start', '')} - {context.user_data.get('event_end', '')}\n"
                    f"Адрес: {context.user_data.get('event_address', '')}\n\n"
                    f"Назначить сотрудника на это событие?",
                    reply_markup=keyboard
                )
                return WAITING_ASSIGN_EMPLOYEE
            else:
                return ConversationHandler.END
        
        if query.data == "assign_yes":
            try:
                # First check if we have employees with free time for this slot
                employees_with_free_time = context.user_data.get('employees_with_free_time', [])
                
                if employees_with_free_time:
                    # Show employees with free time first
                    text = "💡 Сотрудники со свободным временем на это время:\n\n"
                    for emp in employees_with_free_time:
                        emp_name = emp.get('full_name') or emp.get('username') or f"ID: {emp['user_id']}"
                        free_start = emp.get('free_start')
                        free_end = emp.get('free_end')
                        text += f"• {emp_name}"
                        if free_start and free_end:
                            text += f" (свободен: {free_start}-{free_end})"
                        text += "\n"
                    text += "\nИли выберите другого сотрудника:"
                    
                    # Create keyboard with employees with free time at the top
                    emp_ids_with_free_time = [emp['user_id'] for emp in employees_with_free_time]
                    all_employees = await self.db.get_all_employees()
                    
                    # all_employees returns List[Tuple[int, str]] - (user_id, display_name)
                    # Separate employees with free time and others
                    employees_with_ft = [e for e in all_employees if e[0] in emp_ids_with_free_time]
                    other_employees = [e for e in all_employees if e[0] not in emp_ids_with_free_time]
                    
                    # Combine: first those with free time, then others
                    all_employees_list = employees_with_ft + other_employees
                    
                    if not all_employees_list:
                        await query.edit_message_text(
                            "Нет сотрудников в базе.\n"
                            "Добавьте сотрудников через меню '5. Управление сотрудниками' -> 'Добавить сотрудника'"
                        )
                        return ConversationHandler.END
                    
                    keyboard = get_employee_selection_keyboard(all_employees_list)
                    await query.edit_message_text(text, reply_markup=keyboard)
                else:
                    # No employees with free time, show all employees
                    employees = await self.db.get_all_employees()
                    if not employees:
                        # Try to get all users to debug
                        all_users = await self.db.get_all_users()
                        import logging
                        logging.warning(f"No employees found, but total users: {len(all_users)}")
                        for user in all_users:
                            logging.warning(f"User: {user['user_id']}, is_admin: {user.get('is_admin')}")
                        
                        await query.edit_message_text(
                            "Нет сотрудников в базе.\n"
                            "Добавьте сотрудников через меню '5. Управление сотрудниками' -> 'Добавить сотрудника'"
                        )
                        return ConversationHandler.END
                    
                    keyboard = get_employee_selection_keyboard(employees)
                    await query.edit_message_text(
                        "Выберите сотрудника:",
                        reply_markup=keyboard
                    )
                return WAITING_ASSIGN_EMPLOYEE
            except Exception as e:
                import logging
                logging.error(f"Error in admin_assign_employee_decision: {e}", exc_info=True)
                await query.edit_message_text(
                    f"Ошибка при получении списка сотрудников: {str(e)}\n"
                    "Попробуйте еще раз."
                )
                return ConversationHandler.END
        else:
            # Slot created, open for employees to sign up
            await query.edit_message_text("✅ Слот создан и открыт для записи сотрудников.")
            # Clean up context
            for key in ['event_date', 'event_start', 'event_end', 'event_address', 'created_slot_id']:
                context.user_data.pop(key, None)
            return ConversationHandler.END

    async def admin_assign_employee(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to employee selection - show decision again
            slot_id = context.user_data.get('created_slot_id')
            if slot_id:
                date_str = context.user_data.get('event_date', '')
                keyboard = get_yes_no_keyboard("assign", show_back=True)
                await query.edit_message_text(
                    f"Событие создано!\n\n"
                    f"Дата: {date_str}\n"
                    f"Время: {context.user_data.get('event_start', '')} - {context.user_data.get('event_end', '')}\n"
                    f"Адрес: {context.user_data.get('event_address', '')}\n\n"
                    f"Назначить сотрудника на это событие?",
                    reply_markup=keyboard
                )
                return WAITING_ASSIGN_EMPLOYEE
            else:
                return ConversationHandler.END
        
        if query.data.startswith("emp_"):
            emp_id = int(query.data.split("_")[1])
            slot_id = context.user_data.get('created_slot_id')
            
            if not slot_id:
                await query.edit_message_text("Ошибка: слот не найден.")
                return ConversationHandler.END
            
            try:
                await self.db.assign_shift(slot_id, emp_id)
                # Slot will be closed automatically in assign_shift() if fully booked
                
                employee_name = await self.db.get_user_display_name(emp_id)
                await query.edit_message_text(
                    f"✅ Слот назначен сотруднику: {employee_name}"
                )
            except ValueError as e:
                await query.edit_message_text(f"Ошибка: {str(e)}")
            except Exception as e:
                import logging
                logging.error(f"Error assigning employee: {e}", exc_info=True)
                await query.edit_message_text(f"Ошибка при назначении: {str(e)}")
            
            # Clean up context
            for key in ['event_date', 'event_start', 'event_end', 'event_address', 'created_slot_id']:
                context.user_data.pop(key, None)
            return ConversationHandler.END
        return WAITING_ASSIGN_EMPLOYEE

    async def admin_delete_event(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        keyboard = get_date_selection_keyboard(show_back=True)
        await query.edit_message_text(
            "Выберите дату для удаления события:",
            reply_markup=keyboard
        )
        return WAITING_DELETE_DATE

    async def admin_delete_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to event menu
            keyboard = get_schedule_edit_keyboard()
            await query.edit_message_text(
                "Выберите действие:",
                reply_markup=keyboard
            )
            return WAITING_EVENT_DATE
        
        if query.data.startswith("date_"):
            date_str = query.data.split("_")[1]
            context.user_data['delete_date'] = date_str
            
            slots = await self.db.get_schedule_slots_by_date(date_str)
            if not slots:
                await query.edit_message_text("Нет событий на эту дату.")
                return ConversationHandler.END
            
            keyboard = get_slot_selection_keyboard(slots, show_address=True, show_back=True)
            await query.edit_message_text(
                f"Дата: {date_str}\nВыберите событие для удаления:",
                reply_markup=keyboard
            )
            return WAITING_DELETE_SLOT
        return WAITING_DELETE_DATE

    async def admin_delete_slot_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to date selection
            date_str = context.user_data.get('delete_date', '2025-01-01')
            keyboard = get_date_selection_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите дату для удаления события:",
                reply_markup=keyboard
            )
            return WAITING_DELETE_DATE
        
        if query.data.startswith("slot_"):
            slot_id = int(query.data.split("_")[1])
            
            keyboard = get_yes_no_keyboard("confirm_delete", show_back=True)
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
        
        if query.data == "back":
            # Go back to employee selection
            employees = await self.db.get_all_employees()
            keyboard = get_employee_selection_keyboard(employees, show_back=True)
            await query.edit_message_text(
                "Выберите сотрудника для отчета:",
                reply_markup=keyboard
            )
            return WAITING_REPORT_EMPLOYEE
        
        if query.data.startswith("emp_"):
            emp_id = int(query.data.split("_")[1])
            context.user_data['report_employee'] = emp_id
            
            keyboard = get_period_selection_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите период:",
                reply_markup=keyboard
            )
            return WAITING_REPORT_PERIOD
        
        return WAITING_REPORT_EMPLOYEE

    async def admin_report_period_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle period selection for report"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to employee selection
            emp_id = context.user_data.get('report_employee')
            if emp_id:
                employees = await self.db.get_all_employees()
                keyboard = get_employee_selection_keyboard(employees, show_back=True)
                await query.edit_message_text(
                    "Выберите сотрудника для отчета:",
                    reply_markup=keyboard
                )
                return WAITING_REPORT_EMPLOYEE
            else:
                return ConversationHandler.END
        
        if query.data.startswith("period_"):
            if query.data == "period_custom":
                keyboard = get_period_start_date_keyboard(show_back=True)
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
        
        if query.data == "back":
            # Go back to period selection
            keyboard = get_period_selection_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите период:",
                reply_markup=keyboard
            )
            return WAITING_REPORT_PERIOD
        
        if query.data.startswith("period_start_"):
            start_date = query.data.replace("period_start_", "")
            context.user_data['report_period_start'] = start_date
            
            keyboard = get_period_end_date_keyboard(start_date, show_back=True)
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
        
        if query.data == "back":
            # Go back to start date selection
            keyboard = get_period_start_date_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите начальную дату периода:",
                reply_markup=keyboard
            )
            return WAITING_PERIOD_START
        
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
        keyboard = get_date_selection_keyboard(show_back=True)
        await update.message.reply_text(
            "Выберите день для постановки смен:",
            reply_markup=keyboard
        )
        return WAITING_SHIFT_DATE

    async def admin_shift_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to main menu
            return ConversationHandler.END
        
        if query.data.startswith("date_"):
            date_str = query.data.split("_")[1]
            context.user_data['shift_date'] = date_str
            
            slots = await self.db.get_schedule_slots_by_date(date_str)
            if not slots:
                keyboard = get_back_keyboard()
                try:
                    await query.edit_message_text(
                        f"Нет доступных слотов на дату {date_str}.\n"
                        "Сначала создайте слоты расписания через меню '2. Редактировать расписание' -> 'Добавить событие'",
                        reply_markup=keyboard
                    )
                except BadRequest:
                    await query.message.reply_text(
                        f"Нет доступных слотов на дату {date_str}.\n"
                        "Сначала создайте слоты расписания через меню '2. Редактировать расписание' -> 'Добавить событие'",
                        reply_markup=keyboard
                    )
                return WAITING_SHIFT_DATE
            
            keyboard = get_slot_selection_keyboard(slots, show_address=True, show_back=True)
            try:
                await query.edit_message_text(
                    f"Дата: {date_str}\nВыберите слот:",
                    reply_markup=keyboard
                )
            except BadRequest:
                await query.message.reply_text(
                    f"Дата: {date_str}\nВыберите слот:",
                    reply_markup=keyboard
                )
            return WAITING_SHIFT_SLOT
        return WAITING_SHIFT_DATE

    async def admin_shift_slot_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        # Check if user is admin
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            # This is not an admin, let employee handler process it
            return ConversationHandler.END
        
        if query.data == "back":
            # Go back to date selection
            date_str = context.user_data.get('shift_date', '2025-01-01')
            keyboard = get_date_selection_keyboard(show_back=False)
            try:
                await query.edit_message_text(
                    "Выберите день для постановки смен:",
                    reply_markup=keyboard
                )
            except BadRequest:
                await query.message.reply_text(
                    "Выберите день для постановки смен:",
                    reply_markup=keyboard
                )
            return WAITING_SHIFT_DATE
        
        if query.data.startswith("slot_"):
            slot_id = int(query.data.split("_")[1])
            context.user_data['shift_slot_id'] = slot_id
            
            # Get available employees
            employees = await self.db.get_available_employees_for_slot(slot_id)
            if not employees:
                await query.edit_message_text("Нет доступных сотрудников для этого слота.")
                return ConversationHandler.END
            
            keyboard = get_employee_selection_keyboard(employees, show_back=True)
            await query.edit_message_text(
                "Выберите сотрудника:",
                reply_markup=keyboard
            )
            return WAITING_SHIFT_EMPLOYEE
        return WAITING_SHIFT_SLOT

    async def admin_shift_employee_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to slot selection
            date_str = context.user_data.get('shift_date', '2025-01-01')
            slots = await self.db.get_schedule_slots_by_date(date_str)
            if slots:
                keyboard = get_slot_selection_keyboard(slots, show_back=True)
                await query.edit_message_text(
                    f"Дата: {date_str}\nВыберите слот:",
                    reply_markup=keyboard
                )
                return WAITING_SHIFT_SLOT
            else:
                return ConversationHandler.END
        
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
        keyboard = get_period_selection_keyboard(show_back=False)
        await update.message.reply_text(
            "Выберите период:",
            reply_markup=keyboard
        )
        return WAITING_SALARY_PERIOD

    async def employee_salary_period_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle period selection for employee salary"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to main menu
            return ConversationHandler.END
        
        if query.data.startswith("period_"):
            if query.data == "period_custom":
                keyboard = get_period_start_date_keyboard(show_back=True)
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
        
        if query.data == "back":
            # Go back to period selection
            keyboard = get_period_selection_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите период:",
                reply_markup=keyboard
            )
            return WAITING_SALARY_PERIOD
        
        if query.data.startswith("period_start_"):
            start_date = query.data.replace("period_start_", "")
            context.user_data['salary_period_start'] = start_date
            
            keyboard = get_period_end_date_keyboard(start_date, show_back=True)
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
        
        if query.data == "back":
            # Go back to start date selection
            keyboard = get_period_start_date_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите начальную дату периода:",
                reply_markup=keyboard
            )
            return WAITING_PERIOD_START
        
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
        import logging
        logging.info(f"employee_schedule called for user {update.effective_user.id}")
        keyboard = get_date_selection_keyboard(show_back=False)
        await update.message.reply_text(
            "Выберите дату или введите диапазон дат:",
            reply_markup=keyboard
        )
        logging.info(f"employee_schedule returning WAITING_SCHEDULE_DATE")
        return WAITING_SCHEDULE_DATE

    async def employee_schedule_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        import logging
        logging.info(f"employee_schedule_date_selected called")
        query = update.callback_query
        if query:
            logging.info(f"Callback data: {query.data}")
            await query.answer()
        else:
            logging.error("employee_schedule_date_selected called without callback_query")
            return ConversationHandler.END
        
        if query.data.startswith("date_"):
            try:
                date_str = query.data.split("_")[1]
                user_id = update.effective_user.id
                
                # Get only shifts assigned to this employee
                shifts = await self.db.get_employee_shifts(user_id, date_str, date_str)
                
                # Debug logging
                import logging
                import sys
                logging.critical(f"DEBUG employee_schedule_date_selected: user_id={user_id}, date={date_str}, shifts_count={len(shifts)}")
                print(f"DEBUG employee_schedule_date_selected: user_id={user_id}, date={date_str}, shifts_count={len(shifts)}", file=sys.stderr, flush=True)
                if shifts:
                    for shift in shifts:
                        logging.critical(f"DEBUG shift: {shift}")
                        print(f"DEBUG shift: {shift}", file=sys.stderr, flush=True)
                
                if not shifts:
                    await query.edit_message_text(f"На {date_str} у вас нет назначенных смен.")
                    return ConversationHandler.END
                
                schedule_text = f"Ваше расписание на {date_str}:\n\n"
                for shift in shifts:
                    schedule_text += f"🕐 {shift['start_time']}-{shift['end_time']}"
                    if shift.get('address'):
                        schedule_text += f"\n📍 {shift['address']}"
                    required = shift.get('required_employees', 1)
                    schedule_text += f"\n👥 Нужно: {required} чел.\n\n"
                
                await query.edit_message_text(schedule_text)
                return ConversationHandler.END
            except Exception as e:
                import logging
                logging.error(f"Error in employee_schedule_date_selected: {e}", exc_info=True)
                try:
                    await query.edit_message_text(f"Произошла ошибка: {str(e)}")
                except:
                    pass
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
            # Get only shifts assigned to this employee
            shifts = await self.db.get_employee_shifts(user_id, start_date, end_date)
            
            if not shifts:
                await update.message.reply_text(f"Нет смен в периоде {start_date} - {end_date}.")
                return ConversationHandler.END
            
            schedule_text = f"Ваше расписание на период {start_date} - {end_date}:\n\n"
            current_date = None
            for shift in shifts:
                shift_date = shift['date']
                if shift_date != current_date:
                    current_date = shift_date
                    schedule_text += f"\n📅 {current_date}:\n"
                schedule_text += f"  🕐 {shift['start_time']}-{shift['end_time']}"
                if shift.get('address'):
                    schedule_text += f"\n    📍 {shift['address']}"
                required = shift.get('required_employees', 1)
                schedule_text += f"\n    👥 Нужно: {required} чел.\n"
            
            await update.message.reply_text(schedule_text)
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "Неверный формат. Введите даты в формате:\n2025-01-01 2025-01-07"
            )
            return WAITING_SCHEDULE_DATE_RANGE

    async def employee_available_slots(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Employee: View and sign up for available slots"""
        keyboard = get_date_selection_keyboard(show_back=True)
        await update.message.reply_text(
            "Выберите дату для просмотра доступных слотов:",
            reply_markup=keyboard
        )
        return WAITING_EMPLOYEE_SLOT_SELECTION
    
    async def employee_slot_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle date selection for available slots"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to main menu
            return ConversationHandler.END
        
        if query.data.startswith("date_"):
            date_str = query.data.split("_")[1]
            context.user_data['employee_slot_date'] = date_str
            
            # Get open slots for this date that have available space
            # Exclude slots where this employee is already assigned
            user_id = update.effective_user.id
            
            # Debug logging
            import logging
            import sys
            logging.critical(f"DEBUG employee_slot_date_selected: user_id={user_id}, date={date_str}")
            print(f"DEBUG employee_slot_date_selected: user_id={user_id}, date={date_str}", file=sys.stderr, flush=True)
            
            # First, check all slots on this date to see what's available
            all_slots = await self.db.get_schedule_slots_by_range(date_str, date_str, only_open=False)
            logging.critical(f"DEBUG all_slots on {date_str}: {len(all_slots)}")
            print(f"DEBUG all_slots on {date_str}: {len(all_slots)}", file=sys.stderr, flush=True)
            for slot in all_slots:
                logging.critical(f"DEBUG slot: id={slot.get('id')}, is_open={slot.get('is_open')}, required={slot.get('required_employees')}, employee_id={slot.get('employee_id')}")
                print(f"DEBUG slot: id={slot.get('id')}, is_open={slot.get('is_open')}, required={slot.get('required_employees')}, employee_id={slot.get('employee_id')}", file=sys.stderr, flush=True)
            
            slots = await self.db.get_schedule_slots_by_range(date_str, date_str, only_open=True, exclude_employee_id=user_id)
            
            logging.critical(f"DEBUG open slots (exclude employee {user_id}): {len(slots)}")
            print(f"DEBUG open slots (exclude employee {user_id}): {len(slots)}", file=sys.stderr, flush=True)
            
            if not slots:
                keyboard = get_back_keyboard()
                await query.edit_message_text(
                    f"На {date_str} нет доступных слотов для записи.\n\n"
                    "Доступные слоты - это открытые события, на которые еще можно записаться.",
                    reply_markup=keyboard
                )
                return WAITING_EMPLOYEE_SLOT_SELECTION
            
            # Show slots with address and available spots
            text = f"📅 Доступные слоты на {date_str}:\n\n"
            for slot in slots:
                text += f"🕐 {slot['start_time']}-{slot['end_time']}\n"
                if slot.get('address'):
                    text += f"📍 {slot['address']}\n"
                required = slot.get('required_employees', 1)
                # Count how many employees are already assigned
                assigned_count = await self.db.get_slot_assigned_count(slot['id'])
                available = required - assigned_count
                text += f"👥 Нужно: {required} чел. (свободно мест: {available})\n\n"
            
            keyboard = get_slot_selection_keyboard(slots, show_address=True, show_back=True)
            await query.edit_message_text(
                text,
                reply_markup=keyboard
            )
            return WAITING_EMPLOYEE_SLOT_SELECTION
        return WAITING_EMPLOYEE_SLOT_SELECTION
    
    async def employee_slot_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle slot selection for employee signup"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to date selection
            try:
                keyboard = get_date_selection_keyboard(show_back=True)
                try:
                    await query.edit_message_text(
                        "Выберите дату для просмотра доступных слотов:",
                        reply_markup=keyboard
                    )
                except BadRequest:
                    # If message is the same, just send a new message
                    await query.message.reply_text(
                        "Выберите дату для просмотра доступных слотов:",
                        reply_markup=keyboard
                    )
                return WAITING_EMPLOYEE_SLOT_SELECTION
            except Exception as e:
                import logging
                logging.error(f"Error in employee_slot_selected back handler: {e}", exc_info=True)
                # Fallback: just end conversation
                return ConversationHandler.END
        
        if query.data.startswith("slot_"):
            slot_id = int(query.data.split("_")[1])
            user_id = update.effective_user.id
            user = update.effective_user
            
            try:
                # Ensure user exists in database
                user_in_db = await self.db.get_user_by_id(user_id)
                if not user_in_db:
                    # Add user to database
                    await self.db.add_user(
                        user_id=user_id,
                        username=user.username,
                        full_name=user.full_name,
                        is_admin=False
                    )
                
                await self.db.assign_shift(slot_id, user_id)
                # Slot will be closed automatically in assign_shift() if fully booked
                
                # Get slot details for confirmation
                date_str = context.user_data.get('employee_slot_date', '2025-01-01')
                slots = await self.db.get_schedule_slots_by_range(date_str, date_str)
                slot = next((s for s in slots if s['id'] == slot_id), None)
                
                text = "✅ Вы успешно записались на слот!\n\n"
                if slot:
                    text += f"Дата: {slot['date']}\n"
                    text += f"Время: {slot['start_time']}-{slot['end_time']}\n"
                    if slot.get('address'):
                        text += f"Адрес: {slot['address']}\n"
                    required = slot.get('required_employees', 1)
                    text += f"Нужно человек: {required}\n"
                
                await query.edit_message_text(text)
                
                # Clean up
                context.user_data.pop('employee_slot_date', None)
                return ConversationHandler.END
            except ValueError as e:
                await query.edit_message_text(f"❌ Ошибка: {str(e)}")
                return ConversationHandler.END
            except Exception as e:
                import logging
                logging.error(f"Error in employee_slot_selected: {e}", exc_info=True)
                await query.edit_message_text(f"❌ Произошла ошибка: {str(e)}")
                return ConversationHandler.END
        
        return WAITING_EMPLOYEE_SLOT_SELECTION

    async def employee_free_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Employee: Manage free time"""
        import logging
        logging.info(f"employee_free_time called for user {update.effective_user.id}")
        keyboard = [
            [InlineKeyboardButton("Добавить свободное время", callback_data="add_free_time")],
            [InlineKeyboardButton("Удалить свободное время", callback_data="delete_free_time")]
        ]
        keyboard_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Управление свободным временем:",
            reply_markup=keyboard_markup
        )
        return WAITING_FREE_TIME_DATE
    
    async def employee_free_time_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle free time action selection (add or delete)"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "add_free_time":
            keyboard = get_date_selection_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите день для добавления свободного времени:",
                reply_markup=keyboard
            )
            context.user_data['free_time_action'] = 'add'
            return WAITING_FREE_TIME_DATE
        elif query.data == "delete_free_time":
            keyboard = get_date_selection_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите день для удаления свободного времени:",
                reply_markup=keyboard
            )
            context.user_data['free_time_action'] = 'delete'
            return WAITING_FREE_TIME_DELETE_DATE
        elif query.data == "back":
            # Go back to main menu
            return ConversationHandler.END
        
        return WAITING_FREE_TIME_DATE

    async def employee_free_time_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        import logging
        logging.info(f"employee_free_time_date_selected called")
        query = update.callback_query
        if query:
            logging.info(f"Callback data: {query.data}")
            await query.answer()
        else:
            logging.error("employee_free_time_date_selected called without callback_query")
            return ConversationHandler.END
        
        if query.data.startswith("date_"):
            try:
                date_str = query.data.split("_")[1]
                context.user_data['free_time_date'] = date_str
                
                action = context.user_data.get('free_time_action', 'add')
                if action == 'add':
                    keyboard = get_back_keyboard()
                    await query.edit_message_text(
                        f"Дата: {date_str}\n"
                        "Введите слоты в формате:\n"
                        "ЧЧ:ММ ЧЧ:ММ\n"
                        "ЧЧ:ММ ЧЧ:ММ\n"
                        "(можно несколько слотов, каждый с новой строки)",
                        reply_markup=keyboard
                    )
                    return WAITING_FREE_TIME_SLOTS
                else:
                    # This shouldn't happen, but handle it
                    return WAITING_FREE_TIME_DATE
            except Exception as e:
                import logging
                logging.error(f"Error in employee_free_time_date_selected: {e}", exc_info=True)
                try:
                    await query.edit_message_text(f"Произошла ошибка: {str(e)}")
                except:
                    pass
                return ConversationHandler.END
        elif query.data == "back":
            # Go back to action selection - call employee_free_time_action handler logic
            keyboard = [
                [InlineKeyboardButton("Добавить свободное время", callback_data="add_free_time")],
                [InlineKeyboardButton("Удалить свободное время", callback_data="delete_free_time")]
            ]
            keyboard_markup = InlineKeyboardMarkup(keyboard)
            # Clear the action to reset state
            context.user_data.pop('free_time_action', None)
            context.user_data.pop('free_time_date', None)
            try:
                await query.edit_message_text(
                    "Управление свободным временем:",
                    reply_markup=keyboard_markup
                )
            except BadRequest:
                await query.message.reply_text(
                    "Управление свободным временем:",
                    reply_markup=keyboard_markup
                )
            # Return to the state where action selection happens
            return WAITING_FREE_TIME_DATE
        return WAITING_FREE_TIME_DATE
    
    async def employee_free_time_delete_date_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle date selection for deleting free time"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("date_"):
            try:
                date_str = query.data.split("_")[1]
                user_id = update.effective_user.id
                
                # Get free time slots for this date
                free_time_slots = await self.db.get_employee_free_time(user_id, date_str, date_str)
                
                if not free_time_slots:
                    keyboard = get_back_keyboard()
                    await query.edit_message_text(
                        f"На {date_str} нет свободного времени для удаления.",
                        reply_markup=keyboard
                    )
                    return WAITING_FREE_TIME_DELETE_DATE
                
                context.user_data['free_time_delete_date'] = date_str
                keyboard = get_free_time_slots_keyboard(free_time_slots, show_back=True)
                await query.edit_message_text(
                    f"Дата: {date_str}\nВыберите свободное время для удаления:",
                    reply_markup=keyboard
                )
                return WAITING_FREE_TIME_DELETE_SLOT
            except Exception as e:
                import logging
                logging.error(f"Error in employee_free_time_delete_date_selected: {e}", exc_info=True)
                await query.edit_message_text(f"Произошла ошибка: {str(e)}")
                return ConversationHandler.END
        elif query.data == "back":
            # Go back to action selection
            keyboard = [
                [InlineKeyboardButton("Добавить свободное время", callback_data="add_free_time")],
                [InlineKeyboardButton("Удалить свободное время", callback_data="delete_free_time")]
            ]
            keyboard_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Управление свободным временем:",
                reply_markup=keyboard_markup
            )
            return WAITING_FREE_TIME_DATE
        return WAITING_FREE_TIME_DELETE_DATE
    
    async def employee_free_time_delete_slot_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle free time slot selection for deletion"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to date selection
            date_str = context.user_data.get('free_time_delete_date', '2025-01-01')
            keyboard = get_date_selection_keyboard(show_back=True)
            await query.edit_message_text(
                "Выберите день для удаления свободного времени:",
                reply_markup=keyboard
            )
            return WAITING_FREE_TIME_DELETE_DATE
        
        if query.data.startswith("free_time_"):
            try:
                free_time_id = int(query.data.split("_")[2])
                user_id = update.effective_user.id
                
                # Delete the free time slot
                await self.db.delete_free_time_slot(free_time_id, user_id)
                
                await query.edit_message_text("✅ Свободное время удалено.")
                return ConversationHandler.END
            except ValueError as e:
                await query.edit_message_text(f"❌ Ошибка: {str(e)}")
                return ConversationHandler.END
            except Exception as e:
                import logging
                logging.error(f"Error in employee_free_time_delete_slot_selected: {e}", exc_info=True)
                await query.edit_message_text(f"❌ Произошла ошибка: {str(e)}")
                return ConversationHandler.END
        
        return WAITING_FREE_TIME_DELETE_SLOT
        
        return WAITING_FREE_TIME_DELETE_SLOT

    async def employee_free_time_slots_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button from free time slots input"""
        query = update.callback_query
        await query.answer()
        
        # Ensure action is set to 'add' for proper state handling
        context.user_data['free_time_action'] = 'add'
        date_str = context.user_data.get('free_time_date', '')
        keyboard = get_date_selection_keyboard(show_back=True)
        try:
            await query.edit_message_text(
                f"Выберите день для добавления свободного времени:",
                reply_markup=keyboard
            )
        except BadRequest:
            await query.message.reply_text(
                f"Выберите день для добавления свободного времени:",
                reply_markup=keyboard
            )
        return WAITING_FREE_TIME_DATE

    async def employee_free_time_slots(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        # Check for back button
        if text == "◀️ Назад" or text.lower() == "назад":
            keyboard = get_date_selection_keyboard(show_back=True)
            await update.message.reply_text(
                "Выберите день для добавления свободного времени:",
                reply_markup=keyboard
            )
            return WAITING_FREE_TIME_DATE
        
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

    async def admin_add_worker_user_id_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button from worker user ID input"""
        query = update.callback_query
        await query.answer()
        
        keyboard = get_worker_management_keyboard()
        await query.edit_message_text(
            "Управление сотрудниками:",
            reply_markup=keyboard
        )
        return WAITING_WORKER_MENU

    async def admin_add_worker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Add worker"""
        query = update.callback_query
        await query.answer()
        keyboard = get_back_keyboard()
        await query.edit_message_text(
            "Введите Telegram username сотрудника для добавления:\n"
            "(Например: @username)\n\n"
            "Если username скрыт от ботов, попросите сотрудника:\n"
            "1. Написать боту любое сообщение (/start)\n"
            "2. Или предоставить свой User ID (можно получить через @userinfobot)\n"
            "3. Затем используйте формат: id:123456789",
            reply_markup=keyboard
        )
        return WAITING_WORKER_USER_ID

    async def admin_add_worker_user_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle worker username input"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        # Check for back button text
        if text == "◀️ Назад" or text.lower() == "назад":
            keyboard = get_worker_management_keyboard()
            await update.message.reply_text(
                "Управление сотрудниками:",
                reply_markup=keyboard
            )
            return WAITING_WORKER_MENU
        
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

    async def admin_add_worker_name_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button from worker name input"""
        query = update.callback_query
        await query.answer()
        
        keyboard = get_back_keyboard()
        await query.edit_message_text(
            "Введите Telegram username сотрудника для добавления:\n"
            "(Например: @username)\n\n"
            "Если username скрыт от ботов, попросите сотрудника:\n"
            "1. Написать боту любое сообщение (/start)\n"
            "2. Или предоставить свой User ID (можно получить через @userinfobot)\n"
            "3. Затем используйте формат: id:123456789",
            reply_markup=keyboard
        )
        return WAITING_WORKER_USER_ID
    
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
        
        # Mark that we're in remove worker flow
        context.user_data['action'] = 'remove_worker'
        
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
        
        # Only process if we're in the remove worker flow
        # Check if action is 'remove_worker' - if not, this is from another conversation
        if query.data.startswith("emp_"):
            if context.user_data.get('action') != 'remove_worker':
                # This callback is from a different conversation, ignore it
                return ConversationHandler.END
            
            emp_id = int(query.data.split("_")[1])
            
            try:
                user = await self.db.get_user_by_id(emp_id)
                if not user:
                    keyboard = get_worker_management_keyboard()
                    await query.edit_message_text("Сотрудник не найден.", reply_markup=keyboard)
                    return WAITING_WORKER_MENU
                
                # Check if user is admin
                if user.get('is_admin'):
                    keyboard = get_worker_management_keyboard()
                    await query.edit_message_text(
                        "Нельзя удалить администратора.",
                        reply_markup=keyboard
                    )
                    return WAITING_WORKER_MENU
                
                keyboard = get_yes_no_keyboard("confirm_remove")
                context.user_data['remove_worker_id'] = emp_id
                await query.edit_message_text(
                    f"Подтвердите удаление сотрудника:\n"
                    f"ID: {emp_id}\n"
                    f"Имя: {user.get('full_name') or 'Не указано'}\n"
                    f"⚠️ Все назначенные смены будут удалены."
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

    async def admin_view_employee_free_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: View employee free time"""
        # Mark that we're in free_time view flow
        context.user_data.clear()
        context.user_data['action'] = 'view_free_time'
        
        employees = await self.db.get_all_employees()
        if not employees:
            await update.message.reply_text("Нет сотрудников в базе.")
            return ConversationHandler.END
        
        keyboard = get_employee_selection_keyboard(employees)
        await update.message.reply_text(
            "Выберите сотрудника для просмотра свободного времени:",
            reply_markup=keyboard
        )
        return WAITING_FREE_TIME_EMPLOYEE
    
    async def admin_free_time_employee_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle employee selection for free time view - only works in WAITING_FREE_TIME_EMPLOYEE state"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            # Go back to main menu
            return ConversationHandler.END
        
        if query.data.startswith("emp_"):
            # Only process if we're in the free_time view flow
            # Check if action is 'view_free_time' - if not, this is from another conversation
            if context.user_data.get('action') != 'view_free_time':
                # This callback is from a different conversation, ignore it
                return ConversationHandler.END
            
            emp_id = int(query.data.split("_")[1])
            
            try:
                # Get employee info
                employee = await self.db.get_user_by_id(emp_id)
                if not employee:
                    await query.edit_message_text("Сотрудник не найден.")
                    return ConversationHandler.END
                
                # Get all free time slots
                free_time_slots = await self.db.get_employee_free_time(emp_id)
                
                if not free_time_slots:
                    employee_name = employee.get('full_name') or employee.get('username') or f"ID: {emp_id}"
                    await query.edit_message_text(
                        f"У сотрудника {employee_name} нет указанного свободного времени."
                    )
                    return ConversationHandler.END
                
                # Format free time slots
                text = f"Свободное время сотрудника:\n"
                employee_name = employee.get('full_name') or employee.get('username') or f"ID: {emp_id}"
                text += f"👤 {employee_name}\n\n"
                
                current_date = None
                for slot in free_time_slots:
                    slot_date = slot['date']
                    if slot_date != current_date:
                        current_date = slot_date
                        text += f"\n📅 {current_date}:\n"
                    
                    start_time = slot['start_time']
                    end_time = slot['end_time']
                    text += f"  🕐 {start_time}-{end_time}\n"
                
                await query.edit_message_text(text)
                return ConversationHandler.END
            except Exception as e:
                import logging
                logging.error(f"Error in admin_free_time_employee_selected: {e}", exc_info=True)
                await query.edit_message_text(f"Произошла ошибка: {str(e)}")
                return ConversationHandler.END
        
        return WAITING_FREE_TIME_EMPLOYEE

    async def admin_list_workers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: List all workers"""
        import logging
        logger = logging.getLogger(__name__)
        query = update.callback_query
        await query.answer()
        
        users = await self.db.get_all_users()
        logger.error(f"DEBUG admin_list_workers: found {len(users)} total users")
        for user in users:
            logger.error(f"DEBUG User in list: {user['user_id']}, is_admin={user.get('is_admin')}, name={user.get('full_name')}")
        
        if not users:
            keyboard = get_worker_management_keyboard()
            await query.edit_message_text("Нет пользователей в базе.", reply_markup=keyboard)
            return WAITING_WORKER_MENU
        
        text = f"Список всех пользователей ({len(users)}):\n\n"
        for user in users:
            is_admin = user.get('is_admin')
            role = "Админ" if is_admin else "Сотрудник"
            user_id = user['user_id']
            full_name = user.get('full_name')
            if not full_name or not full_name.strip():
                full_name = f'User {user_id}'
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
        
        keyboard = get_back_keyboard()
        await query.edit_message_text(
            "Введите Telegram User ID пользователя для назначения администратором:\n"
            "(Можно получить через @userinfobot)",
            reply_markup=keyboard
        )
        return WAITING_ADMIN_USER_ID

    async def admin_make_admin_user_id_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button from admin user ID input"""
        query = update.callback_query
        await query.answer()
        
        keyboard = get_worker_management_keyboard()
        await query.edit_message_text(
            "Управление сотрудниками:",
            reply_markup=keyboard
        )
        return WAITING_WORKER_MENU

    async def admin_make_admin_user_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle admin user ID input"""
        text = update.message.text.strip()
        
        if self.is_menu_command(text):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        # Check for back button text
        if text == "◀️ Назад" or text.lower() == "назад":
            keyboard = get_worker_management_keyboard()
            await update.message.reply_text(
                "Управление сотрудниками:",
                reply_markup=keyboard
            )
            return WAITING_WORKER_MENU
        
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

    async def admin_edit_employee_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin: Edit user name - show all users list (employees and admins)"""
        query = update.callback_query
        await query.answer()
        
        try:
            users = await self.db.get_all_users_for_editing()
            if not users:
                keyboard = get_worker_management_keyboard()
                try:
                    await query.edit_message_text(
                        "Нет пользователей в базе.",
                        reply_markup=keyboard
                    )
                except BadRequest:
                    # If message is the same, just send a new message
                    await query.message.reply_text(
                        "Нет пользователей в базе.",
                        reply_markup=keyboard
                    )
                return WAITING_WORKER_MENU
            
            keyboard = get_employee_selection_keyboard(users, show_back=True)
            await query.edit_message_text(
                "Выберите пользователя для редактирования имени:",
                reply_markup=keyboard
            )
            return WAITING_EDIT_NAME_EMPLOYEE
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in admin_edit_employee_name: {e}", exc_info=True)
            await query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)
            return WAITING_WORKER_MENU

    async def admin_edit_employee_name_selected(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle employee selection for name editing"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "back":
            keyboard = get_worker_management_keyboard()
            await query.edit_message_text(
                "Управление сотрудниками:",
                reply_markup=keyboard
            )
            return WAITING_WORKER_MENU
        
        if query.data == "emp_all":
            await query.answer("Пожалуйста, выберите конкретного сотрудника", show_alert=True)
            return WAITING_EDIT_NAME_EMPLOYEE
        
        try:
            employee_id = int(query.data.replace("emp_", ""))
            user = await self.db.get_user_by_id(employee_id)
            
            if not user:
                await query.answer("Сотрудник не найден", show_alert=True)
                return WAITING_EDIT_NAME_EMPLOYEE
            
            current_name = user.get('full_name') or user.get('username') or f"User {employee_id}"
            is_admin = user.get('is_admin', False)
            role_text = "администратора" if is_admin else "сотрудника"
            context.user_data['edit_name_employee_id'] = employee_id
            
            keyboard = get_back_keyboard()
            await query.edit_message_text(
                f"Текущее имя: {current_name}\n"
                f"ID: {employee_id}\n"
                f"Роль: {'Админ' if is_admin else 'Сотрудник'}\n\n"
                f"Введите новое имя для {role_text}:",
                reply_markup=keyboard
            )
            return WAITING_EDIT_NAME_INPUT
            
        except ValueError:
            await query.answer("Ошибка: неверный ID сотрудника", show_alert=True)
            return WAITING_EDIT_NAME_EMPLOYEE
        except Exception as e:
            await query.answer(f"Ошибка: {str(e)}", show_alert=True)
            return WAITING_EDIT_NAME_EMPLOYEE

    async def admin_edit_employee_name_input_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle back button from name input to user selection"""
        query = update.callback_query
        await query.answer()
        
        try:
            users = await self.db.get_all_users_for_editing()
            if not users:
                keyboard = get_worker_management_keyboard()
                try:
                    await query.edit_message_text(
                        "Нет пользователей в базе.",
                        reply_markup=keyboard
                    )
                except BadRequest:
                    # If message is the same, just send a new message
                    await query.message.reply_text(
                        "Нет пользователей в базе.",
                        reply_markup=keyboard
                    )
                return WAITING_WORKER_MENU
            
            keyboard = get_employee_selection_keyboard(users, show_back=True)
            await query.edit_message_text(
                "Выберите пользователя для редактирования имени:",
                reply_markup=keyboard
            )
            context.user_data.pop('edit_name_employee_id', None)
            return WAITING_EDIT_NAME_EMPLOYEE
        except BadRequest:
            # Message not modified - try sending new message
            try:
                employees = await self.db.get_all_employees()
                if employees:
                    keyboard = get_employee_selection_keyboard(employees, show_back=True)
                    await query.message.reply_text(
                        "Выберите сотрудника для редактирования имени:",
                        reply_markup=keyboard
                    )
                    context.user_data.pop('edit_name_employee_id', None)
                    return WAITING_EDIT_NAME_EMPLOYEE
            except Exception:
                pass
            await query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)
            return WAITING_WORKER_MENU
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in admin_edit_employee_name_input_back: {e}", exc_info=True)
            await query.answer("Произошла ошибка. Попробуйте еще раз.", show_alert=True)
            return WAITING_WORKER_MENU

    async def admin_edit_employee_name_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new name input"""
        new_name = update.message.text.strip()
        
        if self.is_menu_command(new_name):
            await update.message.reply_text("Операция отменена. Используйте выбранную команду.")
            return ConversationHandler.END
        
        # Check for back button text
        if new_name == "◀️ Назад" or new_name.lower() == "назад":
            users = await self.db.get_all_users_for_editing()
            if not users:
                keyboard = get_worker_management_keyboard()
                await update.message.reply_text(
                    "Нет пользователей в базе.",
                    reply_markup=keyboard
                )
                return WAITING_WORKER_MENU
            
            keyboard = get_employee_selection_keyboard(users, show_back=True)
            await update.message.reply_text(
                "Выберите пользователя для редактирования имени:",
                reply_markup=keyboard
            )
            context.user_data.pop('edit_name_employee_id', None)
            return WAITING_EDIT_NAME_EMPLOYEE
        
        if not new_name:
            keyboard = get_back_keyboard()
            await update.message.reply_text(
                "Имя не может быть пустым. Введите имя:",
                reply_markup=keyboard
            )
            return WAITING_EDIT_NAME_INPUT
        
        employee_id = context.user_data.get('edit_name_employee_id')
        if not employee_id:
            await update.message.reply_text("Ошибка: не найден ID сотрудника. Начните заново.")
            return ConversationHandler.END
        
        try:
            await self.db.update_employee_name(employee_id, new_name)
            user = await self.db.get_user_by_id(employee_id)
            username = user.get('username') if user else None
            is_admin = user.get('is_admin', False) if user else False
            display_info = f"@{username}" if username else f"ID: {employee_id}"
            role_text = "администратора" if is_admin else "сотрудника"
            
            await update.message.reply_text(
                f"✅ Имя {role_text} обновлено:\n"
                f"{display_info}\n"
                f"Новое имя: {new_name}"
            )
            context.user_data.pop('edit_name_employee_id', None)
            return ConversationHandler.END
            
        except ValueError as e:
            await update.message.reply_text(f"Ошибка: {str(e)}")
            return ConversationHandler.END
        except Exception as e:
            await update.message.reply_text(f"Ошибка при обновлении имени: {str(e)}")
            return ConversationHandler.END

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Операция отменена.")
        return ConversationHandler.END
    
    async def handle_menu_command_in_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu commands that interrupt a conversation"""
        # Just end the conversation silently - the menu command will be handled by its entry point handler
        # This prevents the "Операция отменена" message from appearing
        return ConversationHandler.END

