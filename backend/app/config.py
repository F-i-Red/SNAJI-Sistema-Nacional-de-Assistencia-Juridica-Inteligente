
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "SNAJI"
    DEBUG: bool = True
    DATABASE_URL: str = "postgresql://snaji:snaji@db:5432/snaji"

settings = Settings()
