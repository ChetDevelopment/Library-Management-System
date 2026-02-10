from flask import Flask, render_template, redirect, url_for, session, flash, request
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
import bcrypt
import os
from werkzeug.utils import secure_filename
from datetime import date
from datetime import datetime, timedelta
import MySQLdb.cursors
from extensions import mysql
from flask import session
from flask_wtf.csrf import CSRFProtect




app = Flask(__name__)


UPLOAD_FOLDER = 'static/avatars'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs('static/avatars', exist_ok=True)

# --- Database Config ---
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'library_management_system'
app.secret_key = 'your_secret_key'

# mysql is provided by extensions via mysql.connector compatibility.

# --- Forms ---
class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    id_card = StringField('ID Card', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    id_card = StringField('ID Card', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class AdminLoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class EditProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    id_card = StringField('ID Card', validators=[DataRequired()])
    password = PasswordField('New Password (optional)')
    submit = SubmitField('Update Profile')



def get_admin_id():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM admin WHERE id = %s", (session.get('admin_id'),))
    row = cur.fetchone()
    cur.close()
    return row[0] if row else None

# --- Routes ---
@app.route('/')
def home():
    return render_template('index.html')



# --- User Registration ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        id_card = form.id_card.data
        password = form.password.data
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        cursor = mysql.connection.cursor()
        cursor.execute(
            'INSERT INTO user_register (name, email, id_card, password) VALUES (%s, %s, %s, %s)',
            (name, email, id_card, hashed_password)
        )
        mysql.connection.commit()
        cursor.close()

        flash("Registration successful!", "success")
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

# --- User Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        id_card = form.id_card.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM user_register WHERE email=%s AND id_card=%s', (email, id_card))
        user = cursor.fetchone()
        cursor.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[4].encode('utf-8')):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            flash("Logged in successfully!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid login credentials.", "danger")
    return render_template('login.html', form=form)

# --- User Dashboard ---
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # --- User Info ---
    cursor.execute(
        'SELECT name, email, id_card, avatar FROM user_register WHERE id=%s',
        (session['user_id'],)
    )
    user = cursor.fetchone()
    user_avatar_url = url_for('static', filename='avatars/' + (user[3] or 'default.png'))

    # --- Stats ---
    cursor.execute('SELECT COUNT(*) FROM books')
    total_books = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM books WHERE status="available"')
    available_books = cursor.fetchone()[0]

    issued_books = total_books - available_books

    cursor.execute('SELECT COUNT(*) FROM user_register')
    total_members = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM books WHERE status="issued" AND due_date < CURDATE()')
    overdue_books = cursor.fetchone()[0]

    # --- Borrowed Books ---
    cursor.execute('''
        SELECT bh.id, b.id, b.title, bh.borrow_date, bh.due_date, b.status
        FROM borrow_history bh
        JOIN books b ON bh.book_id = b.id
        WHERE bh.user_id=%s AND bh.return_date IS NULL
    ''', (session['user_id'],))
    borrowed_books = []
    today = date.today()
    for borrow_id, book_id, title, borrow_date, due_date, status in cursor.fetchall():
        fine = (today - due_date).days if due_date and today > due_date else 0
        borrowed_books.append({
            'borrow_id': borrow_id,
            'book_id': book_id,
            'title': title,
            'borrow_date': borrow_date,
            'due_date': due_date,
            'status': status,
            'fine': fine
        })
    upcoming_due = sorted(
        [
            {
                'title': b['title'],
                'due_date': b['due_date'],
                'days_left': (b['due_date'] - today).days if b['due_date'] else None
            }
            for b in borrowed_books
            if b['due_date']
        ],
        key=lambda x: x['due_date']
    )[:3]

    # --- Borrow History ---
    cursor.execute('''
        SELECT b.id, b.title, bh.borrow_date, bh.return_date, bh.due_date, b.status
        FROM borrow_history bh
        JOIN books b ON bh.book_id = b.id
        WHERE bh.user_id=%s
    ''', (session['user_id'],))
    borrow_history = []
    user_fines = 0
    for book_id, title, borrow_date, return_date, due_date, status in cursor.fetchall():
        fine = 0
        if due_date:
            if return_date and return_date > due_date:
                fine = (return_date - due_date).days
            elif not return_date and today > due_date:
                fine = (today - due_date).days
            user_fines += fine
        borrow_history.append({
            'id': book_id,
            'title': title,
            'borrow_date': borrow_date,
            'return_date': return_date or '-',
            'status': status,
            'fine': fine
        })

    # --- Search Books ---
    query = request.args.get('query', '')
    active_tab = 'profile'
    search_results = []
    if query:
        like_query = f"%{query}%"
        cursor.execute('''
            SELECT id, title, author, category, isbn, status, copies
            FROM books
            WHERE title LIKE %s OR author LIKE %s OR category LIKE %s OR isbn LIKE %s
        ''', (like_query, like_query, like_query, like_query))
        search_results = [
            {'id': r[0], 'title': r[1], 'author': r[2], 'category': r[3],
             'isbn': r[4], 'status': r[5], 'copies': r[6]}
            for r in cursor.fetchall()
        ]
        active_tab = 'search'

    # --- Borrow Requests (User) ---
    cursor.execute("""
        SELECT br.id, br.book_title, br.author, br.request_date, br.urgency, br.status, br.admin_response
        FROM borrow_requests br
        WHERE br.user_id = %s
        ORDER BY br.request_date DESC
    """, (session['user_id'],))
    borrow_requests = [{
        'id': r[0],
        'book_title': r[1],
        'author': r[2],
        'request_date': r[3],
        'urgency': r[4],
        'status': (r[5].capitalize() if r[5] else 'Pending'),
        'admin_response': r[6]
    } for r in cursor.fetchall()]
    request_count = len(borrow_requests)

    # --- Notifications ---
    cursor.execute("""
        SELECT id, message, seen, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 50
    """, (session['user_id'],))
    notifications = cursor.fetchall()

    cursor.close()

    return render_template(
        'dashboard.html',
        user=user,
        user_avatar_url=user_avatar_url,
        total_books=total_books,
        available_books=available_books,
        issued_books=issued_books,
        total_members=total_members,
        overdue_books=overdue_books,
        borrowed_books=borrowed_books,
        borrow_history=borrow_history,
        user_fines=user_fines,
        search_results=search_results,
        notifications=notifications,
        borrow_requests=borrow_requests,
        request_count=request_count,
        upcoming_due=upcoming_due,
        active_tab=active_tab
    )

# --- View Profile ---
@app.route('/view-profile')
def view_profile():
    if 'user_id' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT name, email, id_card, avatar FROM user_register WHERE id=%s', (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()

    user_avatar_url = url_for('static', filename='avatars/' + (user[3] or 'default.png'))
    return render_template('view_profile.html', user=user, user_avatar_url=user_avatar_url)

# --- Edit Profile ---
@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        flash('Please login first.')
        return redirect(url_for('login'))

    form = EditProfileForm()
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT name, email, id_card, avatar FROM user_register WHERE id=%s', (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'GET':
        form.name.data = user[0]
        form.email.data = user[1]
        form.id_card.data = user[2]

    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        id_card = form.id_card.data
        password = form.password.data

        avatar_file = request.files.get('avatar')
        avatar_filename = user[3]
        if avatar_file and avatar_file.filename != '':
            filename = secure_filename(avatar_file.filename)
            upload_folder = os.path.join('static', 'avatars')
            os.makedirs(upload_folder, exist_ok=True)
            avatar_path = os.path.join(upload_folder, filename)
            avatar_file.save(avatar_path)
            avatar_filename = filename

        if password:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute(
                'UPDATE user_register SET name=%s, email=%s, id_card=%s, password=%s, avatar=%s WHERE id=%s',
                (name, email, id_card, hashed_password, avatar_filename, session['user_id'])
            )
        else:
            cursor.execute(
                'UPDATE user_register SET name=%s, email=%s, id_card=%s, avatar=%s WHERE id=%s',
                (name, email, id_card, avatar_filename, session['user_id'])
            )

        mysql.connection.commit()
        cursor.close()
        flash('Profile updated successfully!')
        return redirect(url_for('dashboard'))

    cursor.close()
    user_avatar_url = url_for('static', filename='avatars/' + (user[3] or 'default.png'))
    return render_template('edit_profile.html', form=form, user_avatar_url=user_avatar_url)

@app.route('/books', methods=['GET', 'POST'])
def books():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor(dictionary=True)  # dictionary cursor
    if request.method == 'POST':
        search = request.form['search']
        cursor.execute("""
            SELECT id, title, author, isbn, status, due_date 
            FROM books 
            WHERE title LIKE %s OR author LIKE %s OR isbn LIKE %s
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cursor.execute("SELECT id, title, author, isbn, status, due_date FROM books")
    
    books = cursor.fetchall()
    cursor.close()
    return render_template('books.html', books=books)

# --- Borrowed Books ---
@app.route('/borrowed_books')
def borrowed_books():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # Get all currently borrowed books for this user
    cursor.execute('''
        SELECT b.id, b.title, bh.borrow_date, bh.due_date, b.status
        FROM borrow_history bh
        JOIN books b ON bh.book_id = b.id
        WHERE bh.user_id = %s AND bh.return_date IS NULL
    ''', (session['user_id'],))

    borrowed_books_rows = cursor.fetchall()
    today = date.today()
    borrowed_books = []
    for row in borrowed_books_rows:
        due_date = row[3]
        is_overdue = bool(due_date and today > due_date)
        borrowed_books.append({
            'id': row[0],
            'title': row[1],
            'borrow_date': row[2],
            'due_date': due_date,
            'status': row[4],
            'is_overdue': is_overdue
        })

    cursor.close()

    return render_template('borrowed_books.html', borrowed_books=borrowed_books)

# --- Borrow request ---

@app.route('/borrow-requests')
def admin_borrow_requests():
    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT br.id, u.name AS user_name, br.book_title, br.author, br.request_date, br.status
        FROM borrow_requests br
        JOIN user_register u ON br.user_id = u.id
        WHERE (br.status IS NULL OR br.status = '' OR LOWER(br.status) = 'pending')
        ORDER BY br.request_date DESC
    """)
    requests = cursor.fetchall()
    cursor.close()

    return render_template('borrow_request.html', borrow_requests=requests)


@app.route('/approve-request/<int:request_id>', methods=['POST'])
def approve_request(request_id):
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "SELECT user_id, book_id, book_title FROM borrow_requests WHERE id=%s",
            (request_id,)
        )
        row = cursor.fetchone()
        if not row:
            flash("Request not found.", "warning")
            return redirect(url_for('admin_borrow_requests'))

        user_id, book_id, req_title = row[0], row[1], row[2]

        cursor.execute(
            """
            UPDATE borrow_requests
            SET status='approved'
            WHERE id=%s AND (status IS NULL OR status='' OR LOWER(status)='pending')
            """,
            (request_id,)
        )
        if cursor.rowcount == 0:
            flash("Request not found or already processed.", "warning")
            mysql.connection.rollback()
            return redirect(url_for('admin_borrow_requests'))

        if book_id:
            cursor.execute("SELECT title FROM books WHERE id=%s", (book_id,))
            book_row = cursor.fetchone()
            book_title = book_row[0] if book_row else (req_title or "your requested book")
        else:
            book_title = req_title or "your requested book"

        cursor.execute("""
            INSERT INTO notifications (user_id, message)
            VALUES (%s, %s)
        """, (user_id, f"Your borrow request for '{book_title}' was approved."))
        mysql.connection.commit()
        flash("Borrow request approved.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error approving request: {str(e)}", "danger")
    finally:
        cursor.close()

    return redirect(url_for('admin_borrow_requests'))


