from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from models import db, bcrypt
import os

jwt = JWTManager()

def create_app(config_class=Config):
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    @jwt.user_identity_loader
    def user_identity_lookup(user):
        return str(user)

    CORS(app, resources={r"/api/*": {"origins": app.config.get('CORS_ORIGINS', '*').split(',')}})

    from routes.auth import auth_bp
    from routes.todos import todos_bp
    from routes.lists import lists_bp
    from routes.dashboard import dashboard_bp
    from routes.analytics import analytics_bp
    from routes.chatbot import chatbot_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(todos_bp)
    app.register_blueprint(lists_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(chatbot_bp)

    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)

    @app.route('/')
    def index():
        return send_from_directory('templates', 'app.html')

    with app.app_context():
        from models import User
        db.create_all()
        from utils.helpers import initialize_default_data
        try:
            initialize_default_data()
        except Exception as e:
            app.logger.warning(f"Could not initialize default data: {e}")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
