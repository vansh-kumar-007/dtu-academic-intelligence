# config/settings.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

APP_NAME = os.getenv("APP_NAME", "DTU Academic Intelligence Platform")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "True") == "True"

DTU_BASE_URL = "https://exam.dtu.ac.in"

# All pages we will scrape
DTU_RESULT_PAGES = {
    "current": "https://exam.dtu.ac.in/result.htm",
    "2024":    "https://exam.dtu.ac.in/result_2024.htm",
    "2023":    "https://exam.dtu.ac.in/result_2023.htm",
    "2022":    "https://exam.dtu.ac.in/result_2022.htm",
    "2021":    "https://exam.dtu.ac.in/result_2021.htm",
    "2020":    "https://exam.dtu.ac.in/result_2020.htm",
    "all":     "https://exam.dtu.ac.in/result_all.htm",
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:dtu1234@localhost:5432/dtu_intel"
)