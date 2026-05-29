from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_mail import Mail, Message
from functools import wraps
import uuid
from datetime import datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Fundraising database
fundraising_db_path = "fundraising.db"
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{fundraising_db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
fund_db = SQLAlchemy(app)

# Contact messages database
messages_db_path = "messages.db"
messages_app = Flask(__name__)
messages_app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{messages_db_path}"
messages_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
messages_db = SQLAlchemy(messages_app)

# Flask mail config
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'ecosphereofficial.ph@gmail.com'
app.config['MAIL_PASSWORD'] = 'dyig yire yngw fnoj'
app.config['MAIL_DEFAULT_SENDER'] = ('EcoSphere', 'ecosphereofficial.ph@gmail.com')
mail = Mail(app)

FUNDRAISING_GOAL = 1000000000

# ── ADMIN CREDENTIALS ──────────────────────────────────────────────────────────
ADMIN_USERNAME = "ecosphere_admin"
ADMIN_PASSWORD = "EcoSphere@2026!"

# Helper function
def generate_reference_code():
    return "ECO-" + uuid.uuid4().hex[:10].upper()

# Admin login required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash("Please log in to access the admin panel.", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# ── MODELS ─────────────────────────────────────────────────────────────────────
class User(fund_db.Model):
    id = fund_db.Column(fund_db.Integer, primary_key=True)
    firstname = fund_db.Column(fund_db.String(50), nullable=False)
    lastname = fund_db.Column(fund_db.String(50), nullable=False)
    contact = fund_db.Column(fund_db.String(15), unique=True, nullable=False)
    email = fund_db.Column(fund_db.String(100), unique=True, nullable=False)
    transactions = fund_db.relationship('Transaction', backref='user', lazy=True)
    emails = fund_db.relationship('Email', backref='user', lazy=True)

class Transaction(fund_db.Model):
    id = fund_db.Column(fund_db.Integer, primary_key=True)
    user_id = fund_db.Column(fund_db.Integer, fund_db.ForeignKey('user.id'), nullable=False)
    amount = fund_db.Column(fund_db.Float, nullable=False)
    mode_of_payment = fund_db.Column(fund_db.String(20), nullable=False)
    transaction_number = fund_db.Column(fund_db.String(50), unique=True, nullable=False)
    reference_number = fund_db.Column(fund_db.String(50), unique=True, nullable=False)
    approval_status = fund_db.Column(fund_db.String(20), nullable=False, default="pending")
    created_at = fund_db.Column(fund_db.DateTime, default=datetime.utcnow)
    reviewed_at = fund_db.Column(fund_db.DateTime, nullable=True)
    emails = fund_db.relationship('Email', backref='transaction', lazy=True)

class Email(fund_db.Model):
    id = fund_db.Column(fund_db.Integer, primary_key=True)
    user_id = fund_db.Column(fund_db.Integer, fund_db.ForeignKey('user.id'), nullable=False)
    transaction_id = fund_db.Column(fund_db.Integer, fund_db.ForeignKey('transaction.id'), nullable=False)
    sent_at = fund_db.Column(fund_db.DateTime, default=datetime.utcnow)
    status = fund_db.Column(fund_db.String(10), nullable=False)

class MessageDB(messages_db.Model):
    id = messages_db.Column(messages_db.Integer, primary_key=True)
    name = messages_db.Column(messages_db.String(100), nullable=False)
    email = messages_db.Column(messages_db.String(100), nullable=False)
    phone = messages_db.Column(messages_db.String(20))
    subject = messages_db.Column(messages_db.String(200), nullable=False)
    message = messages_db.Column(messages_db.Text, nullable=False)

# Create / migrate databases
with app.app_context():
    fund_db.create_all()
    # Add new columns to existing DB if upgrading from old version
    try:
        with fund_db.engine.connect() as conn:
            conn.execute(fund_db.text(
                "ALTER TABLE transaction ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'"
            ))
            conn.commit()
    except Exception:
        pass
    try:
        with fund_db.engine.connect() as conn:
            conn.execute(fund_db.text(
                "ALTER TABLE transaction ADD COLUMN reviewed_at DATETIME"
            ))
            conn.commit()
    except Exception:
        pass

with messages_app.app_context():
    messages_db.create_all()

# ── STATIC PAGES ───────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/sdg')
def sdg():
    return render_template('sdg.html')

@app.route('/projects')
def projects():
    return render_template('projects.html')

@app.route('/aboutus')
def aboutus():
    return render_template('aboutus.html')

# ── CONTACT FORM ───────────────────────────────────────────────────────────────
@app.route("/send_message", methods=["POST"])
def send_message():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    subject = request.form.get("subject", "").strip()
    message_text = request.form.get("message", "").strip()

    if not name or not email or not subject or not message_text:
        flash("Please fill out all required fields!", "error")
        return redirect(url_for("aboutus") + "#Contacts")

    new_msg = MessageDB(name=name, email=email, phone=phone, subject=subject, message=message_text)
    with messages_app.app_context():
        messages_db.session.add(new_msg)
        messages_db.session.commit()

    flash("Your message has been sent successfully!", "success")
    return redirect(url_for("aboutus") + "#Contacts")

# ── DONATION (public fundraising page) ────────────────────────────────────────
@app.route("/donation", methods=["GET", "POST"])
def donation():
    if request.method == "POST":
        try:
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            contact = request.form['contact']
            email = request.form['email']
            amount = float(request.form['amount'])
            payment_mode = request.form['payment_mode']
            transaction_number = request.form.get('transaction_number', '').strip()

            if not transaction_number:
                return jsonify({"success": False, "error": "Transaction number is required."})

            user = User.query.filter((User.email == email) | (User.contact == contact)).first()
            if not user:
                user = User(firstname=first_name, lastname=last_name, contact=contact, email=email)
                fund_db.session.add(user)
                fund_db.session.commit()
            else:
                user.firstname = first_name
                user.lastname = last_name
                fund_db.session.commit()

            reference_code = generate_reference_code()

            # Save as PENDING — not counted until admin approves
            transaction = Transaction(
                user_id=user.id,
                amount=amount,
                mode_of_payment=payment_mode,
                transaction_number=transaction_number,
                reference_number=reference_code,
                approval_status="pending"
            )
            fund_db.session.add(transaction)
            fund_db.session.commit()

            # Notify admin via email about new pending donation
            try:
                admin_msg = Message(
                    subject="[EcoSphere Admin] New Donation Pending Approval",
                    recipients=[app.config['MAIL_USERNAME']]
                )
                admin_msg.html = f"""
                <html>
                <body style="font-family: 'Outfit', sans-serif; color: #1a1a1a; line-height:1.6;">
                    <h2>New Donation Pending Review</h2>
                    <p><strong>Donor:</strong> {first_name} {last_name}</p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Amount:</strong> &#8369;{amount}</p>
                    <p><strong>Payment Method:</strong> {payment_mode}</p>
                    <p><strong>Transaction #:</strong> {transaction_number}</p>
                    <p><strong>Reference:</strong> {reference_code}</p>
                    <p>
                        <a href="http://localhost:5000/admin/dashboard" style="
                            background:#419b58;color:white;padding:10px 20px;
                            border-radius:8px;text-decoration:none;font-weight:bold;">
                            Review in Admin Dashboard
                        </a>
                    </p>
                </body>
                </html>
                """
                mail.send(admin_msg)
            except Exception as e:
                print("Admin notification email failed:", e)

            return jsonify({"success": True, "donation_id": transaction.id})

        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    # Only count APPROVED donations on the public page
    total_amount = fund_db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.approval_status == "approved").scalar() or 0
    total_count = fund_db.session.query(func.count(Transaction.id)).filter(
        Transaction.approval_status == "approved").scalar() or 0
    recent_donors = (Transaction.query
                     .filter_by(approval_status="approved")
                     .order_by(Transaction.id.desc())
                     .limit(5).all())
    progress = min(total_amount / FUNDRAISING_GOAL * 100, 100)

    return render_template(
        "fundraising.html",
        total_amount=total_amount,
        total_count=total_count,
        recent_donors=recent_donors,
        progress=progress,
        goal=FUNDRAISING_GOAL
    )

