import os
from flask import Flask
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from .models import db

# Load environment variables from .env file (if running locally)
load_dotenv()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-fallback')
    
    # Database config: ensure neon postgresql format is correct for sqlalchemy
    # (Sometimes it gives postgres:// instead of postgresql://)
    db_url = os.getenv('DATABASE_URL', 'sqlite:///local.db')
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # JWT Config
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-dev-key')
    
    # Initialize Extensions
    db.init_app(app)
    jwt = JWTManager(app)

    #Blueprint registration
    from .routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    @app.route('/')
    def health_check():
        return {"status": "ok", "message": "Expense API is running"}
        
    return app