@app.route('/reject-request/<int:request_id>', methods=['POST'])
def reject_request(request_id):
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            "SELECT user_id, book_id, book_title FROM borrow_requests WHERE id=%s",
            (request_id,)
        )
        row = cursor.fetchone()
        if not row:
            flash("Request not found.", "warning")
            return redirect(url_for('admin_borrow_requests'))

        user_id, book_id, req_title = row[0], row[1], row[2]

        cursor.execute(
            """
            UPDATE borrow_requests
            SET status='rejected'
            WHERE id=%s AND (status IS NULL OR status='' OR LOWER(status)='pending')
            """,
            (request_id,)
        )
        if cursor.rowcount == 0:
            flash("Request not found or already processed.", "warning")
            mysql.connection.rollback()
            return redirect(url_for('admin_borrow_requests'))

        if book_id:
            cursor.execute("SELECT title FROM books WHERE id=%s", (book_id,))
            book_row = cursor.fetchone()
            book_title = book_row[0] if book_row else (req_title or "your requested book")
        else:
            book_title = req_title or "your requested book"

        cursor.execute("""
            INSERT INTO notifications (user_id, message)
            VALUES (%s, %s)
        """, (user_id, f"Your borrow request for '{book_title}' was rejected."))
        mysql.connection.commit()
        flash("Borrow request rejected.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error rejecting request: {str(e)}", "danger")
    finally:
        cursor.close()

    return redirect(url_for('admin_borrow_requests'))


