#!/usr/bin/env python3
"""
Warehouse Management System - Application Entry Point

Run with:
    python run.py

Or for production:
    gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
"""

import os
from app import create_app

# Create application instance
app = create_app(os.environ.get('FLASK_CONFIG', 'development'))

if __name__ == '__main__':
    # Get port from environment or default to 5000
    port = int(os.environ.get('PORT', 5000))

    # Run the development server
    app.run(
        host='0.0.0.0',
        port=port,
        debug=app.config.get('DEBUG', True)
    )
