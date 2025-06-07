try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

class Settings(BaseSettings):
    """Application configuration"""
    upload_dir: str = "uploads"
    result_dir: str = "results"
    image_dir: str = "images"
    log_level: str = "INFO"
    enable_mixed_precision: bool = False

    class Config:
        env_file = ".env"
        env_prefix = "OPENPOSE_"

settings = Settings()

