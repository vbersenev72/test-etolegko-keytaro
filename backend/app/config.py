from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    keitaro_base_url: str = "https://tlgk.host"
    keitaro_api_key: str
    # Группа кампаний в Keitaro; создаётся автоматически, если её нет
    group_name: str = "adrobot"
    # Домен и источник трафика: если пусто — берутся первые активные из API
    domain_name: str = ""
    traffic_source_name: str = ""
    database_url: str = "sqlite:///./data/app.db"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
