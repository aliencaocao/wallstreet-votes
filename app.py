import flask
from waitress import serve
from flask import Flask, render_template, redirect, request, url_for, session
import mariadb
import hashlib
import secrets
import logging

server_logger = logging.getLogger('waitress')
server_logger.setLevel(logging.DEBUG)

app = Flask(__name__)
app.secret_key = secrets.token_hex(512)


def connect_db(user='root', password='root', host='127.0.0.1', port=3306, database='wallstreet-votes', autocommit=True):
    try:
        db = mariadb.connect(user=user, password=password, host=host, port=port, database=database)
    except Exception as e:
        raise Exception(f'Error connecting to MariaDB: {e}')
    else:
        # print(f'Connected to MariaDB {database}')
        db.autocommit = autocommit
        return db


def close_db(cursor, db):
    cursor.close()
    db.close()


def register_db(username, password):  # does check for duplicate username
    password = hashlib.sha512(password.encode()).hexdigest()
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT username FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if user:
            close_db(cursor, db)
            return f'Error: username already exists! <a href="{url_for("register")}">Try again</a>'
        else:
            cursor.execute(f'INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e} <a href="{url_for("register")}">Try again</a>'
    else:
        close_db(cursor, db)
        return f'Registered successfully! You can <a href="{url_for("login")}">login</a> as {username} now.'


def login_db(username, password):
    password = hashlib.sha512(password.encode()).hexdigest()
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT id FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return bool(user)


def get_userid(username):  # username can be invalid
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT id FROM users WHERE username = ?', (username,))
        userid = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return userid[0] if userid else f'Error: username {username} not found'


def get_username(userid):  # userid can be invalid
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT username FROM users WHERE id = ?', (userid,))
        username = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return username[0] if username else f'Error: user ID {userid} not found'


def vote_leader_db(candidate, voter, up=True):  # assumes userid is valid and is not self, assumes voter has not previously voted for this candidate
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'INSERT INTO leader_votes (candidate, voter, direction) VALUES (?, ?, ?)', (candidate, voter, 1 if up else -1))
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        try:
            cursor.execute(f'UPDATE users SET leader_votes = leader_votes {"+" if up else "-"} 1, register_time = register_time WHERE id = ?', (candidate,))
        except Exception as e:
            close_db(cursor, db)
            return f'Error: {e}'
        else:
            close_db(cursor, db)
            return 'Voted successfully!'


def toggle_leader_db(userid):  # assumes userid is valid
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT is_leader FROM users WHERE id = ?', (userid,))
        user = cursor.fetchone()
        cursor.execute(f'UPDATE users SET is_leader = {"0" if user[0] else "1"}, register_time = register_time WHERE id = ?', (userid,))  # already is leader -> so demote, is not leader now -> so promote
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return f'{"Demoted" if user[0] else "Promoted"} {get_username(userid)}!'


def add_stock_db(ticker, description, userid):  # assumes ticker is not added yet, and userid is a leader
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'INSERT INTO stocks (ticker, description, posted_by) VALUES (?, ?, ?)', (ticker, description, userid))
        vote_stock_db(ticker, userid)
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return f'Added {ticker} successfully!'


def check_stock_exists(ticker):
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT ticker FROM stocks WHERE ticker = ?', (ticker,))
        stock = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return bool(stock)


def get_stocks_db():
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT stocks.ticker, stocks.description, stocks.votes, users.username FROM stocks, users WHERE stocks.posted_by = users.id ORDER BY stocks.votes DESC')
        results = cursor.fetchall()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        stocks = [{'ticker': stock[0], 'description': stock[1], 'votes': stock[2], 'posted_by': stock[4]} for stock in results]  # skips stock[3] because it's the userid
        return stocks


def vote_stock_db(ticker, voter, up=True):  # assumes ticker and voter is valid, assumes voter has not previously voted for this ticker
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'INSERT INTO stock_votes (ticker, voter, direction) VALUES (?, ?, ?)', (ticker, voter, 1 if up else -1))
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        try:
            cursor.execute(f'UPDATE stocks SET votes = votes {"+" if up else "-"} 1 WHERE ticker = ?', (ticker,))
        except Exception as e:
            close_db(cursor, db)
            return f'Error: {e}'
        else:
            close_db(cursor, db)
            return f'Voted {"up" if up else "down"} {ticker} successfully!'


def check_leader_voted(candidate, voter):  # assumes both userid is valid, checks if voter has voted for the candidate
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT direction FROM leader_votes WHERE candidate = ? AND voter = ?', (candidate, voter))
        votes = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        return votes[0] if votes else False  # returns 1 or -1 or False


def check_stock_voted(ticker, voter):  # assumes both userid and ticker is valid, checks if voter has voted for the ticker
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT direction FROM stock_votes WHERE ticker = ? AND voter = ?', (ticker, voter))
        votes = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        return votes[0] if votes else False  # returns 1 or -1 or False


def gen_login_token(session):
    userid = session.get('userid', ' ')
    username = session.get('username', ' ')
    return hashlib.sha256(f'{userid}{app.secret_key}{username}'.encode()).hexdigest()


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        r = login_db(username, password)  # returns boolean if no error, string if error
        if isinstance(r, bool):  # r is userid if success
            if r:
                session['userid'] = get_userid(username)
                session['username'] = username
                session['logged_in'] = gen_login_token(session)
                return redirect(url_for('index'))
            else:
                return f'Invalid username or password! <a href="{url_for("login")}">Try again</a>'
        else:
            return r  # r is error message here
    else:
        if session.get('logged_in', '') == gen_login_token(session):
            return redirect(url_for('index'))
        else:
            return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_pw = request.form['confirm_pw']
        if confirm_pw != password:
            return f'Passwords do not match! <a href="{url_for("register")}">Try again</a>'
        return register_db(username, password)
    else:
        if session.get('logged_in', '') == gen_login_token(session):
            return redirect(url_for('index'))
        else:
            return render_template('register.html')


@app.route('/logout', methods=['GET'])
def logout():
    session.pop('userid', None)
    session.pop('username', None)
    session.pop('logged_in', None)
    return redirect(url_for('login'))


@app.route('/', methods=['GET'])
def home():
    return redirect(url_for('index'))


@app.route('/index', methods=['GET'])
def index():
    if session.get('logged_in', '') == gen_login_token(session):
        return render_template('index.html')
    else:
        return redirect(url_for('login'))


if __name__ == '__main__':
    serve(app, host='localhost', port=8080, threads=8, expose_tracebacks=True, asyncore_use_poll=True)
