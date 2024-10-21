import sqlite3
import os
import bleach
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, '../db/database.db')

app = Flask(__name__)
app.secret_key = '1234567891234567'


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


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


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}


def get_current_user_id():
    username = session.get('username')
    if username:
        conn = get_db_connection()
        user = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user:
            return user['id']
    return 2


@app.route('/')
def index():
    posts = get_all_posts()
    return render_template('index.html', posts=posts)


@app.route('/create', methods=('GET', 'POST'))
def create():
    if request.method == 'POST':
        title = bleach.clean(request.form['title'])
        content = bleach.clean(request.form['content'])

        user_id = get_current_user_id()

        conn = get_db_connection()
        conn.execute('INSERT INTO posts (title, content, user_id) VALUES (?, ?, ?)',
                     (title, content, user_id))

        if 'image' in request.files:
            image = request.files['image']

            if image and allowed_file(image.filename):
                file_name, file_extension = os.path.splitext(image.filename)

                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                new_filename = f"{file_name}_{timestamp}{file_extension}"
                new_filename = secure_filename(new_filename)

                try:
                    image.save(os.path.join(app.root_path, 'static/images', new_filename))
                except OSError:
                    print(f"Error saving image file {new_filename}")

                conn.execute('UPDATE posts SET image = ? WHERE title = ?', (new_filename, title))

        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('create.html')

@app.route('/delete_post/<int:post_id>')
def delete_post(post_id):
    conn = get_db_connection()
    post = get_post(post_id)

    if not post:
        conn.close()
        return "Post not found."

    if session.get('username') == post['username'] or session.get('is_admin'):
        conn.execute('DELETE FROM comments WHERE post_id = ?', (post_id,))
        if post['image']:
            try:
                os.remove(os.path.join(app.root_path, 'static/images', post['image']))
            except OSError:
                print(f"Error deleting image file {post['image']}")
        conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    else:
        conn.close()
        return "You do not have permission to delete this post."


@app.route('/search', methods=['GET'])
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

    if not posts:
        return render_template('index.html', posts=[], search_term=search_term)
    else:
        return render_template('index.html', posts=posts, search_term=search_term)


@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post(post_id):
    conn = get_db_connection()
    post = get_post(post_id)
    comments = get_comments(post_id)
    conn.close()

    return render_template('post.html', post=post, comments=comments)


@app.route('/add_comment/<int:post_id>', methods=['GET', 'POST'])
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
def delete_comment(comment_id):
    conn = get_db_connection()

    comment = get_comment(comment_id)

    if not comment:
        conn.close()
        return "Comment not found."

    if session.get('username') == comment['username'] or session.get('is_admin'):
        conn.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
        conn.commit()

    else:
        conn.close()
        return "You do not have permission to delete this comment."

    conn.close()

    return redirect(url_for('post', post_id=comment['post_id']))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']

            return redirect(url_for('index'))
        else:
            error = "Incorrect username or password. Please try again."

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('index'))


@app.route('/register', methods=['GET', 'POST'])
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
            password_hash = generate_password_hash(password)

            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                         (username, password_hash))

            conn.commit()
            conn.close()

            return redirect(url_for('login'))

        conn.close()

    return render_template('register.html', error=error)

if __name__ == "__main__":
    app.secret_key = '1234567891234567'

    # app.config['SESSION_COOKIE_HTTPONLY'] = False

    app.run(debug=True)