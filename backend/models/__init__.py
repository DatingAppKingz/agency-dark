"""Database models for AgencyDark."""

# Import everything from the registry
from models.registry import *
from models.registry import __all__

# Ensure all models are initialized
from models.registry import init_models

# Initialize models on import
init_models()