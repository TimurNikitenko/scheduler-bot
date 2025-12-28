import os
import asyncpg
from datetime import datetime, date
from typing import List, Optional, Tuple, Dict
import asyncio


class Database:
    def __init__(self, db_url: str = None):
        if db_url is None:
            db_url = os.getenv(
                'DATABASE_URL',
                'postgresql://postgres:postgres@localhost:5432/telegram_bot'
            )
        self.db_url = db_url
        self._pool: Optional[asyncpg.Pool] = None

    async def init_pool(self):
        """Initialize connection pool"""
        import logging
        logger = logging.getLogger(__name__)
        
        if self._pool is None:
            logger.info(f"Creating connection pool with URL: {self.db_url[:50]}...")
            # Parse connection string for asyncpg
            # asyncpg uses postgresql:// but we need to convert from psycopg2 format
            try:
                self._pool = await asyncpg.create_pool(self.db_url, min_size=1, max_size=10)
                logger.info("Connection pool created successfully")
                await self.init_db()
                logger.info("Database initialization completed")
            except Exception as e:
                logger.error(f"Error creating connection pool: {e}", exc_info=True)
                raise

    async def close_pool(self):
        """Close connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    def _ensure_pool(self):
        """Ensure connection pool is initialized"""
        if self._pool is None:
            raise RuntimeError("Database pool not initialized. Call init_pool() first.")

    async def init_db(self):
        """Initialize database schema"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info("Starting database schema initialization...")
            async with self._pool.acquire() as conn:
                logger.info("Connection acquired, creating users table...")
                # Users table (employees and admins)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username VARCHAR(255),
                        full_name VARCHAR(255),
                        is_admin BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("Users table created/verified")
                
                logger.info("Creating schedule_slots table...")
                # Schedule slots (template schedule)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS schedule_slots (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL,
                        start_time TIME NOT NULL,
                        end_time TIME NOT NULL,
                        address TEXT,
                        location_latitude REAL,
                        location_longitude REAL,
                        required_employees INTEGER DEFAULT 1,
                        is_open BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("Schedule_slots table created/verified")
                
                logger.info("Adding columns to schedule_slots if needed...")
                # Add new columns if they don't exist (for existing databases)
                await conn.execute("""
                    DO $$ 
                    BEGIN
                        ALTER TABLE schedule_slots ADD COLUMN IF NOT EXISTS address TEXT;
                        ALTER TABLE schedule_slots ADD COLUMN IF NOT EXISTS location_latitude REAL;
                        ALTER TABLE schedule_slots ADD COLUMN IF NOT EXISTS location_longitude REAL;
                        ALTER TABLE schedule_slots ADD COLUMN IF NOT EXISTS required_employees INTEGER DEFAULT 1;
                    EXCEPTION
                        WHEN duplicate_column THEN NULL;
                    END $$;
                """)
                logger.info("Columns added/verified")
                
                logger.info("Creating shifts table...")
                # Shifts (assigned employees to slots)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS shifts (
                        id SERIAL PRIMARY KEY,
                        slot_id INTEGER REFERENCES schedule_slots(id) ON DELETE CASCADE,
                        employee_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                        date DATE NOT NULL,
                        start_time TIME NOT NULL,
                        end_time TIME NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("Shifts table created/verified")
                
                logger.info("Creating free_time_slots table...")
                # Free time slots (employee availability)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS free_time_slots (
                        id SERIAL PRIMARY KEY,
                        employee_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                        date DATE NOT NULL,
                        start_time TIME NOT NULL,
                        end_time TIME NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info("Free_time_slots table created/verified")
                logger.info("Database schema initialization completed successfully")
        except Exception as e:
            logger.error(f"Error initializing database schema: {e}", exc_info=True)
            raise
    
    async def initialize_admins(self, admin_ids: List[int]):
        """Initialize admin users from environment variable"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not admin_ids:
            logger.info("No admin IDs provided, skipping admin initialization")
            return
        
        self._ensure_pool()
        try:
            logger.info(f"Initializing {len(admin_ids)} admin users...")
            async with self._pool.acquire() as conn:
                for admin_id in admin_ids:
                    try:
                        # Check if user already exists
                        existing = await conn.fetchrow(
                            "SELECT user_id, is_admin FROM users WHERE user_id = $1",
                            admin_id
                        )
                        
                        if existing:
                            # Update existing user to admin if not already
                            if not existing['is_admin']:
                                await conn.execute(
                                    "UPDATE users SET is_admin = TRUE WHERE user_id = $1",
                                    admin_id
                                )
                                logger.info(f"Updated user {admin_id} to admin")
                            else:
                                logger.info(f"User {admin_id} is already an admin")
                        else:
                            # Create new admin user
                            await conn.execute("""
                                INSERT INTO users (user_id, username, full_name, is_admin)
                                VALUES ($1, NULL, NULL, TRUE)
                                ON CONFLICT (user_id) 
                                DO UPDATE SET is_admin = TRUE
                            """, admin_id)
                            logger.info(f"Created admin user {admin_id}")
                    except Exception as e:
                        logger.error(f"Error initializing admin {admin_id}: {e}", exc_info=True)
            
            logger.info("Admin users initialization completed")
        except Exception as e:
            logger.error(f"Error initializing admins: {e}", exc_info=True)
            # Don't raise - this is not critical for bot startup

    async def add_user(self, user_id: int, username: str = None, full_name: str = None, is_admin: bool = False):
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, full_name, is_admin)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) 
                DO UPDATE SET username = EXCLUDED.username, 
                             full_name = EXCLUDED.full_name,
                             is_admin = EXCLUDED.is_admin
            """, user_id, username, full_name, is_admin)

    async def update_employee_name(self, user_id: int, full_name: str):
        """Update user's full name (works for both employees and admins)"""
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE users 
                SET full_name = $1 
                WHERE user_id = $2
            """, full_name, user_id)
            if result == "UPDATE 0":
                raise ValueError("Пользователь не найден")

    async def get_all_users_for_editing(self) -> List[Tuple[int, str]]:
        """Get all users (employees and admins) for name editing"""
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, full_name, username, is_admin
                FROM users 
                ORDER BY COALESCE(NULLIF(full_name, ''), username, CAST(user_id AS TEXT))
            """)
            result = []
            for row in rows:
                user_id = row['user_id']
                full_name = row['full_name']
                username = row['username']
                is_admin = row.get('is_admin', False)
                
                # Build display name
                if full_name and full_name.strip():
                    display_name = full_name.strip()
                elif username:
                    display_name = f"@{username}"
                else:
                    display_name = f"User {user_id}"
                
                # Add role indicator
                if is_admin:
                    display_name = f"👑 {display_name} (Админ)"
                else:
                    display_name = f"👤 {display_name}"
                
                result.append((user_id, display_name))
            return result

    async def is_admin(self, user_id: int) -> bool:
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT is_admin FROM users WHERE user_id = $1", user_id)
            return row and row['is_admin'] is True

    async def get_all_employees(self) -> List[Tuple[int, str]]:
        import logging
        import sys
        logger = logging.getLogger(__name__)
        self._ensure_pool()
        print("=" * 50, file=sys.stderr, flush=True)
        print("DEBUG get_all_employees START", file=sys.stderr, flush=True)
        print("=" * 50, file=sys.stderr, flush=True)
        logger.critical("=" * 50)
        logger.critical("DEBUG get_all_employees START")
        logger.critical("=" * 50)
        async with self._pool.acquire() as conn:
            # Get employees: is_admin must be explicitly FALSE (not NULL, not TRUE)
            rows = await conn.fetch("""
                SELECT user_id, full_name, username, is_admin
                FROM users 
                WHERE (is_admin = FALSE OR is_admin IS NULL)
                ORDER BY COALESCE(NULLIF(full_name, ''), username, CAST(user_id AS TEXT))
            """)
            msg = f"DEBUG get_all_employees: SQL returned {len(rows)} rows"
            print(msg, file=sys.stderr, flush=True)
            logger.critical(msg)
            # Return (user_id, display_name) where display_name is full_name or username or "User {id}"
            result = []
            for row in rows:
                user_id = row['user_id']
                full_name = row['full_name']
                username = row['username']
                is_admin = row.get('is_admin')
                debug_msg = f"DEBUG Processing user {user_id}: is_admin={is_admin}, full_name={full_name}, username={username}"
                print(debug_msg, file=sys.stderr, flush=True)
                logger.critical(debug_msg)
                # Double check: skip if explicitly admin
                if is_admin is True:
                    skip_msg = f"DEBUG Skipping user {user_id} - is_admin is True"
                    print(skip_msg, file=sys.stderr, flush=True)
                    logger.critical(skip_msg)
                    continue
                if full_name and full_name.strip():
                    display_name = full_name.strip()
                elif username:
                    display_name = f"@{username}"
                else:
                    display_name = f"User {user_id}"
                result.append((user_id, display_name))
                added_msg = f"DEBUG Added employee: {user_id} -> {display_name}"
                print(added_msg, file=sys.stderr, flush=True)
                logger.critical(added_msg)
            final_msg = f"DEBUG get_all_employees: returning {len(result)} employees"
            print(final_msg, file=sys.stderr, flush=True)
            logger.critical(final_msg)
            return result

    async def get_all_users(self) -> List[Dict]:
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, username, full_name, is_admin 
                FROM users 
                ORDER BY full_name, username
            """)
            return [dict(row) for row in rows]

    async def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT user_id, username, full_name, is_admin 
                FROM users 
                WHERE user_id = $1
            """, user_id)
            return dict(row) if row else None

    async def remove_user(self, user_id: int):
        """Remove user and all their shifts (CASCADE will handle shifts deletion)"""
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            # First check if user exists and is admin
            user = await conn.fetchrow("""
                SELECT user_id, is_admin 
                FROM users 
                WHERE user_id = $1
            """, user_id)
            
            if not user:
                raise ValueError("Пользователь не найден")
            
            if user['is_admin']:
                raise ValueError("Нельзя удалить администратора")
            
            # Delete user - shifts will be deleted automatically due to CASCADE
            # Free time slots will also be deleted automatically due to CASCADE
            result = await conn.execute("""
                DELETE FROM users 
                WHERE user_id = $1
            """, user_id)
            
            if result == "DELETE 0":
                raise ValueError("Не удалось удалить пользователя")

    async def set_admin_status(self, user_id: int, is_admin: bool):
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE users 
                SET is_admin = $1 
                WHERE user_id = $2
            """, is_admin, user_id)
            if result == "UPDATE 0":
                raise ValueError("Пользователь не найден")

    async def add_schedule_slot(self, date_str: str, start_time: str, end_time: str, 
                                address: str = None, location_latitude: float = None, 
                                location_longitude: float = None, required_employees: int = 1,
                                is_open: bool = True) -> int:
        self._ensure_pool()
        # Convert strings to date and time objects for asyncpg
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        # Parse time strings (format: HH:MM or HH:MM:SS)
        try:
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
        except ValueError:
            start_time_obj = datetime.strptime(start_time, "%H:%M:%S").time()
        try:
            end_time_obj = datetime.strptime(end_time, "%H:%M").time()
        except ValueError:
            end_time_obj = datetime.strptime(end_time, "%H:%M:%S").time()
        
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO schedule_slots (date, start_time, end_time, address, location_latitude, location_longitude, required_employees, is_open)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, date_obj, start_time_obj, end_time_obj, address, location_latitude, location_longitude, required_employees, is_open)
            return row['id']

    async def delete_schedule_slot(self, slot_id: int):
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM schedule_slots WHERE id = $1", slot_id)
            # CASCADE will handle shifts deletion

    async def get_schedule_slots_by_date(self, date_str: str) -> List[Dict]:
        self._ensure_pool()
        # Convert string to date object for asyncpg
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, date, start_time, end_time, address, location_latitude, location_longitude, required_employees, is_open
                FROM schedule_slots
                WHERE date = $1
                ORDER BY start_time
            """, date_obj)
            return [dict(row) for row in rows]

    async def get_schedule_slots_by_range(self, start_date: str, end_date: str, employee_id: Optional[int] = None, only_open: bool = False, exclude_employee_id: Optional[int] = None) -> List[Dict]:
        self._ensure_pool()
        # Convert strings to date objects for asyncpg
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        async with self._pool.acquire() as conn:
            if employee_id:
                rows = await conn.fetch("""
                    SELECT s.id, s.date, s.start_time, s.end_time, s.address,
                           s.location_latitude, s.location_longitude, s.required_employees, s.is_open,
                           sh.employee_id, u.full_name
                    FROM schedule_slots s
                    LEFT JOIN shifts sh ON s.id = sh.slot_id AND sh.employee_id = $1
                    LEFT JOIN users u ON sh.employee_id = u.user_id
                    WHERE s.date BETWEEN $2 AND $3
                    ORDER BY s.date, s.start_time
                """, employee_id, start_date_obj, end_date_obj)
            else:
                if only_open:
                    # Get open slots that have available space (not fully booked)
                    # Exclude slots where the employee is already assigned (if exclude_employee_id is provided)
                    if exclude_employee_id:
                        rows = await conn.fetch("""
                            SELECT s.id, s.date, s.start_time, s.end_time, s.address,
                                   s.location_latitude, s.location_longitude, s.required_employees, s.is_open
                            FROM schedule_slots s
                            WHERE s.date BETWEEN $1 AND $2 
                            AND s.is_open = TRUE
                            AND (
                                SELECT COUNT(*) 
                                FROM shifts sh 
                                WHERE sh.slot_id = s.id
                            ) < s.required_employees
                            AND NOT EXISTS (
                                SELECT 1 
                                FROM shifts sh 
                                WHERE sh.slot_id = s.id AND sh.employee_id = $3
                            )
                            ORDER BY s.date, s.start_time
                        """, start_date_obj, end_date_obj, exclude_employee_id)
                    else:
                        rows = await conn.fetch("""
                            SELECT s.id, s.date, s.start_time, s.end_time, s.address,
                                   s.location_latitude, s.location_longitude, s.required_employees, s.is_open
                            FROM schedule_slots s
                            WHERE s.date BETWEEN $1 AND $2 
                            AND s.is_open = TRUE
                            AND (
                                SELECT COUNT(*) 
                                FROM shifts sh 
                                WHERE sh.slot_id = s.id
                            ) < s.required_employees
                            ORDER BY s.date, s.start_time
                        """, start_date_obj, end_date_obj)
                else:
                    rows = await conn.fetch("""
                        SELECT s.id, s.date, s.start_time, s.end_time, s.address,
                               s.location_latitude, s.location_longitude, s.required_employees, s.is_open,
                               sh.employee_id, u.full_name
                        FROM schedule_slots s
                        LEFT JOIN shifts sh ON s.id = sh.slot_id
                        LEFT JOIN users u ON sh.employee_id = u.user_id
                        WHERE s.date BETWEEN $1 AND $2
                        ORDER BY s.date, s.start_time
                    """, start_date_obj, end_date_obj)
            return [dict(row) for row in rows]

    async def update_slot_open_status(self, slot_id: int, is_open: bool):
        """Update slot open status"""
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            await conn.execute("""
                UPDATE schedule_slots 
                SET is_open = $1 
                WHERE id = $2
            """, is_open, slot_id)
    
    async def get_slot_assigned_count(self, slot_id: int) -> int:
        """Get count of employees assigned to a slot"""
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT COUNT(*) as count
                FROM shifts
                WHERE slot_id = $1
            """, slot_id)
            return row['count'] if row else 0
    
    async def get_slot_by_id(self, slot_id: int) -> Optional[Dict]:
        """Get slot information by ID"""
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, date, start_time, end_time, address,
                       location_latitude, location_longitude, required_employees, is_open
                FROM schedule_slots
                WHERE id = $1
            """, slot_id)
            return dict(row) if row else None
    
    async def get_user_display_name(self, user_id: int) -> str:
        """Get user display name"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return f"User {user_id}"
        if user.get('full_name'):
            return user['full_name']
        if user.get('username'):
            return f"@{user['username']}"
        return f"User {user_id}"
    
    async def assign_shift(self, slot_id: int, employee_id: int):
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Get slot info including required_employees
                slot = await conn.fetchrow("""
                    SELECT date, start_time, end_time, required_employees
                    FROM schedule_slots 
                    WHERE id = $1
                """, slot_id)
                
                if slot:
                    # Check if employee already has a shift at this time
                    existing = await conn.fetchrow("""
                        SELECT id FROM shifts
                        WHERE employee_id = $1 AND date = $2 AND
                        ((start_time <= $3 AND end_time > $3) OR (start_time < $4 AND end_time >= $4))
                    """, employee_id, slot['date'], slot['start_time'], slot['end_time'])
                    
                    if existing:
                        raise ValueError("Employee already has a shift at this time")
                    
                    # Check if slot is already fully booked
                    assigned_count = await conn.fetchval("""
                        SELECT COUNT(*) 
                        FROM shifts 
                        WHERE slot_id = $1
                    """, slot_id)
                    
                    slot_info = await conn.fetchrow("""
                        SELECT required_employees
                        FROM schedule_slots 
                        WHERE id = $1
                    """, slot_id)
                    
                    if slot_info:
                        required = slot_info['required_employees']
                        if assigned_count >= required:
                            raise ValueError(f"Слот уже полностью заполнен. Требуется {required} сотрудник(ов), уже назначено {assigned_count}.")
                    
                    await conn.execute("""
                        INSERT INTO shifts (slot_id, employee_id, date, start_time, end_time)
                        VALUES ($1, $2, $3, $4, $5)
                    """, slot_id, employee_id, slot['date'], slot['start_time'], slot['end_time'])
                    
                    # Remove overlapping free time slots for this employee
                    # Delete free time slots that overlap with the shift
                    await conn.execute("""
                        DELETE FROM free_time_slots
                        WHERE employee_id = $1 
                        AND date = $2
                        AND start_time < $3 
                        AND end_time > $4
                    """, employee_id, slot['date'], slot['end_time'], slot['start_time'])
                    
                    # Check if slot is fully booked and close it if needed
                    assigned_count = await conn.fetchval("""
                        SELECT COUNT(*) 
                        FROM shifts 
                        WHERE slot_id = $1
                    """, slot_id)
                    
                    slot_info = await conn.fetchrow("""
                        SELECT required_employees 
                        FROM schedule_slots 
                        WHERE id = $1
                    """, slot_id)
                    
                    if slot_info and assigned_count >= slot_info['required_employees']:
                        # Slot is fully booked, close it
                        await conn.execute("""
                            UPDATE schedule_slots 
                            SET is_open = FALSE 
                            WHERE id = $1
                        """, slot_id)

    async def get_employee_shifts(self, employee_id: int, start_date: str, end_date: str) -> List[Dict]:
        """Get employee shifts with slot details"""
        self._ensure_pool()
        # Convert strings to date objects for asyncpg
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        async with self._pool.acquire() as conn:
            # Debug: check if there are any shifts for this employee
            debug_rows = await conn.fetch("""
                SELECT sh.id, sh.slot_id, sh.employee_id, sh.date, sh.start_time, sh.end_time
                FROM shifts sh
                WHERE sh.employee_id = $1 AND sh.date BETWEEN $2 AND $3
            """, employee_id, start_date_obj, end_date_obj)
            import logging
            import sys
            logging.critical(f"DEBUG get_employee_shifts: employee_id={employee_id}, date_range={start_date}-{end_date}, raw_shifts_count={len(debug_rows)}")
            print(f"DEBUG get_employee_shifts: employee_id={employee_id}, date_range={start_date}-{end_date}, raw_shifts_count={len(debug_rows)}", file=sys.stderr, flush=True)
            for row in debug_rows:
                logging.critical(f"DEBUG raw shift: {dict(row)}")
                print(f"DEBUG raw shift: {dict(row)}", file=sys.stderr, flush=True)
            
            rows = await conn.fetch("""
                SELECT sh.date, sh.start_time, sh.end_time,
                       s.address, s.required_employees
                FROM shifts sh
                INNER JOIN schedule_slots s ON sh.slot_id = s.id
                WHERE sh.employee_id = $1 AND sh.date BETWEEN $2 AND $3
                ORDER BY sh.date, sh.start_time
            """, employee_id, start_date_obj, end_date_obj)
            return [dict(row) for row in rows]

    async def add_free_time_slot(self, employee_id: int, date_str: str, start_time: str, end_time: str):
        self._ensure_pool()
        # Convert strings to date and time objects for asyncpg
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        # Parse time strings (format: HH:MM or HH:MM:SS)
        try:
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
        except ValueError:
            start_time_obj = datetime.strptime(start_time, "%H:%M:%S").time()
        try:
            end_time_obj = datetime.strptime(end_time, "%H:%M").time()
        except ValueError:
            end_time_obj = datetime.strptime(end_time, "%H:%M:%S").time()
        
        async with self._pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO free_time_slots (employee_id, date, start_time, end_time)
                VALUES ($1, $2, $3, $4)
            """, employee_id, date_obj, start_time_obj, end_time_obj)
    
    async def delete_free_time_slot(self, free_time_id: int, employee_id: int):
        """Delete a free time slot by ID (only if it belongs to the employee)"""
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM free_time_slots
                WHERE id = $1 AND employee_id = $2
            """, free_time_id, employee_id)
            if result == "DELETE 0":
                raise ValueError("Свободное время не найдено или не принадлежит вам")
    
    async def get_employee_free_time(self, employee_id: int, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get free time slots for an employee"""
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            if start_date and end_date:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
                rows = await conn.fetch("""
                    SELECT id, date, start_time, end_time
                    FROM free_time_slots
                    WHERE employee_id = $1 AND date BETWEEN $2 AND $3
                    ORDER BY date, start_time
                """, employee_id, start_date_obj, end_date_obj)
            else:
                # Get all free time slots for employee
                rows = await conn.fetch("""
                    SELECT id, date, start_time, end_time
                    FROM free_time_slots
                    WHERE employee_id = $1
                    ORDER BY date, start_time
                """, employee_id)
            return [dict(row) for row in rows]
    
    async def remove_overlapping_free_time(self, employee_id: int, date_str: str, start_time: str, end_time: str):
        """Remove free time slots that overlap with assigned shift"""
        self._ensure_pool()
        # Convert strings to date and time objects for asyncpg
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        # Parse time strings
        try:
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
        except ValueError:
            start_time_obj = datetime.strptime(start_time, "%H:%M:%S").time()
        try:
            end_time_obj = datetime.strptime(end_time, "%H:%M").time()
        except ValueError:
            end_time_obj = datetime.strptime(end_time, "%H:%M:%S").time()
        
        async with self._pool.acquire() as conn:
            # Delete free time slots that overlap with the shift
            # Overlap condition: free_time_start < shift_end AND free_time_end > shift_start
            await conn.execute("""
                DELETE FROM free_time_slots
                WHERE employee_id = $1 
                AND date = $2
                AND start_time < $3 
                AND end_time > $4
            """, employee_id, date_obj, end_time_obj, start_time_obj)
    
    async def get_employees_with_free_time(self, date_str: str, start_time: str, end_time: str) -> List[Dict]:
        """Get employees who have free time that overlaps with the given time slot"""
        self._ensure_pool()
        # Convert strings to date and time objects for asyncpg
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        # Parse time strings
        try:
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
        except ValueError:
            start_time_obj = datetime.strptime(start_time, "%H:%M:%S").time()
        try:
            end_time_obj = datetime.strptime(end_time, "%H:%M").time()
        except ValueError:
            end_time_obj = datetime.strptime(end_time, "%H:%M:%S").time()
        
        async with self._pool.acquire() as conn:
            # Find employees with free time that overlaps with the slot
            # Overlap condition: free_time_start < slot_end AND free_time_end > slot_start
            rows = await conn.fetch("""
                SELECT DISTINCT u.user_id, u.full_name, u.username, ft.start_time as free_start, ft.end_time as free_end
                FROM users u
                INNER JOIN free_time_slots ft ON u.user_id = ft.employee_id
                WHERE u.is_admin = FALSE
                AND ft.date = $1
                AND ft.start_time < $2 
                AND ft.end_time > $3
                ORDER BY u.full_name
            """, date_obj, end_time_obj, start_time_obj)
            return [dict(row) for row in rows]

    async def get_available_employees_for_slot(self, slot_id: int) -> List[Tuple[int, str]]:
        self._ensure_pool()
        async with self._pool.acquire() as conn:
            # Get slot info
            slot = await conn.fetchrow("""
                SELECT date, start_time, end_time 
                FROM schedule_slots 
                WHERE id = $1
            """, slot_id)
            
            if not slot:
                return []
            
            # Get employees who don't have shifts at this time
            rows = await conn.fetch("""
                SELECT DISTINCT u.user_id, u.full_name
                FROM users u
                WHERE u.is_admin = FALSE
                AND u.user_id NOT IN (
                    SELECT employee_id FROM shifts
                    WHERE date = $1 AND
                    ((start_time <= $2 AND end_time > $2) OR (start_time < $3 AND end_time >= $3))
                )
                ORDER BY u.full_name
            """, slot['date'], slot['start_time'], slot['end_time'])
            
            return [(row['user_id'], row['full_name'] or f"User {row['user_id']}") for row in rows]

    async def calculate_salary(self, employee_id: int, start_date: str, end_date: str, rate_per_hour: float) -> Tuple[float, List[Dict]]:
        from datetime import time as time_type
        shifts = await self.get_employee_shifts(employee_id, start_date, end_date)
        total_hours = 0.0
        for shift in shifts:
            start_time = shift['start_time']
            end_time = shift['end_time']
            # PostgreSQL returns time objects directly, but handle strings too
            if isinstance(start_time, time_type):
                start = start_time
            elif isinstance(start_time, str):
                try:
                    start = datetime.strptime(start_time, "%H:%M:%S").time()
                except ValueError:
                    start = datetime.strptime(start_time, "%H:%M").time()
            else:
                start = datetime.strptime(str(start_time), "%H:%M:%S").time()
            
            if isinstance(end_time, time_type):
                end = end_time
            elif isinstance(end_time, str):
                try:
                    end = datetime.strptime(end_time, "%H:%M:%S").time()
                except ValueError:
                    end = datetime.strptime(end_time, "%H:%M").time()
            else:
                end = datetime.strptime(str(end_time), "%H:%M:%S").time()
            
            hours = (datetime.combine(date.today(), end) - datetime.combine(date.today(), start)).total_seconds() / 3600
            total_hours += hours
        salary = total_hours * rate_per_hour
        return salary, shifts
