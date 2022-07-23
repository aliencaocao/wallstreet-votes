import flask
from waitress import serve
from flask import Flask, render_template, request, url_for
import mariadb
import hashlib

app = Flask(__name__)


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


def register(username, password):  # does check for duplicate username
    password = hashlib.sha512(password.encode()).hexdigest()
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT username FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if user:
            close_db(cursor, db)
            return 'Error: username already exists!'
        else:
            cursor.execute(f'INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return f'Registered successfully! You can login as {username} now.'


def login(username, password):
    password = hashlib.sha512(password.encode()).hexdigest()
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT username, password FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return bool(user)


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


def vote_leader(candidate, voter, up=True):  # assumes userid is valid and is not self, assumes voter has not previously voted for this candidate
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


def toggle_leader(userid):  # assumes userid is valid
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT id, is_leader FROM users WHERE id = ?', (userid,))
        user = cursor.fetchone()
        cursor.execute(f'UPDATE users SET is_leader = {"0" if user[1] else "1"}, register_time = register_time WHERE id = ?', (userid,))  # already is leader -> so demote, is not leader now -> so promote
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        return f'{"Demoted" if user[1] else "Promoted"} {get_username(userid)}!'


def add_stock(ticker, description, userid):  # assumes ticker is not added yet, and userid is a leader
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'INSERT INTO stocks (ticker, description, posted_by) VALUES (?, ?, ?)', (ticker, description, userid))
        vote_stock(ticker, userid)
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


def get_stocks():
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT stocks.ticker, stocks.description, stocks.votes, stocks.posted_by, users.username FROM stocks, users WHERE stocks.posted_by = users.id ORDER BY stocks.votes DESC')
        results = cursor.fetchall()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        close_db(cursor, db)
        stocks = [{'ticker': stock[0], 'description': stock[1], 'votes': stock[2], 'posted_by': stock[4]} for stock in results]  # skips stock[3] because it's the userid
        return stocks


def vote_stock(ticker, voter, up=True):  # assumes ticker and voter is valid, assumes voter has not previously voted for this ticker
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
        cursor.execute(f'SELECT candidate, voter, direction FROM leader_votes WHERE candidate = ? AND voter = ?', (candidate, voter))
        votes = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        if votes:
            return votes[2]  # returns 1 or -1
        else:
            return False


def check_stock_voted(ticker, voter):  # assumes both userid and ticker is valid, checks if voter has voted for the ticker
    db = connect_db()
    cursor = db.cursor()
    try:
        cursor.execute(f'SELECT ticker, voter, direction FROM stock_votes WHERE ticker = ? AND voter = ?', (ticker, voter))
        votes = cursor.fetchone()
    except Exception as e:
        close_db(cursor, db)
        return f'Error: {e}'
    else:
        if votes:
            return votes[2]  # returns 1 or -1
        else:
            return False


print(register('test', 'test'))
print(get_stocks())


