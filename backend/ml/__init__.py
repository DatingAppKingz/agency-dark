# ML Module for Advanced Analytics
import os

# Check if ML features are disabled
ML_DISABLED = os.getenv('DISABLE_ML', 'false').lower() == 'true'

if ML_DISABLED:
    print("ML features are disabled via DISABLE_ML environment variable")