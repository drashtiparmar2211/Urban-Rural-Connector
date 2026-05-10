import sqlite3
import os

# Path to your main website database
main_db = 'instance/urc_database.db'

def migrate():
    if not os.path.exists(main_db):
        print("Main database not found! Run your main app.py once first to create the instance folder.")
        return

    conn = sqlite3.connect(main_db)
    cursor = conn.cursor()

    print("--- Starting Sync and Migration ---")

    # 1. Update existing Orders table with logistics columns (Safeguard)
    # This adds columns if they don't exist without deleting your data
    columns_to_add = [
        ("product_id", "INTEGER"),
        ("delivery_type", "TEXT"),
        ("delivery_address", "TEXT"),
        ("pickup_address", "TEXT"),
        ("driver_id", "INTEGER"),
        ("pickup_id", "TEXT")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to orders table.")
        except sqlite3.OperationalError:
            # Column already exists, skip it
            pass

    # 2. Create Drivers Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS drivers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL UNIQUE,
        vehicle_type TEXT NOT NULL,
        vehicle_num TEXT NOT NULL UNIQUE,
        gps_lat REAL, gps_lng REAL,
        is_available INTEGER DEFAULT 1,
        rating REAL DEFAULT 5.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 3. Create Verification OTPs Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS verification_otps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        otp_type TEXT NOT NULL,
        otp_code TEXT NOT NULL,
        is_used INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME NOT NULL
    )''')

    # 4. Insert/Reset Demo Drivers for Logistics Assignment
    try:
        # We ensure at least one driver is available for the process_payment route
        drivers = [
            ("Rajesh Kumar", "+919876543210", "truck", "GJ-01-AB-1234", 22.30, 73.20, 1),
            ("Suresh Patel", "+919876543211", "bike", "GJ-01-CD-5678", 22.32, 73.22, 1)
        ]
        cursor.executemany('''
            INSERT OR IGNORE INTO drivers(name, phone, vehicle_type, vehicle_num, gps_lat, gps_lng, is_available) 
            VALUES(?,?,?,?,?,?,?)
        ''', drivers)
        print("Logistics drivers are ready for assignment.")
    except Exception as e:
        print(f"Driver setup note: {e}")

    conn.commit()
    conn.close()
    print("--- Migration complete! Order structure and Transport tables are synced. ---")

if __name__ == "__main__":
    migrate()
