from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://you_can_book:you_can_book@127.0.0.1:5432/you_can_book_db?ssl=disable"
    sql_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
