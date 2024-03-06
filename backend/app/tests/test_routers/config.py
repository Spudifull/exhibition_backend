from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env_test", extra="ignore")
    mongodb_url: str
    database_name: str
    base_image_url: str

settings = Settings()
