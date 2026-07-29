from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    line_channel_secret: str = Field(default=...)
    line_channel_access_token: str = Field(default=...)

    model_name: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(extra="ignore")


settings = Settings()
