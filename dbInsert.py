# Connect to database

import sqlite3
file = 'database.db'
conn = sqlite3.connect(file)
cursor = conn.cursor()

# Delete a user (it will do nothing if username doesn't exist)

delete_query = "DELETE FROM `user` WHERE username = 'josh@vv.com'"
cursor.execute(delete_query)

# Determine length of database, so as to create appropriate id number

test_query = "SELECT * FROM USER"
all_users = cursor.execute(test_query).fetchall()
if all_users != []:
    last_user_id = int(all_users[-1][0])
else:
    last_user_id = 0

# This is the new user's info

insert_params = (last_user_id + 1, 'testusername2', 'testpassword2')

# Peform the insert (it will do nothing if username already exists)

insert_query = "INSERT INTO `user` (id, username, password) VALUES(?,?,?)"
cursor.execute(insert_query, insert_params)

# Save the changes and close the connection

conn.commit()
conn.close()
