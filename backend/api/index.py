"""Vercel entry point: exposes the Django WSGI app as a serverless function."""

from config.wsgi import application

app = application
