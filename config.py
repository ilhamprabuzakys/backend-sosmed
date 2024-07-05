from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Sosial Media Cegah"
    APP_DESCRIPTION: str = "API untuk mengelola fungsi sosial media cegah"
    API_PREFIX: str = '/api'
    FE_URL: str = 'https://sidepe.bnn.go.id/socmed/dashboard'
    DATABASE_URL: str = 'postgresql://iotekno:password@iotekno.id:5432/sosmed_cegah'
    CORS_ALLOW_ORIGINS: list = ['*']
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list = ["GET", "POST"]
    CORS_ALLOW_HEADERS: list = ["Content-Type", "Authorization"]


settings = Settings()