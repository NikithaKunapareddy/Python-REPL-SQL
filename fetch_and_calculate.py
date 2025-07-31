def fetch_all_bookings_for_user(username):
    """Fetch and explain all bookings for a given username. Returns total final price."""
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    c.execute('SELECT id FROM users WHERE username=?', (username,))
    user_row = c.fetchone()
    if not user_row:
        print(f"No user found with username '{username}'")
        conn.close()
        return 0.0
    user_id = user_row[0]
    c.execute('SELECT id FROM bookings WHERE user_id=?', (user_id,))
    booking_ids = [row[0] for row in c.fetchall()]
    if not booking_ids:
        print(f"No bookings found for user '{username}'")
        conn.close()
        return 0.0
    total = 0.0
    route_totals = {}
    for bid in booking_ids:
        print("\n==============================")
        # Fetch route_id for this booking
        c.execute('SELECT route_id FROM bookings WHERE id=?', (bid,))
        route_row = c.fetchone()
        if not route_row:
            continue
        route_id = route_row[0]
        # Fetch route details
        c.execute('SELECT origin, destination FROM routes WHERE id=?', (route_id,))
        route_info = c.fetchone()
        if not route_info:
            continue
        route_key = f"{route_info[0]} -> {route_info[1]}"
        final_price = fetch_and_explain_booking(bid)
        if final_price is not None:
            total += final_price
            if route_key not in route_totals:
                route_totals[route_key] = 0.0
            route_totals[route_key] += final_price
    print("\n==============================")
    for route_key, route_total in route_totals.items():
        print(f"Total price for route {route_key}: {route_total}")
    print(f"Total price for all bookings for user '{username}': {total}")
    conn.close()
    return total

import sqlite3

def fetch_and_explain_booking(booking_id):
    conn = sqlite3.connect('travel.db')
    c = conn.cursor()
    try:
        c.execute('SELECT user_id, route_id, price_paid, seat_number, booking_time, status, traveller_type FROM bookings WHERE id=?', (booking_id,))
        booking = c.fetchone()
        if not booking:
            print(f"No booking found with ID {booking_id}")
            return None
        user_id, route_id, price_paid, seat_number, booking_time, status, traveller_type = booking
    except sqlite3.OperationalError as e:
        if 'traveller_type' in str(e):
            c.execute('SELECT user_id, route_id, price_paid, seat_number, booking_time, status FROM bookings WHERE id=?', (booking_id,))
            booking = c.fetchone()
            if not booking:
                print(f"No booking found with ID {booking_id}")
                return None
            user_id, route_id, price_paid, seat_number, booking_time, status = booking
            traveller_type = 'adult'
        else:
            raise
    c.execute('SELECT origin, destination, base_price, seats_total, transport_type FROM routes WHERE id=?', (route_id,))
    route = c.fetchone()
    if not route:
        print(f"No route found for booking.")
        return None
    origin, destination, base_price, seats_total, transport_type = route
    c.execute('SELECT COUNT(*) FROM bookings WHERE route_id=? AND id<=?', (route_id, booking_id))
    booked_so_far = c.fetchone()[0]
    seats_left = seats_total - booked_so_far + 1
    c.execute('SELECT loyalty_points FROM users WHERE id=?', (user_id,))
    row = c.fetchone()
    loyalty_points = row[0] if row else 0
    demand_factor = 1 + (1 - seats_left / seats_total) * 0.5
    demand_factor_explanation = (
        f"Demand factor = 1 + (1 - seats_left / seats_total) * 0.5\n"
        f"              = 1 + (1 - {seats_left} / {seats_total}) * 0.5\n"
        f"              = 1 + ({1 - seats_left / seats_total:.2f}) * 0.5\n"
        f"              = {demand_factor:.2f}"
    )
    price_after_demand = round(base_price * demand_factor, 2)
    price_after_demand_explanation = (
        f"Price after demand = base_price * demand_factor\n"
        f"                  = {base_price} * {demand_factor:.2f}\n"
        f"                  = {price_after_demand}"
    )
    c.execute('''SELECT percentage FROM discounts WHERE (user_type=? OR user_type IS NULL OR user_type='') AND min_points<=? ORDER BY percentage DESC LIMIT 1''', (traveller_type, loyalty_points))
    discount_row = c.fetchone()
    discount = discount_row[0] if discount_row else 0
    child_discount_explanation = ""
    if traveller_type == 'child':
        price_after_demand_before = price_after_demand
        price_after_demand *= 0.5
        child_discount_explanation = (
            f"Traveller type is 'child', so 50% child discount applies.\n"
            f"Price after child discount = {price_after_demand_before} * 0.5 = {price_after_demand}"
        )
    final_price = round(price_after_demand * (1 - discount / 100), 2)
    discount_explanation = (
        f"Discount applied = {discount}%\n"
        f"Final price = price_after_demand * (1 - discount/100)\n"
        f"           = {price_after_demand} * (1 - {discount}/100)\n"
        f"           = {final_price}"
    )
    print(f"Booking ID: {booking_id}")
    print(f"Route: {origin} -> {destination} ({transport_type})")
    print(f"Base price: {base_price}")
    print(f"Seats total: {seats_total}")
    print(f"Seats left at booking: {seats_left}")
    print("\n--- Calculation Details ---")
    print(demand_factor_explanation)
    print("\n" + price_after_demand_explanation)
    if child_discount_explanation:
        print("\n" + child_discount_explanation)
    print("\n" + discount_explanation)
    print("--------------------------\n")
    print(f"Traveller type: {traveller_type}")
    print(f"User loyalty points: {loyalty_points}")
    print(f"Final price paid: {final_price}")
    print(f"Price recorded in booking: {price_paid}")
    print(f"Booking time: {booking_time}")
    print(f"Status: {status}")
    conn.close()
    return final_price

if __name__ == "__main__":
    print("Choose calculation mode:")
    print("1. By booking ID(s)")
    print("2. By username (all bookings for user)")
    mode = input("Enter 1 or 2: ").strip()
    if mode == '2':
        username = input("Enter username: ").strip()
        fetch_all_bookings_for_user(username)
    else:
        booking_ids_input = input("Enter booking ID(s) to explain calculation (comma-separated for group): ").strip()
        booking_ids = []
        for part in booking_ids_input.split(','):
            part = part.strip()
            if part.isdigit():
                booking_ids.append(int(part))
        if not booking_ids:
            print("No valid booking IDs entered.")
        else:
            total = 0.0
            for bid in booking_ids:
                print("\n==============================")
                final_price = fetch_and_explain_booking(bid)
                if final_price is not None:
                    total += final_price
            print("\n==============================")
            print(f"Total price for all bookings: {total}")
