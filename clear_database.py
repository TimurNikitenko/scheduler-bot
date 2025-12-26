#!/usr/bin/env python3
"""
Script to clear the database.
WARNING: This will delete ALL data from the database!
"""
import os
import sys
import asyncio
from dotenv import load_dotenv
from bot.database import Database

load_dotenv()

async def clear_database():
    """Clear all data from the database"""
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')
    db = Database(db_url=db_url)
    
    print("⚠️  WARNING: This will delete ALL data from the database!")
    print(f"Database URL: {db_url}")
    
    confirmation = input("\nType 'DELETE ALL' to confirm: ")
    
    if confirmation != "DELETE ALL":
        print("Operation cancelled.")
        return
    
    try:
        await db.init_pool()
        
        async with db._pool.acquire() as conn:
            async with conn.transaction():
                print("\nDeleting data...")
                
                # Delete in order to respect foreign key constraints
                # Delete shifts first (references schedule_slots and users)
                result = await conn.execute("DELETE FROM shifts")
                print(f"  Deleted shifts")
                
                # Delete free time slots (references users)
                result = await conn.execute("DELETE FROM free_time_slots")
                print(f"  Deleted free time slots")
                
                # Delete schedule slots
                result = await conn.execute("DELETE FROM schedule_slots")
                print(f"  Deleted schedule slots")
                
                # Delete users (employees and admins)
                result = await conn.execute("DELETE FROM users")
                print(f"  Deleted users")
        
        await db.close_pool()
        print("\n✅ Database cleared successfully!")
        
    except Exception as e:
        print(f"\n❌ Error clearing database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

async def clear_only_employees():
    """Clear only employees (non-admin users) and their related data"""
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/telegram_bot')
    db = Database(db_url=db_url)
    
    print("⚠️  WARNING: This will delete all employees and their data!")
    print("Admins will be preserved.")
    print(f"Database URL: {db_url}")
    
    confirmation = input("\nType 'DELETE EMPLOYEES' to confirm: ")
    
    if confirmation != "DELETE EMPLOYEES":
        print("Operation cancelled.")
        return
    
    try:
        await db.init_pool()
        
        async with db._pool.acquire() as conn:
            async with conn.transaction():
                print("\nDeleting employee data...")
                
                # Get employee IDs first
                rows = await conn.fetch("SELECT user_id FROM users WHERE is_admin = FALSE")
                employee_ids = [row['user_id'] for row in rows]
                
                if not employee_ids:
                    print("  No employees found.")
                    await db.close_pool()
                    return
                
                # Delete shifts for employees
                await conn.execute(
                    "DELETE FROM shifts WHERE employee_id = ANY($1::bigint[])",
                    employee_ids
                )
                print(f"  Deleted shifts for {len(employee_ids)} employees")
                
                # Delete free time slots for employees
                await conn.execute(
                    "DELETE FROM free_time_slots WHERE employee_id = ANY($1::bigint[])",
                    employee_ids
                )
                print(f"  Deleted free time slots for {len(employee_ids)} employees")
                
                # Delete employees
                result = await conn.execute("DELETE FROM users WHERE is_admin = FALSE")
                print(f"  Deleted {len(employee_ids)} employees")
        
        await db.close_pool()
        print("\n✅ Employees cleared successfully!")
        
    except Exception as e:
        print(f"\n❌ Error clearing employees: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--employees-only':
        asyncio.run(clear_only_employees())
    else:
        print("Usage:")
        print("  python clear_database.py              - Clear ALL data (users, shifts, slots)")
        print("  python clear_database.py --employees-only  - Clear only employees (keep admins)")
        print()
        choice = input("Choose option (1=all, 2=employees only): ")
        
        if choice == "1":
            asyncio.run(clear_database())
        elif choice == "2":
            asyncio.run(clear_only_employees())
        else:
            print("Invalid choice.")
