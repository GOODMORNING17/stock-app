import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    transaction_db = db.execute("SELECT symbol, SUM(number) AS number, price FROM new WHERE user_id=? GROUP BY symbol", user_id)

    cash_db = db.execute("SELECT cash FROM users where id=?",user_id)
    cash = cash_db[0]["cash"]

    return render_template("index.html", database = transaction_db, cash = cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "GET":
        return render_template("buy.html")

    else:
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")

    if not symbol:
        return apology("must give symbol, 400")

    stock = lookup(symbol.upper())

    if stock == None:
        return apology("symbol doesnt exist, 400")

    if not shares:
        return apology("input number of shares, 400")

    if not shares.isdigit():
        return apology("you cannot purchase shares", 400)

    transaction_value = float(int(shares) * stock["price"])

    user_id  = session["user_id"]
    check_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id = user_id)
    check_cash = check_cash_db[0]["cash"]


    if check_cash < transaction_value :
        return apology("Not enough money, 400")

    Cash = check_cash - transaction_value

    db.execute("UPDATE users SET cash = ? WHERE id = ?", Cash, user_id)

    date = datetime.datetime.now()

    db.execute("INSERT INTO new (user_id, symbol, number, price, date) VALUES (?, ?, ?, ?, ?)", user_id, stock["symbol"], shares, stock["price"], date)

    return redirect("/")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_id = session["user_id"]

    transaction_db = db.execute("SELECT symbol, number, price, date FROM new WHERE user_id = ?", user_id)

    cash_db = db.execute("SELECT cash FROM users where id=?",user_id)
    cash = cash_db[0]["cash"]

    return render_template("history.html", database = transaction_db, cash = cash)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")

    else:
        symbol = request.form.get("symbol")

    if not symbol:
        return apology("must give symbol, 403")

    stock = lookup(symbol.upper())

    if stock == None:
        return apology("symbol doesnt exist, 403")

    return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "GET":
        return render_template("Register.html")

    else:
       username = request.form.get("username")
       password = request.form.get("password")
       confirmation = request.form.get("confirmation")

        # Ensure username was submitted
       if not username:
           return apology("must provide username", 400)

        # Ensure password was submitted
       if not password:
           return apology("must provide password", 400)

       if not confirmation:
           return apology("must provide confirm_password", 400)

       if password != confirmation:
           return apology("password confimation wrong", 400)

       hash = generate_password_hash(password)

       try:
           new_user = db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", username, hash)
       except:
           return apology("username already existed", 400)

       session["user_id"] = new_user

       return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method =="GET":
        user_id = session["user_id"]
        share_symbol = db.execute("SELECT symbol FROM new WHERE user_id = :id GROUP BY symbol", id = user_id)
        return render_template("sell.html", symbols = [row["symbol"] for row in share_symbol])

    else:
        symbol = request.form.get("symbol")
        number = int(request.form.get("number"))

    user_id  = session["user_id"]
    stock = lookup(symbol.upper())
    date = datetime.datetime.now()
    user_number_db = db.execute("SELECT number FROM new WHERE user_id = :id AND symbol = :symbol GROUP BY symbol", id = user_id, symbol = symbol)
    user_number = user_number_db[0]["number"]

    if stock == None:
        return apology("share doesnt exist, 403")

    if number > user_number:
        return apology("you dont own that many stocks, 403")

    db.execute("INSERT INTO new (user_id, symbol, number, price, date) VALUES(?, ?, ?, ?, ?)", user_id, stock["symbol"], (-1)*number, stock["price"], date)

    transaction_value = float(number * stock["price"])

    check_cash_db = db.execute("SELECT cash FROM users WHERE id = :id", id = user_id)
    check_cash = check_cash_db[0]["cash"]

    Cash = check_cash + transaction_value

    db.execute("UPDATE users SET cash = ? WHERE id = ?", Cash, user_id)

    return redirect("/")
