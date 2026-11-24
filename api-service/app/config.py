from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://you_can_book:you_can_book@127.0.0.1:5432/you_can_book_db?ssl=disable"
    sql_echo: bool = False

    # JWT: секрет подписи, алгоритм и время жизни access-токена
    jwt_secret: str = "dev-secret-change-me-at-least-32-bytes-long"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
