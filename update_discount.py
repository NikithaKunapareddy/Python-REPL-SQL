import sqlite3

conn = sqlite3.connect('travel.db')
c = conn.cursor()

# Update all discounts above 50% to 50%
c.execute('UPDATE discounts SET percentage=50 WHERE percentage > 50')
conn.commit()
print('All discounts above 50% have been updated to 50%.')
conn.close()
