"""
Counter Service - A simple web service that counts POST requests
and returns the counter value on GET requests.
"""

from counter_service.app import create_app

__all__ = ['create_app']

