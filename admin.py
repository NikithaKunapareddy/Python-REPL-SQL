import sqlite3
import getpass
import hashlib

def setup_database():
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        loyalty_points INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        origin TEXT NOT NULL,
        destination TEXT NOT NULL,
        departure_time TEXT NOT NULL,
        base_price REAL NOT NULL,
        seats_total INTEGER NOT NULL,
        seats_available INTEGER NOT NULL,
        transport_type TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        route_id INTEGER NOT NULL,
        seat_number TEXT,
        price_paid REAL NOT NULL,
        booking_time TEXT NOT NULL,
        status TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(route_id) REFERENCES routes(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS discounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        percentage REAL NOT NULL,
        user_type TEXT,
        min_points INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    print('Database setup complete.')

def add_user():
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    username = input('Username: ')
    password = input('Password: ')
    hashed = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed))
        conn.commit()
        print('User added successfully!')
    except sqlite3.IntegrityError:
        print('Username already exists!')
    conn.close()

def add_route():
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    origin = input('Origin: ')
    destination = input('Destination: ')
    departure_time = input('Departure time (YYYY-MM-DDTHH:MM:SS): ')
    base_price = float(input('Base price: '))
    seats_total = int(input('Total seats: '))
    transport_type = input('Transport type (flight/train/bus): ')
    c.execute('INSERT INTO routes (origin, destination, departure_time, base_price, seats_total, seats_available, transport_type) VALUES (?, ?, ?, ?, ?, ?, ?)',
              (origin, destination, departure_time, base_price, seats_total, seats_total, transport_type))
    conn.commit()
    conn.close()
    print('Route added successfully!')

def add_discount():
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    name = input('Discount name: ')
    percentage = float(input('Discount percentage: '))
    user_type = input('User type (or leave blank for all): ') or None
    min_points = int(input('Minimum loyalty points (0 if not required): '))
    c.execute('INSERT INTO discounts (name, percentage, user_type, min_points) VALUES (?, ?, ?, ?)',
              (name, percentage, user_type, min_points))
    conn.commit()
    conn.close()
    print('Discount added successfully!')

def main():
    while True:
        print('\nAdmin Menu:')
        print('1. Setup Database')
        print('2. Add User')
        print('3. Add Route')
        print('4. Add Discount')
        print('5. Exit')
        choice = input('Choose an option: ')
        if choice == '1':
            setup_database()
        elif choice == '2':
            add_user()
        elif choice == '3':
            add_route()
        elif choice == '4':
            add_discount()
        elif choice == '5':
            print('Goodbye!')
            break
        else:
            print('Invalid choice!')

if __name__ == "__main__":
    main()
