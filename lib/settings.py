from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DB_PATH: str = str(Path(__file__).resolve().parent.parent / "data" / "ace.db")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
