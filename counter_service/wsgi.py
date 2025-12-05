"""
WSGI entry point for Gunicorn.
"""

from counter_service.app import create_app

# Create the application instance
application = create_app()

if __name__ == '__main__':
    application.run()

