from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Tuple, Optional
from datetime import datetime, timedelta


def get_main_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    if is_admin:
        keyboard = [
            ["1. Расписание"],
            ["2. Редактировать расписание"],
            ["3. Отчет"],
            ["4. Поставить смены"],
            ["5. Управление сотрудниками"],
            ["6. Сотрудник свободен в"]
        ]
    else:
        keyboard = [
            ["1. Моя зарплата"],
            ["2. Мое расписание"],
            ["3. Доступные слоты"],
            ["4. Указать свободное время"]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def get_employee_selection_keyboard(employees: List[Tuple[int, str]]) -> InlineKeyboardMarkup:
    buttons = []
    for emp_id, name in employees:
        # Show name with ID if name exists, otherwise just ID
        if name and name != f"User {emp_id}":
            button_text = f"{name} ({emp_id})"
        else:
            button_text = f"User {emp_id}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=f"emp_{emp_id}")])
    buttons.append([InlineKeyboardButton("Все", callback_data="emp_all")])
    return InlineKeyboardMarkup(buttons)


def get_schedule_edit_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Добавить событие", callback_data="add_event")],
        [InlineKeyboardButton("Удалить событие", callback_data="delete_event")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_date_selection_keyboard(days: int = 14) -> InlineKeyboardMarkup:
    buttons = []
    today = datetime.now().date()
    row = []
    for i in range(days):
        date_obj = today + timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        date_display = date_obj.strftime("%d.%m")
        row.append(InlineKeyboardButton(date_display, callback_data=f"date_{date_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if show_back:
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(buttons)


def get_slot_selection_keyboard(slots: List, show_address: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    for slot in slots:
        slot_id = slot['id'] if isinstance(slot, dict) else slot[0]
        start_time = slot['start_time'] if isinstance(slot, dict) else slot[2]
        end_time = slot['end_time'] if isinstance(slot, dict) else slot[3]
        if show_address and isinstance(slot, dict) and slot.get('address'):
            address_short = slot['address'][:20] + "..." if len(slot['address']) > 20 else slot['address']
            button_text = f"{start_time}-{end_time} ({address_short})"
        else:
            button_text = f"{start_time}-{end_time}"
        buttons.append([InlineKeyboardButton(button_text, callback_data=f"slot_{slot_id}")])
    return InlineKeyboardMarkup(buttons)


def get_yes_no_keyboard(action: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("Да", callback_data=f"{action}_yes"),
            InlineKeyboardButton("Нет", callback_data=f"{action}_no")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("Отмена", callback_data="cancel")]]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back")]]
    return InlineKeyboardMarkup(keyboard)


def get_employees_count_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="count_1"),
            InlineKeyboardButton("2", callback_data="count_2"),
            InlineKeyboardButton("3", callback_data="count_3"),
            InlineKeyboardButton("4", callback_data="count_4")
        ],
        [InlineKeyboardButton("◀️ Назад", callback_data="back")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_worker_management_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Добавить сотрудника", callback_data="add_worker")],
        [InlineKeyboardButton("Удалить сотрудника", callback_data="remove_worker")],
        [InlineKeyboardButton("Список сотрудников", callback_data="list_workers")],
        [InlineKeyboardButton("Назначить админа", callback_data="make_admin")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_period_selection_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting date period"""
    today = datetime.now().date()
    
    # Calculate this month start and end
    this_month_start = today.replace(day=1)
    if today.month == 12:
        next_month = this_month_start.replace(year=today.year + 1, month=1)
    else:
        next_month = this_month_start.replace(month=today.month + 1)
    this_month_end = next_month - timedelta(days=1)
    
    # Calculate next month start and end
    if next_month.month == 12:
        month_after = next_month.replace(year=next_month.year + 1, month=1)
    else:
        month_after = next_month.replace(month=next_month.month + 1)
    next_month_end = month_after - timedelta(days=1)
    
    buttons = [
        [InlineKeyboardButton("Сегодня", callback_data=f"period_{today}_{today}")],
        [
            InlineKeyboardButton("Эта неделя", callback_data=f"period_{today}_{today + timedelta(days=6)}"),
            InlineKeyboardButton("Следующая неделя", callback_data=f"period_{today + timedelta(days=7)}_{today + timedelta(days=13)}")
        ],
        [
            InlineKeyboardButton("Этот месяц", callback_data=f"period_{this_month_start}_{this_month_end}"),
            InlineKeyboardButton("Следующий месяц", callback_data=f"period_{next_month}_{next_month_end}")
        ],
        [InlineKeyboardButton("Выбрать период", callback_data="period_custom")]
    ]
    return InlineKeyboardMarkup(buttons)


def get_period_start_date_keyboard(show_back: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for selecting start date of custom period"""
    buttons = []
    today = datetime.now().date()
    row = []
    for i in range(14):
        date_obj = today + timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        date_display = date_obj.strftime("%d.%m")
        row.append(InlineKeyboardButton(date_display, callback_data=f"period_start_{date_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if show_back:
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(buttons)


def get_period_end_date_keyboard(start_date_str: str, show_back: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for selecting end date of custom period"""
    buttons = []
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    today = datetime.now().date()
    # Show dates from start_date to 14 days ahead
    row = []
    for i in range(14):
        date_obj = max(start_date, today) + timedelta(days=i)
        date_str = date_obj.strftime("%Y-%m-%d")
        date_display = date_obj.strftime("%d.%m")
        row.append(InlineKeyboardButton(date_display, callback_data=f"period_end_{date_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    if show_back:
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back")])
    return InlineKeyboardMarkup(buttons)

