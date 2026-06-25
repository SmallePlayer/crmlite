import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "crm-secret-key-change-in-production-12345")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./crm.db")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
