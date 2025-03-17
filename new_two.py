from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import os
import matplotlib.pyplot as plt
import google.generativeai as genai

app = Flask(__name__)
DB_FILE = "finance.db"

#  Configure Gemini AI API
GENAI_API_KEY = "AIzaSyDwYBSB6tfT2pZXVscnM7uY1HIJBLRwmVQ"  
genai.configure(api_key=GENAI_API_KEY)

#  Initialize database
def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE transactions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            date TEXT,
                            description TEXT,
                            category TEXT,
                            transaction_type TEXT,
                            amount REAL)''')
        conn.commit()
        conn.close()


    if not os.path.exists("static"):
        os.makedirs("static")

init_db() 

#  Home Page - Display Transactions
@app.route('/')
def index():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Fetch transactions
    cursor.execute("SELECT id, date, description, category, transaction_type, amount FROM transactions ORDER BY date DESC")
    transactions = cursor.fetchall()
    
    conn.close()


    transactions = [
        {"id": t[0], "date": t[1], "description": t[2], "category": t[3], "transaction_type": t[4], "amount": t[5]}
        for t in transactions
    ]

    # Calculate total income, expenses, and balance
    total_income = sum(t["amount"] for t in transactions if t["transaction_type"] == "income")
    total_expense = sum(t["amount"] for t in transactions if t["transaction_type"] == "expense")
    balance = total_income - total_expense

    return render_template('index.html', transactions=transactions, 
                           total_income=total_income, 
                           total_expense=total_expense, 
                           balance=balance)

# 🔹 Add Transaction Page
@app.route('/add', methods=["GET", "POST"])
def add():
    if request.method == "POST":
        date = request.form["date"]
        description = request.form["description"]
        category = request.form["category"]
        transaction_type = request.form["transaction_type"]
        amount = float(request.form["amount"])

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO transactions (date, description, category, transaction_type, amount) VALUES (?, ?, ?, ?, ?)",
                       (date, description, category, transaction_type, amount))
        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template("add_transaction.html")

# 🔹 Expense Analysis Page
@app.route('/analysis')
def analysis():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT category, SUM(amount) FROM transactions WHERE transaction_type='expense' GROUP BY category")
    expenses = cursor.fetchall()
    conn.close()

    if expenses:
        categories, amounts = zip(*expenses)


        if not os.path.exists("static"):
            os.makedirs("static")

        # Generate Pie Chart
        plt.figure(figsize=(6, 6))
        plt.pie(amounts, labels=categories, autopct="%1.1f%%", colors=["#ff9999", "#66b3ff", "#99ff99", "#ffcc99"])
        plt.title("Expense Breakdown by Category")
        plt.savefig("static/expense_chart.png")
        plt.close()
        chart_exists = True
    else:
        chart_exists = False

    total_expense = sum(amount for _, amount in expenses)

    return render_template("analysis.html", total_expense=total_expense, chart_exists=chart_exists)

# 🔹 AI Advice Page
conversation_history = []  # Store previous messages

@app.route('/ai_advice', methods=["GET", "POST"])
def ai_advice():
    global conversation_history  # Keep track of past messages

    if request.method == "POST":
        data = request.get_json()
        user_query = data.get("userQuery", "")

        if not user_query:
            return jsonify({"aiResponse": "Please enter a valid query."})

        # Fetch transaction data
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT date, description, category, transaction_type, amount FROM transactions ORDER BY date DESC LIMIT 5")
        transactions = cursor.fetchall()
        conn.close()

        transaction_history = "\n".join(
            [f"{t[0]} - {t[1]} ({t[2]}): {t[3]} ₹{t[4]}" for t in transactions]
        ) if transactions else "No transaction data available."


        conversation_history.append(f"User: {user_query}")

        # Keep only the last 5 messages to prevent excessive memory usage
        conversation_history = conversation_history[-5:]

        # AI prompt with context
        ai_prompt = f"""
        Previous Conversations:
        {"\n".join(conversation_history)}

        User's Financial Transactions:
        {transaction_history}

        Current Query: {user_query}

        Provide concise financial advice based on the conversation history and transactions. use bullet points to be more organized answer.
        """

        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(ai_prompt)
            ai_response = response.text if response and hasattr(response, 'text') else "No response received."

            conversation_history.append(f"AI: {ai_response}")

        except Exception as e:
            ai_response = f"Error: {str(e)}"

        return jsonify({"aiResponse": ai_response})

    return render_template("ai_advice.html")


#  Delete Transaction
@app.route('/delete/<int:id>', methods=["POST"])
def delete_transaction(id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

#  Run Flask App
if __name__ == '__main__':
    app.run(debug=True)
