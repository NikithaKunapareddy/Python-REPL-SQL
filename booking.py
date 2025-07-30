
import sqlite3
import getpass
import hashlib
from datetime import datetime

def authenticate_user(username, password):
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    hashed = hashlib.sha256(password.encode()).hexdigest()
    c.execute('SELECT id FROM users WHERE username=? AND password=?', (username, hashed))
    user = c.fetchone()
    conn.close()
    return user[0] if user else None

def get_route_info(origin, destination):
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    c.execute('SELECT id, base_price, departure_time, transport_type FROM routes WHERE origin=? AND destination=?', (origin, destination))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'route_id': row[0],
            'base_price': row[1],
            'departure_time': row[2],
            'transport_type': row[3]
        }
    else:
        return None

def calculate_final_price(base_price, traveller_type='adult', user_id=None):
    price = base_price
    # Apply child discount
    if traveller_type == 'child':
        price *= 0.5
    # Apply best discount from discounts table
    if user_id is not None:
        conn = sqlite3.connect('travel.db')
        c = conn.cursor()
        # Get user loyalty points
        c.execute('SELECT loyalty_points FROM users WHERE id=?', (user_id,))
        user_row = c.fetchone()
        loyalty_points = user_row[0] if user_row else 0
        # Find best discount (highest percentage) for this user/traveller_type/points
        c.execute('''SELECT percentage FROM discounts WHERE (user_type=? OR user_type IS NULL OR user_type='') AND min_points<=? ORDER BY percentage DESC LIMIT 1''', (traveller_type, loyalty_points))
        discount_row = c.fetchone()
        if discount_row:
            discount = discount_row[0]
            price *= (1 - discount / 100)
        conn.close()
    return round(price, 2)

def book_ticket(user_id, route_id, seat_number=None, traveller_type='adult'):
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    c.execute('SELECT seats_available, base_price, seats_total FROM routes WHERE id=?', (route_id,))
    route = c.fetchone()
    if not route or route[0] <= 0:
        conn.close()
        return {'error': 'No seats available'}
    seats_left, base_price, seats_total = route
    demand_factor = 1 + (1 - seats_left / seats_total) * 0.5
    price_paid = round(base_price * demand_factor, 2)
    final_price = calculate_final_price(price_paid, traveller_type, user_id)
    booking_time = datetime.now().isoformat()
    c.execute('INSERT INTO bookings (user_id, route_id, seat_number, price_paid, booking_time, status) VALUES (?, ?, ?, ?, ?, ?)',
              (user_id, route_id, seat_number, final_price, booking_time, 'confirmed'))
    c.execute('UPDATE routes SET seats_available = seats_available - 1 WHERE id=?', (route_id,))
    conn.commit()
    booking_id = c.lastrowid
    conn.close()
    return {'booking_id': booking_id, 'price_paid': final_price, 'status': 'confirmed'}

def main():
    while True:
        print('=== Booking CLI ===')
        username = input('Username: ')
        password = input('Password: ')
        user_id = authenticate_user(username, password)
        if not user_id:
            print('Authentication failed. Try again.')
            continue
        print(f'Welcome, {username}!')

        while True:
            print('\n1. Book a single ticket')
            print('2. Book multiple tickets (group booking)')
            print('3. Logout')
            action = input('Choose an option: ').strip()
            if action == '3':
                break
            # Show all available routes
            conn = sqlite3.connect('travel.db')
            c = conn.cursor()
            c.execute('SELECT id, origin, destination, departure_time, base_price, transport_type FROM routes')
            routes = c.fetchall()
            if not routes:
                print('No routes available.')
                conn.close()
                break
            print('\nAvailable Routes:')
            for idx, r in enumerate(routes, 1):
                print(f"{idx}. {r[1]} -> {r[2]}, {r[5]}, Departure: {r[3]}, Price: ${r[4]:.2f}")
            while True:
                try:
                    choice = int(input('Select a route number to book: '))
                    if 1 <= choice <= len(routes):
                        break
                    else:
                        print('Invalid selection. Try again.')
                except ValueError:
                    print('Please enter a valid number.')
            selected_route = routes[choice - 1]
            route_id = selected_route[0]
            origin = selected_route[1]
            destination = selected_route[2]
            transport_type = selected_route[5]
            departure_time = selected_route[3]
            base_price = selected_route[4]
            conn.close()

            if action == '1':
                # Single ticket booking
                traveller_type = input('Traveller type (adult/child): ') or 'adult'
                print(f"\nTicket from {origin} to {destination} ({transport_type})")
                print(f"Departure: {departure_time}")
                print(f"Base price: ${base_price:.2f}")
                print(f"Traveller type: {traveller_type}")
                final_price = calculate_final_price(base_price, traveller_type, user_id)
                print(f"Final price: ${final_price:.2f}")
                book = input('Do you want to book this ticket? (y/n): ').strip().lower()
                if book == 'y':
                    result = book_ticket(user_id, route_id, None, traveller_type)
                    print('Booking result:', result)
                else:
                    print('Booking cancelled.')
            elif action == '2':
                # Group booking
                try:
                    num_tickets = int(input('How many tickets do you want to book? '))
                except ValueError:
                    print('Invalid number. Returning to menu.')
                    continue
                for i in range(num_tickets):
                    print(f'\nBooking ticket {i+1} of {num_tickets}')
                    traveller_type = input('Traveller type (adult/child): ') or 'adult'
                    print(f"Ticket from {origin} to {destination} ({transport_type})")
                    print(f"Departure: {departure_time}")
                    print(f"Base price: ${base_price:.2f}")
                    print(f"Traveller type: {traveller_type}")
                    final_price = calculate_final_price(base_price, traveller_type, user_id)
                    print(f"Final price: ${final_price:.2f}")
                    book = input('Do you want to book this ticket? (y/n): ').strip().lower()
                    if book == 'y':
                        result = book_ticket(user_id, route_id, None, traveller_type)
                        print('Booking result:', result)
                    else:
                        print('Booking cancelled.')
            else:
                print('Invalid option. Try again.')

        another = input('Log in as another user? (y/n): ').strip().lower()
        if another != 'y':
            print('Goodbye!')
            break

if __name__ == "__main__":
    main()
