# config/settings.py
# This file loads all our environment variables in one place.
# Every other file will import settings from here.

import os
from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# App Settings
APP_NAME = os.getenv("APP_NAME", "DTU Academic Intelligence Platform")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "True") == "True"

# Scraper Settings
DTU_RESULT_URL = "https://exam.dtu.ac.in/result.htm"
DTU_BASE_URL = "https://exam.dtu.ac.in"

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")