# ── PENDING CONFIRMATION PAGE (shown to donor after submission) ────────────────
@app.route("/donation/pending/<int:transaction_id>")
def donation_pending(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    return render_template("donation_pending.html", donation=transaction)

# ── PAYMENT INSTRUCTIONS PAGE (shown after admin approves) ────────────────────
@app.route("/payment/<int:transaction_id>")
def payment(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    return render_template("payment.html", donation=transaction)

# ── ADMIN LOGIN / LOGOUT ───────────────────────────────────────────────────────
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid username or password.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('admin_username', None)
    return redirect(url_for('admin_login'))

# ── ADMIN DASHBOARD ────────────────────────────────────────────────────────────
@app.route("/admin")
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    # Only APPROVED totals count
    total_amount = fund_db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.approval_status == "approved").scalar() or 0
    total_donations = fund_db.session.query(func.count(Transaction.id)).filter(
        Transaction.approval_status == "approved").scalar() or 0
    pending_count = fund_db.session.query(func.count(Transaction.id)).filter(
        Transaction.approval_status == "pending").scalar() or 0
    total_users = fund_db.session.query(func.count(User.id)).scalar() or 0
    total_emails_sent = fund_db.session.query(func.count(Email.id)).filter(
        Email.status == "sent").scalar() or 0

    gcash_total = fund_db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.mode_of_payment == "GCash",
        Transaction.approval_status == "approved").scalar() or 0
    maya_total = fund_db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.mode_of_payment == "Maya",
        Transaction.approval_status == "approved").scalar() or 0
    bancnet_total = fund_db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.mode_of_payment == "BancNet",
        Transaction.approval_status == "approved").scalar() or 0

    progress = min(total_amount / FUNDRAISING_GOAL * 100, 100)

    all_transactions = (
        fund_db.session.query(Transaction, User)
        .join(User, Transaction.user_id == User.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )
    # Pending transactions highlighted separately for the admin
    pending_transactions = (
        fund_db.session.query(Transaction, User)
        .join(User, Transaction.user_id == User.id)
        .filter(Transaction.approval_status == "pending")
        .order_by(Transaction.created_at.asc())
        .all()
    )

    all_users = User.query.order_by(User.id.desc()).all()
    all_emails = (
        fund_db.session.query(Email, User, Transaction)
        .join(User, Email.user_id == User.id)
        .join(Transaction, Email.transaction_id == Transaction.id)
        .order_by(Email.sent_at.desc())
        .all()
    )

    with messages_app.app_context():
        messages_count = MessageDB.query.count()
        all_messages_raw = MessageDB.query.order_by(MessageDB.id.desc()).all()
        messages_list = [
            {"id": m.id, "name": m.name, "email": m.email,
             "phone": m.phone, "subject": m.subject, "message": m.message}
            for m in all_messages_raw
        ]

    return render_template(
        "admin_dashboard.html",
        total_amount=total_amount,
        total_donations=total_donations,
        pending_count=pending_count,
        total_users=total_users,
        total_emails_sent=total_emails_sent,
        gcash_total=gcash_total,
        maya_total=maya_total,
        bancnet_total=bancnet_total,
        progress=progress,
        goal=FUNDRAISING_GOAL,
        all_transactions=all_transactions,
        pending_transactions=pending_transactions,
        all_users=all_users,
        all_emails=all_emails,
        messages_list=messages_list,
        messages_count=messages_count,
    )

# ── ADMIN: APPROVE TRANSACTION ─────────────────────────────────────────────────
@app.route("/admin/approve_transaction/<int:txn_id>", methods=["POST"])
@admin_required
def admin_approve_transaction(txn_id):
    txn = Transaction.query.get_or_404(txn_id)
    txn.approval_status = "approved"
    txn.reviewed_at = datetime.utcnow()
    fund_db.session.commit()

    # Send confirmation email to donor
    user = User.query.get(txn.user_id)
    email_status = "failed"
    try:
        msg = Message(
            subject="Your EcoSphere Donation Has Been Approved! 🌿",
            recipients=[user.email]
        )
        msg.html = f"""
        <html>
        <body style="font-family: 'Outfit', sans-serif; color: #1a1a1a; line-height:1.6; max-width:560px; margin:auto;">
            <div style="background:#419b58;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="color:white;margin:0;font-size:1.6rem;">Donation Approved! ✅</h1>
            </div>
            <div style="background:#f9fff9;padding:28px;border-radius:0 0 12px 12px;border:1px solid #d4edda;">
                <p>Hi <strong>{user.firstname} {user.lastname}</strong>,</p>
                <p>Great news! Your donation has been <strong style="color:#419b58;">verified and approved</strong> by our team.</p>
                <table style="width:100%;border-collapse:collapse;margin:20px 0;">
                    <tr style="background:#eaf7f0;">
                        <td style="padding:10px 14px;font-weight:600;border-radius:6px 0 0 6px;">Amount</td>
                        <td style="padding:10px 14px;border-radius:0 6px 6px 0;">&#8369;{txn.amount:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px 14px;font-weight:600;">Payment Method</td>
                        <td style="padding:10px 14px;">{txn.mode_of_payment}</td>
                    </tr>
                    <tr style="background:#eaf7f0;">
                        <td style="padding:10px 14px;font-weight:600;border-radius:6px 0 0 6px;">Transaction #</td>
                        <td style="padding:10px 14px;border-radius:0 6px 6px 0;">{txn.transaction_number}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px 14px;font-weight:600;">EcoSphere Ref #</td>
                        <td style="padding:10px 14px;">{txn.reference_number}</td>
                    </tr>
                </table>
                <p>Your contribution helps fund real environmental projects across the Philippines. 🌱</p>
                <p>Warm regards,<br><strong>The EcoSphere Team</strong></p>
            </div>
        </body>
        </html>
        """
        mail.send(msg)
        email_status = "sent"
    except Exception as e:
        print("Approval email failed:", e)

    email_record = Email(user_id=user.id, transaction_id=txn.id, status=email_status)
    fund_db.session.add(email_record)
    fund_db.session.commit()

    flash(f"Transaction #{txn_id} approved and donor notified.", "success")
    return redirect(url_for('admin_dashboard') + "#pending")

# ── ADMIN: REJECT TRANSACTION ──────────────────────────────────────────────────
@app.route("/admin/reject_transaction/<int:txn_id>", methods=["POST"])
@admin_required
def admin_reject_transaction(txn_id):
    txn = Transaction.query.get_or_404(txn_id)
    txn.approval_status = "rejected"
    txn.reviewed_at = datetime.utcnow()
    fund_db.session.commit()

    # Send rejection email to donor
    user = User.query.get(txn.user_id)
    email_status = "failed"
    try:
        msg = Message(
            subject="Update on Your EcoSphere Donation Submission",
            recipients=[user.email]
        )
        msg.html = f"""
        <html>
        <body style="font-family: 'Outfit', sans-serif; color: #1a1a1a; line-height:1.6; max-width:560px; margin:auto;">
            <div style="background:#e53e3e;padding:24px;border-radius:12px 12px 0 0;text-align:center;">
                <h1 style="color:white;margin:0;font-size:1.6rem;">Donation Not Verified</h1>
            </div>
            <div style="background:#fff5f5;padding:28px;border-radius:0 0 12px 12px;border:1px solid #fed7d7;">
                <p>Hi <strong>{user.firstname} {user.lastname}</strong>,</p>
                <p>We were unable to verify your donation submission with the following details:</p>
                <table style="width:100%;border-collapse:collapse;margin:20px 0;">
                    <tr style="background:#fff0f0;">
                        <td style="padding:10px 14px;font-weight:600;">Amount</td>
                        <td style="padding:10px 14px;">&#8369;{txn.amount:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px 14px;font-weight:600;">Payment Method</td>
                        <td style="padding:10px 14px;">{txn.mode_of_payment}</td>
                    </tr>
                    <tr style="background:#fff0f0;">
                        <td style="padding:10px 14px;font-weight:600;">Transaction #</td>
                        <td style="padding:10px 14px;">{txn.transaction_number}</td>
                    </tr>
                    <tr>
                        <td style="padding:10px 14px;font-weight:600;">EcoSphere Ref #</td>
                        <td style="padding:10px 14px;">{txn.reference_number}</td>
                    </tr>
                </table>
                <p>This may be due to an incorrect transaction number or unmatched payment details. 
                   If you believe this is an error, please contact us at 
                   <a href="mailto:ecosphereofficial.ph@gmail.com">ecosphereofficial.ph@gmail.com</a> 
                   and we'll be happy to help.</p>
                <p>Warm regards,<br><strong>The EcoSphere Team</strong></p>
            </div>
        </body>
        </html>
        """
        mail.send(msg)
        email_status = "sent"
    except Exception as e:
        print("Rejection email failed:", e)

    email_record = Email(user_id=user.id, transaction_id=txn.id, status=email_status)
    fund_db.session.add(email_record)
    fund_db.session.commit()

    flash(f"Transaction #{txn_id} rejected and donor notified.", "success")
    return redirect(url_for('admin_dashboard') + "#pending")

# ── ADMIN: DELETE TRANSACTION ──────────────────────────────────────────────────
@app.route("/admin/delete_transaction/<int:txn_id>", methods=["POST"])
@admin_required
def admin_delete_transaction(txn_id):
    txn = Transaction.query.get_or_404(txn_id)
    Email.query.filter_by(transaction_id=txn_id).delete()
    fund_db.session.delete(txn)
    fund_db.session.commit()
    flash(f"Transaction #{txn_id} deleted.", "success")
    return redirect(url_for('admin_dashboard') + "#transactions")

# ── ADMIN: DELETE MESSAGE ──────────────────────────────────────────────────────
@app.route("/admin/delete_message/<int:msg_id>", methods=["POST"])
@admin_required
def admin_delete_message(msg_id):
    with messages_app.app_context():
        msg = MessageDB.query.get_or_404(msg_id)
        messages_db.session.delete(msg)
        messages_db.session.commit()
    flash(f"Message #{msg_id} deleted.", "success")
    return redirect(url_for('admin_dashboard') + "#messages")

# ── RUN ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)