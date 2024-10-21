import sqlite3 #Library that helps to interact with a SQLite database
import os #Provides functionalities to handle file paths
import bleach #Helps "sanitizing" inputs to prevent HTML/JS injection attacks
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session #Core library for setting up web applications
from werkzeug.utils import secure_filename #Ensures file names are safe for saving to disk
from werkzeug.security import generate_password_hash, check_password_hash #Provides hashing functions for securely managing passwords

#Define the directory and path to the SQLite database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, '../db/database.db')

app = Flask(__name__)
app.secret_key = '1234567891234567'

#Connects the
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Retrieves all posts from the database
def get_all_posts():
    conn = get_db_connection()
    posts = conn.execute('''
        SELECT posts.id, posts.title, posts.content, posts.created, users.username 
        FROM posts 
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.created DESC
    ''').fetchall()
    conn.close()
    return posts

# Gets a single post from the database
def get_post(post_id):
    conn = get_db_connection()
    post = conn.execute('''
        SELECT posts.id, posts.title, posts.content, posts.created, posts.image, users.username 
        FROM posts 
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
    ''', (post_id,)).fetchone()
    conn.close()
    return post

#Gets all comments from a single posts based on the post's id
def get_comments(post_id):
    conn = get_db_connection()
    comments = conn.execute('''
        SELECT comments.id, comments.content, comments.created, users.username 
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = ?
        ORDER BY comments.created DESC
    ''', (post_id,)).fetchall()
    conn.close()
    return comments

#Gets a singular comment based on the comment's id
def get_comment(comment_id):
    conn = get_db_connection()
    comment = conn.execute('''
        SELECT comments.id, comments.content, comments.created, comments.post_id, users.username  
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.id = ?
    ''', (comment_id,)).fetchone()
    conn.close()
    return comment

#Validates if an uploaded file has an acceptable extension
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

#Retrieves the ID of the currently logged-in user by looking up their username in the session
def get_current_user_id():
    username = session.get('username')
    if username:
        conn = get_db_connection()
        user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user:
            return user['id']
    # If no user is logged in, the default user ID is "2"
    return 2


@app.route('/')
#The root route ('/') fetches all posts and renders the "index.html" template to display them
def index():
    posts = get_all_posts()
    return render_template('index.html', posts=posts)


@app.route('/create', methods=('GET', 'POST'))
#The page for creating new posts
def create():
    # On Post requesti, the form data (title and content) is sanitized and inserted into the database
    if request.method == 'POST':

        #These lines are safe from Cross Site Scripting because of the "bleach" library
        title = bleach.clean(request.form['title'])
        content = bleach.clean(request.form['content'])

        #These lines are vulnerable to Cross Site Scripting
        title = request.form['title']
        content = request.form['content']

        user_id = get_current_user_id()

        conn = get_db_connection()
        conn.execute('INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)',
                     (title, content, user_id))
        #If an image is uploaded, it's validated and saved securely.
        if 'image' in request.files:
            image = request.files['image']

            if image and allowed_file(image.filename):
                file_name, file_extension = os.path.splitext(image.filename)
                # The image is timestamped and updated in the post record
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                new_filename = f"{file_name}_{timestamp}{file_extension}"
                new_filename = secure_filename(new_filename)

                try:
                    image.save(os.path.join(app.root_path, 'static/images', new_filename))
                except OSError:
                    print(f"Error saving image file {new_filename}")

                conn.execute('UPDATE posts SET image = ? WHERE title = ?', (new_filename, title))
        #On a successful post, redirect back to the main page
        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('create.html')

@app.route('/delete_post/<int:post_id>')
#The page for deleting post/s
def delete_post(post_id):
    conn = get_db_connection()
    post = get_post(post_id)

    #Check if the post exists
    if not post:
        conn.close()
        return "Post not found."

    #Checks if the current user is allowed to delete the post
    if session.get('username') == post['username'] or session.get('is_admin'):
        conn.execute('DELETE FROM comments WHERE post_id = ?', (post_id,))
        #If the post contains an image, attempt to delete the image before dropping the post from the database
        if post['image']:
            try:
                os.remove(os.path.join(app.root_path, 'static/images', post['image']))
            except OSError:
                print(f"Error deleting image file {post['image']}")
        #Delete the post from the database
        conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()
        #Redirect back to the main pag upon deletion
        return redirect(url_for('index'))
    else:
        conn.close()
        return "You do not have permission to delete this post."