@app.route('/collect-book/<int:request_id>', methods=['GET'])
def collect_book(request_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT br.user_id, br.book_id, b.title, b.status, b.copies
            FROM borrow_requests br
            JOIN books b ON br.book_id = b.id
            WHERE br.id=%s AND br.user_id=%s
        """, (request_id, session['user_id']))
        row = cursor.fetchone()
        if not row:
            flash("Request not found.", "danger")
            return redirect(url_for('dashboard'))

        user_id, book_id, book_title, status, copies = row

        cursor.execute("SELECT status, book_id, book_title FROM borrow_requests WHERE id=%s", (request_id,))
        req_row = cursor.fetchone()
        if not req_row or (req_row[0] and req_row[0].lower() != 'approved'):
            flash("This request is not approved yet.", "warning")
            return redirect(url_for('dashboard'))
        if not req_row[1]:
            flash("This request is not linked to a catalog book. Please contact admin.", "warning")
            return redirect(url_for('dashboard'))

        if copies is not None and copies <= 0:
            flash("This book is currently unavailable.", "warning")
            return redirect(url_for('dashboard'))

        # Borrow book: decrement copies, set status, create history
        cursor.execute("UPDATE books SET copies = copies - 1 WHERE id=%s AND copies > 0", (book_id,))
        cursor.execute("""
            UPDATE books
            SET status = 'issued'
            WHERE id=%s AND copies = 0
        """, (book_id,))

        borrow_date = date.today()
        due_date = borrow_date + timedelta(days=14)
        cursor.execute("""
            INSERT INTO borrow_history (user_id, book_id, borrow_date, due_date)
            VALUES (%s, %s, %s, %s)
        """, (user_id, book_id, borrow_date, due_date))

        cursor.execute("""
            INSERT INTO notifications (user_id, message)
            VALUES (%s, %s)
        """, (user_id, f"You collected '{book_title}'. Due: {due_date}"))

        # Mark request as completed
        cursor.execute("UPDATE borrow_requests SET status='completed' WHERE id=%s", (request_id,))

        mysql.connection.commit()
        flash("Book collected successfully.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error collecting book: {str(e)}", "danger")
    finally:
        cursor.close()

    return redirect(url_for('dashboard'))




# --- Borrow History ---
@app.route('/borrow-history')
def borrow_history():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT bh.id, bk.title, bh.borrow_date, bh.due_date, bh.return_date
        FROM borrow_history bh
        JOIN books bk ON bh.book_id = bk.id
        WHERE bh.user_id=%s
        ORDER BY bh.borrow_date DESC
    """, (session['user_id'],))
    rows = cursor.fetchall()
    borrow_history = [{
        'id': r[0],
        'title': r[1],
        'borrow_date': r[2],
        'due_date': r[3],
        'return_date': r[4],
    } for r in rows]
    total_borrowed = len(borrow_history)
    total_returned = sum(1 for r in borrow_history if r['return_date'])
    pending_returns = total_borrowed - total_returned
    cursor.close()

    return render_template(
        'borrow_history.html',
        borrow_history=borrow_history,
        total_borrowed=total_borrowed,
        total_returned=total_returned,
        pending_returns=pending_returns
    )


# --- Notifications ---
@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    # Fetch notifications for the logged-in user
    cursor.execute('SELECT id, message, seen FROM notifications WHERE user_id=%s ORDER BY id DESC', (session['user_id'],))
    notifications_list = cursor.fetchall()
    cursor.close()

    # Convert each row to a dictionary for easier access in Jinja2
    notifications_dict = []
    for n in notifications_list:
        notifications_dict.append({
            'id': n[0],
            'message': n[1],
            'seen': n[2]
        })

    return render_template('notifications.html', notifications=notifications_dict)

@app.route('/mark-seen/<int:notification_id>', methods=['POST'])
def mark_seen(notification_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    cursor.execute('UPDATE notifications SET seen=1 WHERE id=%s AND user_id=%s', (notification_id, session['user_id']))
    mysql.connection.commit()
    cursor.close()

    return redirect(url_for('notifications'))



# --- Logout ---
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

# --- Admin Login ---
@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    form = AdminLoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM admin WHERE email=%s', (email,))
        admin = cursor.fetchone()
        cursor.close()

        if admin:
            stored_password = admin[3]
            if stored_password.startswith("$2b$") or stored_password.startswith("$2a$"):
                if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                    session['admin_id'] = admin[0]
                    session['admin_name'] = admin[1]
                    flash("Admin login successful!", "success")
                    return redirect(url_for('admin_dashboard'))
                else:
                    flash("Incorrect password.", "danger")
            else:
                if password == stored_password:
                    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    cursor = mysql.connection.cursor()
                    cursor.execute('UPDATE admin SET password=%s WHERE id=%s', (hashed, admin[0]))
                    mysql.connection.commit()
                    cursor.close()
                    session['admin_id'] = admin[0]
                    session['admin_name'] = admin[1]
                    flash("Admin login successful!", "success")
                    return redirect(url_for('admin_dashboard'))
                else:
                    flash("Incorrect password.", "danger")
        else:
            flash("Admin not found.", "warning")
    return render_template('admin_login.html', form=form)

@app.route('/admin-logout')
def admin_logout():
    session.pop('admin_id', None)
    session.pop('admin_name', None)
    flash("Admin logged out successfully.", "success")
    return redirect(url_for('admin_login'))

@app.route('/reset-user-password/<int:user_id>', methods=['POST'])
def reset_user_password(user_id):
    # Check admin session
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        logging.warning("Unauthorized reset password attempt for user_id %d", user_id)
        return redirect(url_for('admin_login'))

    new_password = "user1234"  # In production, generate a random password
    try:
        # Hash password with a fixed work factor for consistent performance
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
        cursor = mysql.connection.cursor()
        cursor.execute('UPDATE user_register SET password = %s WHERE id = %s', (hashed_password, user_id))
        rows_affected = cursor.rowcount
        mysql.connection.commit()
        cursor.close()

        if rows_affected == 0:
            flash(f"No user found with ID {user_id} to reset password.", "danger")
            logging.warning("No user found for reset password, user_id %d", user_id)
        else:
            flash(f"User password reset to '{new_password}' for ID {user_id}", "success")
            logging.info("Password reset successfully for user_id %d", user_id)
    except Error as e:
        flash(f"Error resetting password: {str(e)}", "danger")
        logging.error("Database error resetting password for user_id %d: %s", user_id, str(e))
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f"Unexpected error resetting password: {str(e)}", "danger")
        logging.error("Unexpected error resetting password for user_id %d: %s", user_id, str(e))
        return redirect(url_for('admin_dashboard'))
    finally:
        if 'cursor' in locals():
            cursor.close()

    return redirect(url_for('admin_dashboard'))

