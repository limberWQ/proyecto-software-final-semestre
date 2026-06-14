import os
from datetime import timedelta


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://tse_user:tse_pass@db:3306/tse_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-jwt-secret")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=8)
    # El frontend server-side guarda el JWT en una cookie httpOnly
    # (set_access_cookies en login web); la API también acepta el
    # token vía header Authorization.
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_COOKIE_CSRF_PROTECT = False
    JWT_COOKIE_SECURE = False

    # SEGIP API
    SEGIP_API_URL = os.getenv("SEGIP_API_URL", "http://segip:5001")
    SEGIP_API_KEY = os.getenv("SEGIP_API_KEY", "TSE-SECRET-KEY-2025")

    # Edad mínima para votar
    EDAD_MINIMA_VOTO = 18

    # Duración de la sesión de kiosco (minutos)
    DURACION_SESION_KIOSCO_MIN = 5