@app.route('/search', methods=['GET'])
#The page for searching for posts based on their names or content
def search():
    search_term = bleach.clean(request.args.get('search_term', ''))
    conn = get_db_connection()

    posts = conn.execute('''
        SELECT posts.id, posts.title, posts.content, posts.created, users.username 
        FROM posts 
        JOIN users ON posts.user_id = users.id
        WHERE posts.title LIKE ? OR posts.content LIKE ?
        ORDER BY posts.created DESC
    ''', ('%' + search_term + '%', '%' + search_term + '%')).fetchall()
    conn.close()

    #If no posts are found
    if not posts:
        #Return to the start menu with an empty list of posts
        return render_template('index.html', posts=[], search_term=search_term)
    else:
        #Return to the start menu with the relevant posts
        return render_template('index.html', posts=posts, search_term=search_term)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
#The page for showing a particular post based on its post id
def post(post_id):
    conn = get_db_connection()
    post = get_post(post_id)
    comments = get_comments(post_id)
    conn.close()

    return render_template('post.html', post=post, comments=comments)


@app.route('/add_comment/<int:post_id>', methods=['GET', 'POST'])
#Page for adding comments onto posts based on the post's id
def add_comment(post_id):
    comment_content = bleach.clean(request.form['comment_content'])
    user_id = get_current_user_id()

    conn = get_db_connection()
    conn.execute('INSERT INTO comments (content, post_id, user_id) VALUES (?, ?, ?)',
                 (comment_content, post_id, user_id))
    conn.commit()
    conn.close()

    return redirect(url_for('post', post_id=post_id))

@app.route('/delete_comment/<int:comment_id>', methods=['GET', 'POST'])
#Page for deleting a comment from a post based on the user's id
def delete_comment(comment_id):
    conn = get_db_connection()
    comment = get_comment(comment_id)

    #If the comment doesn't exist
    if not comment:
        conn.close()
        return "Comment not found."

    #Only delete the comment if the user made it, or they're an admin
    if session.get('username') == comment['username'] or session.get('is_admin'):
        conn.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
        conn.commit()
    else:
        conn.close()
        return "You do not have permission to delete this comment."

    conn.close()
    #Redirect back to the main page
    return redirect(url_for('post', post_id=comment['post_id']))

@app.route('/login', methods=['GET', 'POST'])
#Page for loging onto the website as a user
def login():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            #Sett the user's username and admin status
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            #Return to the main menu
            return redirect(url_for('index'))
        else:
            error = "Incorrect username or password. Please try again."
    #Return back to the same page with an error message
    return render_template('login.html', error=error)

@app.route('/logout')
#Page for logging out
def logout():
    #Remove the user from the session
    session.pop('username', None)
    session.pop('is_admin', None)
    #Return back to the main page
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
#Page for registering a new user
def register():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_pw = request.form['confirm_password']

        if bleach.clean(username) != username:
            error = "Username contains invalid characters. Please try again."
            return render_template('register.html', error=error)

        conn = get_db_connection()
        existing_user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()

        if existing_user:
            error = "Username already exists. Please choose a different username."
        elif password != confirm_pw:
            error = "Passwords do not match. Please try again."
        else:
            #Generate a hash of the password
            password_hash = generate_password_hash(password)
            #Add the new user's information into the database
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         (username, password_hash))

            conn.commit()
            conn.close()
            #Return to the login page
            return redirect(url_for('login'))

        conn.close()
    #Return back to the register page with an error message
    return render_template('register.html', error=error)

if __name__ == "__main__":
    app.secret_key = '1234567891234567'

    # app.config['SESSION_COOKIE_HTTPONLY'] = False

    app.run(debug=True)