# --- Admin Dashboard ---
@app.route('/admin-dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor()

    try:
        # ===== STATISTICS =====
        cursor.execute('SELECT COUNT(*) AS total FROM books')
        total_books = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) AS total FROM books WHERE status="available"')
        available_books = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) AS total FROM books WHERE status="issued"')
        issued_books = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) AS total FROM user_register')
        total_members = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM borrow_history
            WHERE return_date IS NULL AND due_date < CURDATE()
        """)
        overdue_books = cursor.fetchone()[0]

        # ===== BOOK LIST (PAGINATED) =====
        try:
            books_page = int(request.args.get('books_page', 1))
        except ValueError:
            books_page = 1
        books_page = max(1, books_page)
        books_limit = 40
        books_offset = (books_page - 1) * books_limit

        cursor.execute("""
            SELECT id, title, author, category, isbn, status, due_date
            FROM books
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """, (books_limit + 1, books_offset))
        books_tuples = cursor.fetchall()
        books_has_more = len(books_tuples) > books_limit
        books_tuples = books_tuples[:books_limit]
        books = [{
            'id': b[0],
            'title': b[1],
            'author': b[2],
            'category': b[3],
            'isbn': b[4],
            'status': b[5],
            'due_date': b[6]
        } for b in books_tuples]

        # ===== MEMBERS LIST =====
        cursor.execute('SELECT id, name, email, id_card FROM user_register')
        members_tuples = cursor.fetchall()
        members = [{
            'id': m[0],
            'name': m[1],
            'email': m[2],
            'id_card': m[3]
        } for m in members_tuples]

        # ===== BORROW REQUESTS =====
        cursor.execute("""
            SELECT br.id, u.name AS user_name, br.book_title, br.urgency, br.reason,
                   br.request_date, br.status
            FROM borrow_requests br
            JOIN user_register u ON br.user_id = u.id
            WHERE br.status='Pending'
            ORDER BY br.request_date DESC
        """)
        borrow_requests = [{
            'id': r[0],
            'user_name': r[1],
            'book_title': r[2],
            'urgency': r[3],
            'reason': r[4],
            'request_date': r[5],
            'status': r[6]
        } for r in cursor.fetchall()]

        # ===== BORROW HISTORY =====
        cursor.execute("""
            SELECT bh.id, u.name AS user_name, b.title AS book_title,
                   bh.borrow_date, bh.return_date, bh.due_date, b.status
            FROM borrow_history bh
            JOIN books b ON bh.book_id = b.id
            JOIN user_register u ON bh.user_id = u.id
            ORDER BY bh.borrow_date DESC
        """)
        borrowed = [{
            'id': bh[0],
            'user_name': bh[1],
            'book_title': bh[2],
            'borrow_date': bh[3],
            'return_date': bh[4],
            'due_date': bh[5],
            'status': bh[6]
        } for bh in cursor.fetchall()]

        # ===== OVERDUE INFO =====
        cursor.execute("""
            SELECT bh.id, u.name AS user_name, b.title AS book_title,
                   bh.due_date,
                   GREATEST(DATEDIFF(CURDATE(), bh.due_date), 0) * 0.5 AS fine_amount
            FROM borrow_history bh
            JOIN books b ON bh.book_id = b.id
            JOIN user_register u ON bh.user_id = u.id
            WHERE bh.return_date IS NULL AND bh.due_date < CURDATE()
        """)
        overdue_info = [{
            'borrow_id': o[0],
            'user_name': o[1],
            'book_title': o[2],
            'due_date': o[3],
            'fine_amount': o[4]
        } for o in cursor.fetchall()]

    except Exception as e:
        flash(f"Database error: {str(e)}", "danger")
        total_books = available_books = issued_books = total_members = overdue_books = 0
        books = members = borrow_requests = borrowed = overdue_info = []

    finally:
        cursor.close()

    return render_template(
        'dashboard_admin.html',
        admin_name=session.get('admin_name'),
        total_books=total_books,
        available_books=available_books,
        issued_books=issued_books,
        total_members=total_members,
        overdue_books=overdue_books,
        books=books,
        books_has_more=books_has_more,
        books_page=books_page,
        members=members,
        borrow_requests=borrow_requests,
        requests=borrow_requests,
        requests_has_more=False,
        borrowed=borrowed,
        overdue_info=overdue_info
    )

@app.route('/debug-admin')
def debug_admin():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT COUNT(*) AS total FROM books')
    result = cursor.fetchone()
    cursor.close()
    return f"Result: {result}, Type: {type(result)}"
    
@app.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
def edit_user_page(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name, email, id_card FROM user_register WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    if not user:
        flash("User not found", "danger")
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        id_card = request.form['id_card']
        cursor.execute("UPDATE user_register SET name=%s, email=%s, id_card=%s WHERE id=%s",
                       (name, email, id_card, user_id))
        mysql.connection.commit()
        cursor.close()
        flash("User updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    cursor.close()
    return render_template('edit_user.html', user=user)

@app.route('/delete-user/<int:user_id>', methods=['POST'])
def delete_user_page(user_id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM user_register WHERE id=%s", (user_id,))
    mysql.connection.commit()
    cursor.close()
    flash("User deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/add-book', methods=['GET', 'POST'])
def add_book():
    # --- Check admin login ---
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        # --- Get form data ---
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        category = request.form.get('category', '').strip()  # optional
        isbn = request.form.get('isbn', '').strip()
        status = request.form.get('status', 'available')

        # --- Simple validation ---
        if not title or not author or not isbn:
            flash("Title, Author, and ISBN are required.", "danger")
            return render_template('add_book.html')

        # --- Insert into database ---
        cursor = mysql.connection.cursor()
        cursor.execute(
            "INSERT INTO books (title, author, category, isbn, status) VALUES (%s, %s, %s, %s, %s)",
            (title, author, category, isbn, status)
        )
        mysql.connection.commit()
        cursor.close()

        flash("Book added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    # --- Render the add book form ---
    return render_template('add_book.html')

@app.route('/add-user', methods=['GET', 'POST'])
def add_user():
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        id_card = request.form['id_card']
        password = request.form['password']
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Handle avatar upload
        avatar_file = request.files.get('avatar')
        avatar_filename = None
        if avatar_file and avatar_file.filename != '':
            filename = secure_filename(avatar_file.filename)
            avatar_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            avatar_filename = filename

        cursor = mysql.connection.cursor()
        cursor.execute(
            'INSERT INTO user_register (name, email, id_card, password, avatar) VALUES (%s, %s, %s, %s, %s)',
            (name, email, id_card, hashed_password, avatar_filename)
        )
        mysql.connection.commit()
        cursor.close()

        flash("User added successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('add_user.html')

@app.route('/edit-user/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    cursor = mysql.connection.cursor()

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        id_card = request.form['id_card']

        cursor.execute(
            "UPDATE user_register SET name=%s, email=%s, id_card=%s WHERE id=%s",
            (name, email, id_card, user_id)
        )
        mysql.connection.commit()
        cursor.close()
        flash("User updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    cursor.execute("SELECT * FROM user_register WHERE id=%s", (user_id,))
    user = cursor.fetchone()
    cursor.close()

    return render_template('edit_user.html', user=user)

@app.route('/edit-book/<int:book_id>', methods=['GET', 'POST'])
def edit_book_page(book_id):
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, title, author, category, isbn, status FROM books WHERE id=%s", (book_id,))
    row = cursor.fetchone()
    cursor.close()

    # If the book is not found, redirect to dashboard
    if not row:
        flash("Book not found!", "danger")
        return redirect(url_for('admin_dashboard'))

    # Convert the row tuple into a dictionary for Jinja
    book = {
        'id': row[0],
        'title': row[1],
        'author': row[2],
        'category': row[3],
        'isbn': row[4],
        'status': row[5]
    }

    if request.method == 'POST':
        title = request.form['title']
        author = request.form['author']
        category = request.form.get('category')
        isbn = request.form.get('isbn')
        status = request.form.get('status', 'available')

        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE books 
            SET title=%s, author=%s, category=%s, isbn=%s, status=%s
            WHERE id=%s
        """, (title, author, category, isbn, status, book_id))
        mysql.connection.commit()
        cursor.close()

        flash("Book updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('edit_book.html', book=book)

@app.route('/delete-book/<int:book_id>', methods=['POST'])
def delete_book_page(book_id):
    # --- Check if admin is logged in ---
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor()

    # --- Optional: Check if the book exists before deleting ---
    cursor.execute("SELECT id, title FROM books WHERE id=%s", (book_id,))
    book = cursor.fetchone()
    if not book:
        cursor.close()
        flash("Book not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    # --- Delete the book ---
    cursor.execute("DELETE FROM books WHERE id=%s", (book_id,))
    mysql.connection.commit()
    cursor.close()

    flash(f"Book '{book[1]}' deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/borrow-requests-pending')
def borrow_requests():
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT br.id, u.name AS user_name, br.book_title, br.author, br.request_date, br.status
        FROM borrow_requests br
        JOIN user_register u ON br.user_id = u.id
        WHERE br.status = 'pending'
        ORDER BY br.request_date DESC
    """)
    requests = cursor.fetchall()
    cursor.close()

    return render_template('borrow_request.html', borrow_requests=requests)

@app.route('/reports')
def reports():
    if 'admin_id' not in session:
        flash("Please login as admin.", "warning")
        return redirect(url_for('admin_login'))

    cursor = mysql.connection.cursor()

    try:
        # --- Fetch Books ---
        cursor.execute('SELECT id, title, author, status FROM books')
        books_raw = cursor.fetchall()
        books = [
            (id_, title, author, status.strip().capitalize() if status else 'Available')
            for id_, title, author, status in books_raw
        ]

        # --- Fetch Total Borrowed Books (Active Borrows) ---
        cursor.execute("""
            SELECT COUNT(*) 
            FROM borrow_history 
            WHERE return_date IS NULL
        """)
        total_borrowed = cursor.fetchone()[0]

        # --- Fetch Total Reserved Books ---
        # Option 1: If using reservations table
        cursor.execute("""
            SELECT COUNT(*) 
            FROM reservations 
            WHERE status = 'active'
        """)
        total_reserved = cursor.fetchone()[0]

        # --- (Alternative) If using books.status ---
        # Comment out the above and uncomment this if you don't have a reservations table
        # total_reserved = sum(1 for book in books if book[3] == 'Reserved')

        # --- Fetch Analytics ---
        cursor.execute("""
            SELECT id, message, created_at, seen
            FROM admin_analytics
            WHERE admin_id = %s
            ORDER BY created_at DESC
            LIMIT 30
        """, (session['admin_id'],))
        analytics_raw = cursor.fetchall()
        analytics = [
            (a_id, msg, created_at.strftime('%b %d, %I:%M %p'), seen)
            for a_id, msg, created_at, seen in analytics_raw
        ]

    except Exception as e:
        flash(f"Error loading report: {str(e)}", "danger")
        return redirect(url_for('admin_login'))
    finally:
        cursor.close()

    return render_template(
        'reports.html',
        books=books,
        analytics=analytics,
        total_borrowed=total_borrowed,
        total_reserved=total_reserved  # New variable
    )

@app.route('/reserve-book/<int:book_id>', methods=['POST'])
def reserve_book(book_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT id, title, status FROM books WHERE id=%s", (book_id,))
        book = cursor.fetchone()
        if not book:
            flash("Book not found!", "danger")
            return redirect(url_for('dashboard'))
        if book[2].lower() not in ['available', 'reserved']:
            flash("This book cannot be reserved.", "warning")
            return redirect(url_for('dashboard'))

        cursor.execute("""
            UPDATE books 
            SET status='Reserved', reserved_by_user_id=%s 
            WHERE id=%s
        """, (session['user_id'], book_id))

        cursor.execute("""
            INSERT INTO notifications (user_id, message)
            VALUES (%s, %s)
        """, (session['user_id'], f"You reserved '{book[1]}' successfully."))

        admin_id = get_admin_id()
        if admin_id:
            cursor.execute("""
                INSERT INTO admin_analytics (admin_id, message)
                VALUES (%s, %s)
            """, (admin_id, f"User '{session.get('user_name', 'ID:'+str(session['user_id']))}' reserved '{book[1]}' (ID: {book_id})."))

        mysql.connection.commit()
        flash("Book reserved successfully!", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error reserving book: {str(e)}", "danger")
    finally:
        cursor.close()

    return redirect(url_for('dashboard'))

@app.route('/cancel-reservation/<int:book_id>', methods=['POST'])
def cancel_reservation(book_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            UPDATE books 
            SET status='Available', reserved_by_user_id=NULL 
            WHERE id=%s AND reserved_by_user_id=%s
        """, (book_id, session['user_id']))
        if cursor.rowcount == 0:
            flash("Reservation not found.", "warning")
        else:
            flash("Reservation cancelled.", "success")
        mysql.connection.commit()
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        cursor.close()
    return redirect(url_for('dashboard'))

@app.route('/export-reservations')
def export_reservations():
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT u.username, b.title
        FROM books b
        JOIN user_register u ON b.reserved_by_user_id = u.id
        WHERE b.status = 'Reserved'
    """)
    reservations = cursor.fetchall()
    cursor.close()
    output = "Username,Book Title\n"
    for r in reservations:
        output += f"{r[0]},{r[1]}\n"
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=reservations.csv"}
    )

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    cur = None
    try:
        cur = mysql.connection.cursor()

        # Handle Form Submission
        if request.method == 'POST':
            # Get form data
            max_borrow_days = request.form.get('max_borrow_days')
            fine_per_day = request.form.get('fine_per_day')
            open_time = request.form.get('open_time')
            close_time = request.form.get('close_time')
            contact_email = request.form.get('contact_email')

            # Server-side validation
            try:
                max_borrow_days = int(max_borrow_days)
                fine_per_day = float(fine_per_day)
                if max_borrow_days < 1 or max_borrow_days > 90:
                    raise ValueError("Maximum borrow days must be between 1 and 90")
                if fine_per_day < 0 or fine_per_day > 10:
                    raise ValueError("Fine per day must be between 0 and 10")
                if not contact_email or '@' not in contact_email:
                    raise ValueError("Invalid email format")
                if not open_time or not close_time:
                    raise ValueError("Open and close times are required")
            except ValueError as e:
                flash(str(e), 'danger')
                logging.error(f"Validation error: {str(e)}")
                return redirect(url_for('settings'))

            # Check if record exists
            try:
                cur.execute("SELECT id FROM system_settings WHERE id=1")
                existing = cur.fetchone()
            except Error as e:
                flash(f"Database error checking settings: {str(e)}", 'danger')
                logging.error(f"Database error: {str(e)}, SQL: {cur._last_executed if cur else 'No query'}")
                return redirect(url_for('settings'))

            # Prepare data for database
            data = (max_borrow_days, fine_per_day, open_time, close_time, contact_email)

            if existing:
                # Update existing settings
                cur.execute("""
                    UPDATE system_settings 
                    SET max_borrow_days=%s, fine_per_day=%s, open_time=%s, close_time=%s, contact_email=%s
                    WHERE id=1
                """, data)
            else:
                # Insert new record
                cur.execute("""
                    INSERT INTO system_settings 
                    (id, max_borrow_days, fine_per_day, open_time, close_time, contact_email)
                    VALUES (1, %s, %s, %s, %s, %s)
                """, data)

            mysql.connection.commit()
            flash("Settings updated successfully!", "success")
            logging.info("Settings updated successfully")
            return redirect(url_for('settings'))

        # Handle Page Load (GET)
        cur.execute("SELECT * FROM system_settings WHERE id=1")
        settings_data = cur.fetchone()

        # If no settings found, create a default record
        if not settings_data:
            default_data = (1, 7, 0.50, '08:00', '17:00', 'admin@library.com')
            cur.execute("""
                INSERT INTO system_settings 
                (id, max_borrow_days, fine_per_day, open_time, close_time, contact_email)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, default_data)
            mysql.connection.commit()
            logging.info("Created default settings record")
            cur.execute("SELECT * FROM system_settings WHERE id=1")
            settings_data = cur.fetchone()

        # Prepare settings dictionary
        settings = {
            'max_borrow_days': settings_data[1],
            'fine_per_day': float(settings_data[2]),  # Ensure float for display
            'open_time': settings_data[3],
            'close_time': settings_data[4],
            'contact_email': settings_data[5]
        }

        return render_template('settings.html', settings=settings)

    except Error as e:
        flash(f"Database error: {str(e)}", 'danger')
        logging.error(f"Database error in settings: {str(e)}, SQL: {cur._last_executed if cur else 'No query'}")
        return redirect(url_for('settings'))
    finally:
        if cur:
            cur.close()
@app.route('/settings/reset', methods=['POST'])
def reset_settings():
    cur = None
    try:
        cur = mysql.connection.cursor()
        default_data = (7, 0.50, '08:00', '17:00', 'admin@library.com', 1)
        cur.execute("""
            UPDATE system_settings 
            SET max_borrow_days=%s, fine_per_day=%s, open_time=%s, close_time=%s, contact_email=%s
            WHERE id=%s
        """, default_data)
        mysql.connection.commit()
        flash("Settings reset to defaults successfully!", "success")
        logging.info("Settings reset to defaults")
        return redirect(url_for('settings'))
    except Error as e:
        flash(f"Database error during reset: {str(e)}", 'danger')
        logging.error(f"Database error in reset_settings: {str(e)}, SQL: {cur._last_executed if cur else 'No query'}")
        return redirect(url_for('settings'))
    finally:
        if cur:
            cur.close()
@app.route('/search-books')
def search_books():
    query = request.args.get('query', '')
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT id, title, author, category, isbn, status, copies
        FROM books
        WHERE title LIKE %s OR author LIKE %s OR category LIKE %s OR isbn LIKE %s
    """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
    search_results = cursor.fetchall()
    cursor.close()

    return render_template(
        'dashboard.html',
        user=session.get('user'),  # fetch or pass user info
        user_avatar_url=session.get('user_avatar_url'),
        total_books=session.get('total_books'),
        available_books=session.get('available_books'),
        issued_books=session.get('issued_books'),
        overdue_books=session.get('overdue_books'),
        user_fines=session.get('user_fines'),
        borrowed_books=session.get('borrowed_books'),
        borrow_history=session.get('borrow_history'),
        notifications=session.get('notifications'),
        search_results=search_results
    )


# Show borrow form
@app.route('/borrow-form/<int:book_id>', methods=['GET', 'POST'])
def borrow_form(book_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # Fetch book safely
    cursor.execute("SELECT id, title, author, status, copies FROM books WHERE id=%s", (book_id,))
    book = cursor.fetchone()
    if not book:
        cursor.close()
        flash("Book not found!", "danger")
        return redirect(url_for('dashboard'))  # or 'home'

    # Check if book is available
    if book[3] != 'available':  # assuming column index 3 = status
        cursor.close()
        flash("This book is not available for borrowing.", "warning")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            # 1. Update book status and copies
            cursor.execute("UPDATE books SET copies = copies - 1 WHERE id=%s", (book_id,))
            cursor.execute("""
                UPDATE books 
                SET status = 'issued' 
                WHERE id=%s AND copies = 0
            """, (book_id,))

            # 2. Record borrow history
            borrow_date = date.today()
            due_date = borrow_date + timedelta(days=14)
            cursor.execute("""
                INSERT INTO borrow_history (user_id, book_id, borrow_date, due_date)
                VALUES (%s, %s, %s, %s)
            """, (session['user_id'], book_id, borrow_date, due_date))

            # 3. USER NOTIFICATION
            cursor.execute("""
                INSERT INTO notifications (user_id, message)
                VALUES (%s, %s)
            """, (session['user_id'], f"You successfully borrowed '{book[1]}'. Due: {due_date}"))

            # 4. ADMIN ANALYTICS ALERT
            admin_id = get_admin_id()
            if admin_id:
                cursor.execute("""
                    INSERT INTO admin_analytics (admin_id, message)
                    VALUES (%s, %s)
                """, (admin_id,
                      f"User '{session.get('user_name', 'ID:'+str(session['user_id']))}' "
                      f"borrowed '{book[1]}' (ID: {book_id}). Due: {due_date}"))

            mysql.connection.commit()
            flash("Book borrowed successfully!", "success")

        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error borrowing book: {str(e)}", "danger")
        finally:
            cursor.close()

        return redirect(url_for('dashboard'))

    cursor.close()
    return render_template('borrow_form.html', book=book)
       
@app.route('/add-balance', methods=['GET', 'POST'])
def add_balance():
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        amount = request.form['amount']
        try:
            amount = float(amount)
            if amount <= 0:
                flash("Amount must be greater than 0", "danger")
                return redirect(url_for('add_balance'))
        except ValueError:
            flash("Invalid amount", "danger")
            return redirect(url_for('add_balance'))

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE user_register SET balance = balance + %s WHERE id=%s",
                       (amount, session['user_id']))
        mysql.connection.commit()
        cursor.close()

        flash(f"${amount} added to your balance successfully!", "success")
        return redirect(url_for('dashboard'))

    return render_template('add_balance.html')


@app.route('/pay-fine/<int:borrow_id>', methods=['GET', 'POST'])
def pay_fine(borrow_id):    
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # Get borrow info
    cursor.execute("SELECT user_id, fine, return_date, due_date FROM borrow_history WHERE id=%s", (borrow_id,))
    borrow = cursor.fetchone()
    if not borrow:
        flash("Borrow record not found.", "danger")
        return redirect(url_for('dashboard'))

    user_id, fine, return_date, due_date = borrow

    # Only allow if fine > 0
    if fine <= 0:
        flash("No fine to pay.", "info")
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        amount = float(request.form['amount'])
        if amount < fine:
            flash(f"Amount must be at least ${fine}.", "warning")
            return redirect(url_for('pay_fine', borrow_id=borrow_id))

        # Update fine as paid
        cursor.execute("UPDATE borrow_history SET fine=0 WHERE id=%s", (borrow_id,))
        mysql.connection.commit()
        cursor.close()

        flash(f"Fine of ${fine} paid successfully!", "success")
        return redirect(url_for('dashboard'))

    cursor.close()
    return render_template("pay_fine.html", fine=fine, borrow_id=borrow_id)

# --- Return Book ---
# --- Return Book ---
# --- Return Book ---
@app.route('/return-book/<int:borrow_id>', methods=['GET', 'POST'])
def return_book(borrow_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # Get borrowed book info
    cursor.execute('''
        SELECT b.id, b.title, bh.borrow_date, bh.due_date, bh.return_date, b.status
        FROM borrow_history bh
        JOIN books b ON bh.book_id = b.id
        WHERE bh.id=%s AND bh.user_id=%s
    ''', (borrow_id, session['user_id']))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        flash("Book not found or already returned.", "danger")
        return redirect(url_for('dashboard'))

    book_id, book_title, borrow_date, due_date, return_date, book_status = row
    today = date.today()
    is_overdue = False
    fine = 0

    if due_date and today > due_date:
        is_overdue = True
        fine = (today - due_date).days

    if request.method == 'POST':
        # Mark book as returned
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            'UPDATE borrow_history SET return_date=%s, fine=%s WHERE id=%s',
            (now, fine, borrow_id)
        )
        cursor.execute('UPDATE books SET status="Available" WHERE id=%s', (book_id,))
        mysql.connection.commit()
        cursor.close()
        if fine > 0:
            flash(f'Book "{book_title}" returned late. Please pay fine.', 'warning')
            return redirect(url_for('pay_fine', borrow_id=borrow_id))
        flash(f'Book "{book_title}" has been returned successfully!', 'success')
        return redirect(url_for('dashboard'))

    cursor.close()
    # Render your custom return page
    return render_template(
        'return_book.html',  # <- your custom HTML file
        book_title=book_title,
        borrow_date=borrow_date,
        due_date=due_date,
        date_today=today,
        is_overdue=is_overdue,
        fine=fine
    )
# --- Renew Book ---
@app.route('/renew-book/<int:book_id>', methods=['GET', 'POST'])
def renew_book(book_id):
    if 'user_id' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    try:
        # Fetch the borrow record
        cursor.execute("""
            SELECT bh.id, bh.book_id, bh.user_id, b.title, bh.borrow_date, bh.due_date
            FROM borrow_history bh
            JOIN books b ON bh.book_id = b.id
            WHERE bh.book_id=%s AND bh.user_id=%s AND bh.return_date IS NULL
        """, (book_id, session['user_id']))
        borrow = cursor.fetchone()

        if not borrow:
            flash("Borrow record not found.", "danger")
            return redirect(url_for('dashboard'))

        if request.method == 'POST':
            new_due_date = date.today() + timedelta(days=14)  # extend by 14 days

            # Update due date
            cursor.execute("""
                UPDATE borrow_history
                SET due_date=%s
                WHERE id=%s
            """, (new_due_date, borrow[0]))

            # Add notification
            cursor.execute("""
                INSERT INTO notifications (user_id, message)
                VALUES (%s, %s)
            """, (session['user_id'], f"You renewed '{borrow[3]}'. New due date: {new_due_date}"))

            mysql.connection.commit()
            flash(f"Book renewed successfully! New due date: {new_due_date}", "success")
            return redirect(url_for('dashboard'))

        # GET request: show renewal confirmation
        return render_template('renew_book.html',
                               book_title=borrow[3],
                               current_due_date=borrow[5],
                               new_due_date=date.today() + timedelta(days=14))

    except Exception as e:
        flash(f"Error renewing book: {str(e)}", "danger")
        return redirect(url_for('dashboard'))

    finally:
        cursor.close()

@app.route('/submit-borrow-request/<int:book_id>', methods=['POST'])
def submit_borrow_request(book_id):
    if 'user_id' not in session:
        flash("You must login first.", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']
    urgency = request.form.get('urgency', 'Medium')
    reason = request.form.get('reason')
    notes = request.form.get('notes', '')
    request_date = date.today()

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO borrow_requests (user_id, book_id, urgency, reason, notes, request_date)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (user_id, book_id, urgency, reason, notes, request_date))
    mysql.connection.commit()
    cur.close()

    flash("Your borrow request has been submitted to the admin.", "success")
    return redirect(url_for('dashboard'))


@app.route('/submit-borrow-request', methods=['POST'])
def submit_borrow_request_from_form():
    if 'user_id' not in session:
        flash("You must login first.", "danger")
        return redirect(url_for('login'))

    user_id = session['user_id']
    book_title = request.form.get('book_title', '').strip()
    author = request.form.get('author', '').strip()
    isbn = request.form.get('isbn', '').strip()
    category = request.form.get('category', '').strip()
    urgency = request.form.get('urgency', 'Medium')
    needed_by = request.form.get('needed_by', '').strip()
    reason = request.form.get('reason')
    notes = request.form.get('notes', '')
    request_date = date.today()

    cur = mysql.connection.cursor()
    try:
        book_id = None
        if isbn:
            cur.execute("SELECT id FROM books WHERE isbn=%s LIMIT 1", (isbn,))
            row = cur.fetchone()
            book_id = row[0] if row else None

        if not book_id and book_title and author:
            cur.execute("SELECT id FROM books WHERE title=%s AND author=%s LIMIT 1", (book_title, author))
            row = cur.fetchone()
            book_id = row[0] if row else None

        if not book_id and book_title:
            cur.execute("SELECT id FROM books WHERE title=%s LIMIT 1", (book_title,))
            row = cur.fetchone()
            book_id = row[0] if row else None

        cur.execute("""
            INSERT INTO borrow_requests
            (user_id, book_id, book_title, author, isbn, category, urgency, reason, notes, needed_by, request_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, book_id, book_title, author, isbn, category,
            urgency, reason, notes, needed_by, request_date
        ))
        mysql.connection.commit()
        flash("Your borrow request has been submitted to the admin.", "success")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error submitting request: {str(e)}", "danger")
    finally:
        cur.close()

    return redirect(url_for('dashboard'))

