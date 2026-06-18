"""Vercel serverless entrypoint — exposes the FastAPI ASGI app.

Vercel's @vercel/python runtime serves the module-level `app` (ASGI). All routes
already live under /api/* in the FastAPI app, and vercel.json routes every path
here, so the app receives the original path unchanged.
"""
import os
import sys

# Make the backend package importable (this file is backend/api/index.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402,F401
