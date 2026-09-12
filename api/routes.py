import os
import requests
from flask import Blueprint, request, jsonify, url_for
from flask_jwt_extended import create_access_token
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from .models import db, User, Category

auth_bp = Blueprint('auth', __name__)

def generate_verification_token(email):
    serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY"))
    return serializer.dumps(email, salt='email-verify-salt')

def confirm_verification_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(os.getenv("SECRET_KEY"))
    try:
        email = serializer.loads(token, salt='email-verify-salt', max_age=expiration)
    except (SignatureExpired, BadSignature):
        return False
    return email

def send_verification_email(to_email, verify_url):
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "accept": "application/json",
        "api-key": os.getenv("BREVO_API_KEY"),
        "content-type": "application/json"
    }
    payload = {
        "sender": {
            "name": os.getenv("SENDER_NAME", "Expense Tracker"),
            "email": os.getenv("SENDER_EMAIL")
        },
        "to": [{"email": to_email}],
        "subject": "Verify Your Expense Tracker Account",
        "htmlContent": (
            f"<p>Welcome to Expense Tracker!</p>"
            f"<p>Click <a href='{verify_url}'>here</a> to verify your account.</p>"
            f"<p>This link will expire in 1 hour.</p>"
        )
    }
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    response.raise_for_status()

@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({"error": "Email already registered"}), 400
        
    new_user = User(
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        email=data.get('email')
    )
    new_user.set_password(data.get('password'))
    
    db.session.add(new_user)
    db.session.commit() # The user now has a user_id
    
    # Create 5 initial categories
    default_categories = [
        {"name": "Food", "emoji": "🍔"},
        {"name": "Transport", "emoji": "🚕"},
        {"name": "Shopping", "emoji": "🛍️"},
        {"name": "Entertainment", "emoji": "🍿"},
        {"name": "Study", "emoji": "📚"}
    ]
    
    for cat in default_categories:
        new_category = Category(
            category_name=cat["name"],
            category_emoji=cat["emoji"],
            user_id=new_user.user_id
        )
        db.session.add(new_category)
        
    db.session.commit() # Save the new categories
    
    token = generate_verification_token(new_user.email)
    verify_url = url_for('auth.verify_email', token=token, _external=True)
    
    try:
        send_verification_email(new_user.email, verify_url)
    except Exception as e:
        return jsonify({"error": f"User created, but failed to send email: {str(e)}"}), 500
        
    return jsonify({"message": "User registered successfully. Please check your email to verify."}), 201

@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    email = confirm_verification_token(token)
    if not email:
        return jsonify({"error": "The confirmation link is invalid or has expired."}), 400
        
    user = User.query.filter_by(email=email).first_or_404()
    if user.is_verified:
        return jsonify({"message": "Account already verified."}), 200
        
    user.is_verified = True
    db.session.commit()
    
    return jsonify({"message": "Account verified successfully!"}), 200

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    
    if not user or not user.check_password(data.get('password')):
        return jsonify({"error": "Invalid email or password."}), 401
        
    if not user.is_verified:
        return jsonify({"error": "Please verify your email before logging in."}), 403
        
    access_token = create_access_token(identity=str(user.user_id))
    
    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "user": user.to_dict()
    }), 200