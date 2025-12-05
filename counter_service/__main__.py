"""
Entry point for running the counter service with Gunicorn.
"""

import os
from counter_service.app import create_app

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    # For local development (not used in production)
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)

