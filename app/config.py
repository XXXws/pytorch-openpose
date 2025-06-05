import os

# Project root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Model directory can be set via environment variable MODEL_DIR
MODEL_DIR = os.getenv('MODEL_DIR', 'model')
# Convert to absolute path if not already
if not os.path.isabs(MODEL_DIR):
    MODEL_DIR = os.path.join(BASE_DIR, MODEL_DIR)
