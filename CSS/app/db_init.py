import sqlite3
import os
from time import sleep
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, '../db/database.db')
SCHEMA = os.path.join(BASE_DIR, '../db/schema.sql')

SECRET_KEY = '1234567891234567'

connection = sqlite3.connect(DATABASE)

with open(SCHEMA) as f:
    connection.executescript(f.read())

cursor = connection.cursor()
cursor.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
            ('admin', generate_password_hash('admin'), 1)
            )

admin_id = cursor.lastrowid

cursor.execute("INSERT INTO posts (title, content, user_id, image) VALUES (?, ?, ?, ?)",
            ('The very first post!', 'Yay, we finally created a blog website!! How do you like it so far?', admin_id, "firstpost.png")
            )

sleep(1)

cursor.execute("INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)",
            ('Does it also work without an image?', 'This is just a test post to see if I could create a post without uploading an image!', admin_id)
            )

cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)",
            ('guest', generate_password_hash('guestaccount'))
            )


cursor.execute("INSERT INTO comments (content, user_id, post_id) VALUES (?, ?, ?)",
            ("Let's go!", admin_id, 1))

cursor.execute("INSERT INTO comments (content, user_id, post_id) VALUES (?, ?, ?)",
            ("can't wait for this! x)", 2, 1))

cursor.execute("INSERT INTO comments (content, user_id, post_id) VALUES (?, ?, ?)",
            ("This is bad... the design sux!", 2, 1))


cursor.execute("INSERT INTO comments (content, user_id, post_id) VALUES (?, ?, ?)",
            ("seems like it worked to me", 2, 2))


connection.commit()
connection.close()