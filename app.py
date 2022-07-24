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
app.debug = True


def pack_ticker_direction(ticker, direction):
    return f'{ticker}_{direction}'


def unpack_ticker_direction(ticker_direction, ticker_only=False, dir_only=False):
    split = ticker_direction.split('_')
    if ticker_only:
        return split[0]
    elif dir_only:
        return split[1]
    else:
        return split


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
            cursor.execute(f'UPDATE users SET total_leader_votes = total_leader_votes + 1, register_time = register_time WHERE id = ?', (candidate,))
        except Exception as e:
            close_db(cursor, db)
            return f'Error: {e}'
        else:
            close_db(cursor, db)
            return f'Voted {"up" if up else "down"} successfully!'


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


def add_stock_db(ticker, description, userid, long=True):  # assumes ticker is not added yet, and userid is a leader, assumes ticker is upper()'ed
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'INSERT INTO stocks (ticker_direction, description, posted_by) VALUES (?, ?, ?)', (ticker + '_' + ('1' if long else '0'), description, userid))
        vote_stock_db(ticker + '_' + ('1' if long else '0'), userid)
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return f'Added {ticker} ({"long" if long else "short"}) successfully!'


def check_stock_exists(ticker_direction):
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT ticker_direction FROM stocks WHERE ticker_direction = ?', (ticker_direction,))
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
        cursor.execute(f'SELECT stocks.ticker_direction, stocks.description, stocks.votes, stocks.total_votes, users.username FROM stocks, users WHERE stocks.posted_by = users.id ORDER BY stocks.votes DESC')
        results = cursor.fetchall()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        stocks = [{'ticker': unpack_ticker_direction(stock[0], ticker_only=True), 'direction': unpack_ticker_direction(stock[0], dir_only=True), 'description': stock[1], 'votes': stock[2], 'total_votes': stock[3], 'posted_by': stock[4]} for stock in results]
        return stocks


def vote_stock_db(ticker_direction, voter, up=True):  # assumes ticker and voter is valid, assumes voter has not previously voted for this ticker
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'INSERT INTO stock_votes (ticker_direction, voter, direction) VALUES (?, ?, ?)', (ticker_direction, voter, 1 if up else -1))
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        try:
            cursor.execute(f'UPDATE stocks SET votes = votes {"+" if up else "-"} 1 WHERE ticker_direction = ?', (ticker_direction,))
            cursor.execute(f'UPDATE stocks SET total_votes = total_votes + 1 WHERE ticker_direction = ?', (ticker_direction,))
        except Exception as e:
            close_db(cursor, db)
            return f'Error: {e}'
        else:
            close_db(cursor, db)
            return f'Voted {"up" if up else "down"} {unpack_ticker_direction(ticker_direction, ticker_only=True)} ({"long" if unpack_ticker_direction(ticker_direction, dir_only=True) else "short"}) successfully!'


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


def check_stock_voted(ticker_direction, voter):  # assumes both userid and ticker is valid, checks if voter has voted for the ticker
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT direction FROM stock_votes WHERE ticker_direction = ? AND voter = ?', (ticker_direction, voter))
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
        stocks = get_stocks_db()
        for stock in stocks:
            stock['direction_text'] = 'long' if stock['direction'] else 'short'
        return render_template('index.html', stocks=stocks)
    else:
        return redirect(url_for('login'))


@app.route('/vote_stock', methods=['GET'])
def vote_stock():
    if session.get('logged_in', '') == gen_login_token(session):
        ticker = request.args.get('ticker')
        direction = int(request.args.get('direction'))
        up = int(request.args.get('up'))
        voter = int(session.get('userid'))
        ticker_direction = pack_ticker_direction(ticker, direction)
        if not check_stock_exists(ticker_direction):
            return f'Stock {ticker} ({"long" if direction else "short"}) does not exist! <a href="{url_for("index")}">Try again</a>'
        return vote_stock_db(ticker_direction, voter, up) + f' <a href="{url_for("index")}">Home</a>'
    else:
        return redirect(url_for('login'))


if __name__ == '__main__':
    serve(app, host='localhost', port=8080, threads=8, expose_tracebacks=True, asyncore_use_poll=True)
