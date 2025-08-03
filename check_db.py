import sqlite3

conn = sqlite3.connect('travel.db')
c = conn.cursor()

print('Tables in database:')
for table in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    print(f"- {table[0]}")

print('\nChecking if bookings table exists...')
tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

if 'bookings' in tables:
    print('\nBookings table schema:')
    for col in c.execute('PRAGMA table_info(bookings)').fetchall():
        print(f"  {col}")
    
    print('\nSample bookings:')
    for booking in c.execute('SELECT * FROM bookings LIMIT 5').fetchall():
        print(f"  {booking}")
else:
    print('Bookings table does not exist - will create it')
    # Create bookings table
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        route_id INTEGER,
        booking_date TEXT,
        final_price REAL,
        traveller_type TEXT DEFAULT 'adult',
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(route_id) REFERENCES routes(id)
    )''')
    conn.commit()
    print('Created bookings table')

conn.close()
print('Database check complete!')
