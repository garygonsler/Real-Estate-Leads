from flask import Flask
from flask_migrate import Migrate
from flask_cors import CORS
import logging
import os

from config.config import config
from app.database import db, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask extensions
migrate = Migrate()


def create_app(config_name=None):
    """
    Application factory pattern
    
    Args:
        config_name: Configuration to use (development, production, testing)
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    init_db(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register blueprints
    from app.api.tracking import tracking_bp
    from app.api.leads import leads_bp
    from app.api.dashboard import dashboard_bp
    
    app.register_blueprint(tracking_bp)
    app.register_blueprint(leads_bp)
    app.register_blueprint(dashboard_bp)
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'real-estate-ai'}, 200
    
    @app.route('/')
    def index():
        return {
            'service': 'Real Estate AI',
            'version': '1.0.0',
            'endpoints': {
                'health': '/health',
                'tracking': '/track',
                'leads': '/api/leads',
                'dashboard': '/api/dashboard'
            }
        }
    
    logger.info(f"Application created with {config_name} configuration")
    
    return app


# Create app instance
app = create_app()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
