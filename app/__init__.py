import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


def create_app(config_name=None):
    """Application factory"""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Ensure instance folders exist
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'instance/uploads'), exist_ok=True)
    os.makedirs(app.config.get('BARCODE_FOLDER', 'instance/barcodes'), exist_ok=True)

    # Register blueprints
    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.inventory import inventory_bp
    from app.routes.locations import locations_bp
    from app.routes.production import production_bp
    from app.routes.orders import orders_bp
    from app.routes.customers import customers_bp
    from app.routes.reports import reports_bp
    from app.routes.api import api_bp
    from app.routes.moulds import moulds_bp
    from app.routes.settings import settings_bp
    from app.routes.labels import labels_bp
    from app.routes.scheduling import scheduling_bp
    from app.routes.costing import bp as costing_bp
    from app.routes.materials import bp as materials_bp
    from app.routes.data_management import bp as data_management_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(inventory_bp, url_prefix='/inventory')
    app.register_blueprint(locations_bp, url_prefix='/locations')
    app.register_blueprint(production_bp, url_prefix='/production')
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(customers_bp, url_prefix='/customers')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(moulds_bp, url_prefix='/moulds')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(labels_bp, url_prefix='/labels')
    app.register_blueprint(scheduling_bp, url_prefix='/scheduling')
    app.register_blueprint(costing_bp)
    app.register_blueprint(materials_bp, url_prefix='/materials')
    app.register_blueprint(data_management_bp)

    # Create database tables
    with app.app_context():
        db.create_all()
        # Create default admin user if not exists
        from app.models.user import User
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@warehouse.local',
                role='admin',
                first_name='System',
                last_name='Administrator'
            )
            admin.set_password('admin123')  # Change in production!
            db.session.add(admin)
            db.session.commit()

    return app
