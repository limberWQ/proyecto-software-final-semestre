import os


class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://segip_user:segip_pass@db:3306/segip_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
