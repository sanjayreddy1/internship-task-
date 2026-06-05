import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    USE_SQLITE = os.getenv('USE_SQLITE', 'true').lower() in ('true', '1', 'yes')

    if USE_SQLITE:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///todo.db'
    else:
        DB_USER = os.getenv('DB_USER', None)
        DB_PASSWORD = os.getenv('DB_PASSWORD', None)
        DB_HOST = os.getenv('DB_HOST', 'localhost')
        DB_PORT = os.getenv('DB_PORT', '1433')
        DB_NAME = os.getenv('DB_NAME', 'TodoDB')
        DB_DRIVER = os.getenv('DB_DRIVER', 'ODBC Driver 18 for SQL Server')

        if DB_USER and DB_PASSWORD:
            SQLALCHEMY_DATABASE_URI = (
                f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
                f"?driver={DB_DRIVER.replace(' ', '+')}"
                f"&TrustServerCertificate=yes&Encrypt=yes&ConnectionTimeout=30"
            )
        else:
            SQLALCHEMY_DATABASE_URI = (
                f"mssql+pyodbc://@{DB_HOST}:{DB_PORT}/{DB_NAME}"
                f"?driver={DB_DRIVER.replace(' ', '+')}"
                f"&Trusted_Connection=yes&TrustServerCertificate=yes&Encrypt=yes&ConnectionTimeout=30"
            )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'max_overflow': 20,
    }

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-me')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5000')

    ITEMS_PER_PAGE = 20
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
