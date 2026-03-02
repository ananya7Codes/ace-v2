import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    X_API_KEY: str = ""
    X_API_SECRET: str = ""
    X_ACCESS_TOKEN: str = ""
    X_ACCESS_TOKEN_SECRET: str = ""

    DB_PATH: str = str(Path(__file__).resolve().parent.parent / "data" / "ace.db")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
