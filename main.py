import sys
import os

# Add the backend directory to the Python path so internal imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.main import app