@app.route('/admin/borrow-requests')
def admin_borrow_requests_pending():
    if 'admin_id' not in session:
        flash("You must login as admin.", "danger")
        return redirect(url_for('admin_login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT br.id, u.name as user_name, b.title as book_title, br.urgency,
               br.reason, br.notes, br.request_date, br.status
        FROM borrow_requests br
        JOIN users u ON br.user_id = u.id
        JOIN books b ON br.book_id = b.id
        ORDER BY br.request_date DESC
    """)
    requests = cur.fetchall()
    cur.close()
    return render_template('admin_borrow_requests.html', requests=requests)

@app.route('/mark-analytics-seen/<int:aid>', methods=['POST'])
def mark_analytics_seen(aid):
    """
    Mark a single admin_analytics entry as read.
    Called via AJAX when the admin clicks a "New" activity item.
    """
    # -------------------------------------------------
    # 1. Must be logged in as admin
    # -------------------------------------------------
    if 'admin_id' not in session:
        return '', 403  # Forbidden

    # -------------------------------------------------
    # 2. Update the row – only if it belongs to this admin
    # -------------------------------------------------
    try:
        cur = mysql.connection.cursor()
        cur.execute(
            """
            UPDATE admin_analytics
            SET seen = 1
            WHERE id = %s AND admin_id = %s
            """,
            (aid, session['admin_id'])
        )
        affected = cur.rowcount          # 1 if updated, 0 if not found/owned
        mysql.connection.commit()
    except Exception as e:
        mysql.connection.rollback()
        # Optional: log the error
        app.logger.error(f"Failed to mark analytics {aid} as seen: {e}")
        return '', 500  # Internal Server Error
    finally:
        cur.close()

    # -------------------------------------------------
    # 3. Return proper HTTP status
    # -------------------------------------------------
    return '', 204 if affected else 404   # 204 = No Content (success), 404 = not found


# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)
