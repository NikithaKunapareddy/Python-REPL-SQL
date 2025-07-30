import sqlite3

conn = sqlite3.connect('travel.db')
c = conn.cursor()

with open('db_output.txt', 'w', encoding='utf-8') as f:
    f.write("Users:\n")
    for row in c.execute('SELECT id, username FROM users'):
        f.write(str(row) + '\n')
    f.write("\nRoutes:\n")
    for row in c.execute('SELECT id, origin, destination, departure_time, base_price, seats_total, transport_type FROM routes'):
        f.write(str(row) + '\n')

conn.close()
