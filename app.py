from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime, timedelta
import uuid
import logging

app = Flask(__name__)

# Secret Key for sessions
app.secret_key = 'your_secret_key_here'  # Make sure to change this for security

# Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Mahesh@123',
    'database': 'pay_later_service'
}

# Setting up basic logging
logging.basicConfig(level=logging.DEBUG)

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as e:
        logging.error(f"Database connection error: {e}")
        raise Exception("Database connection failed. Please try again later.")

@app.route('/')
def home():
    return render_template('/index.html')

@app.route("/user")
def user():
    return render_template("register_user.html")

@app.route('/register_user', methods=["POST"])
def register_user():
    try:
        name = request.form["name"]
        email = request.form["email"]
        password = request.form['password']
        hashed_password = generate_password_hash(password)  # Hash the password before storing it

        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("INSERT INTO users (name, email, credit_limit, balance_due, password) VALUES (%s, %s, %s, %s, %s)",
                       (name, email, 10000, 0, hashed_password))
        connection.commit()
        cursor.close()
        connection.close()

        return render_template('register_success.html')
    except Exception as e:
        logging.error(f"Error during user registration: {e}")
        return render_template('register_user.html', error="There was an issue during registration. Please try again.")

@app.route('/userlogin')
def userlogin():
    return render_template('userlogin.html')

@app.route('/userloginverify', methods=['GET', 'POST'])
def userloginverify():
    try:
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']

            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # Fetch user by email
            cursor.execute("SELECT id, name, password FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            connection.close()

            if user and check_password_hash(user['password'], password):  
                session['user_id'] = user['id']  # Store user_id in session
                session['user_name'] = user['name']  # Store user name in session (optional)
                return redirect(url_for('userdashboard'))  # Redirect to the dashboard page
            else:
                return render_template('userlogin.html', error="Invalid email or password")

        return render_template('userlogin.html')
    except Exception as e:
        logging.error(f"Error during user login: {e}")
        return render_template('userlogin.html', error="There was an issue during login. Please try again.")

@app.route('/userdashboard')
def userdashboard():
    try:
        if 'user_id' not in session:
            return redirect(url_for('userlogin'))  # Redirect to login page if not logged in
        
        return render_template('userdashboard.html')
    except Exception as e:
        logging.error(f"Error accessing user dashboard: {e}")
        return render_template('userdashboard.html', error="There was an issue accessing the dashboard. Please try again.")

@app.route('/logout')
def logout():
    try:
        session.clear()
        return render_template('index.html')  # Redirect to home page after logging out
    except Exception as e:
        logging.error(f"Error during logout: {e}")
        return redirect(url_for('index.html'), error="There was an issue logging out. Please try again.")

@app.route("/platform")
def registerPlatform1():
    return render_template('register_platform.html')

# Platform Registration
@app.route("/register_platform", methods=["POST"])
def register_platform():
    try:
        name = request.form["name"]
        bank_account = request.form["bank_account"]
        api_key = str(uuid.uuid4())[:12]
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("INSERT INTO platforms (name, bank_account, api_key) VALUES (%s, %s, %s)", (name, bank_account, api_key))
        connection.commit()
        cursor.close()
        connection.close()
        return f"Platform registered successfully! API Key: {api_key}"
    except Exception as e:
        logging.error(f"Error during platform registration: {e}")
        return render_template('register_platform.html', error="There was an issue registering the platform. Please try again.")

@app.route('/transaction1')
def transaction1():
    return render_template('transaction.html')

# API: Validate User
@app.route("/api/validate_user", methods=["POST"])
def validate_user():
    try:
        data = request.json
        user_id = data["user_id"]
        amount = data["amount"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT balance_due, credit_limit FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.close()
        connection.close()

        if not user or user['balance_due'] + amount > user['credit_limit']:
            return jsonify({"valid": False}), 400
        return jsonify({"valid": True}), 200
    except Exception as e:
        logging.error(f"Error validating user: {e}")
        return jsonify({"error": "An error occurred while validating the user. Please try again."}), 500

# Transaction
@app.route("/transaction", methods=["POST"])
def initiate_transaction():
    try:
        data = request.json
        user_id = data["user_id"]
        platform_id = data["platform_id"]
        amount = data["amount"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Validate user and platform
        cursor.execute("SELECT id, balance_due FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        cursor.execute("SELECT id FROM platforms WHERE id = %s", (platform_id,))
        platform = cursor.fetchone()

        if not user or not platform:
            cursor.close()
            connection.close()
            return jsonify({"error": "Invalid user or platform"}), 404

        service_tax = int(amount) * 0.03
        due_date = datetime.now() + timedelta(days=30)
        timestamp = datetime.now()

        # Insert transaction
        cursor.execute(
            "INSERT INTO transactions (user_id, platform_id, amount, service_tax, status, due_date, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (user_id, platform_id, amount, service_tax, "Pending", due_date, timestamp)
        )
        transaction_id = cursor.lastrowid

        # Update user's balance_due
        cursor.execute("UPDATE users SET balance_due = balance_due + %s WHERE id = %s", (amount, user_id))

        connection.commit()
        cursor.close()
        connection.close()

        return jsonify({"transaction_id": transaction_id}), 201
    except Exception as e:
        logging.error(f"Error during transaction: {e}")
        return jsonify({"error": "There was an issue processing the transaction. Please try again."}), 500

@app.route('/transaction_status1')
def transaction_status1():
    return render_template('transaction_status.html')

# View Transaction Status
@app.route("/transaction_status", methods=["GET"])
def transaction_status():
    try:
        transaction_id = request.args.get("transaction_id")
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT status, amount FROM transactions WHERE id = %s", (transaction_id,))
        transaction = cursor.fetchone()
        cursor.close()
        connection.close()

        if not transaction:
            return jsonify({"error": "Transaction not found"}), 404

        return jsonify({"status": transaction['status'], "amount": transaction['amount']}), 200
    except Exception as e:
        logging.error(f"Error fetching transaction status: {e}")
        return jsonify({"error": "An error occurred while fetching the transaction status. Please try again."}), 500

if __name__ == "__main__":
    app.run(debug=True)
