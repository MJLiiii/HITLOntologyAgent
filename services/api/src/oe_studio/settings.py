from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OE_", env_file=".env", extra="ignore")
    data_dir: Path = Path(".data")
    database_url: str = ""
    mode: str = "local"
    eager_jobs: bool = False
    service_token: str = ""
    model_url: str = ""
    model_name: str = ""
    model_api_key: str = ""
    model_timeout: float = Field(default=45, gt=0, le=120)
    trustgraph_config_file: Path | None = None
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0, le=20 * 1024 * 1024)

    @model_validator(mode="after")
    def local_only(self):
        if self.mode != "local":
            raise ValueError("Only local mode is enabled; shared identity integration remains gated")
        self.data_dir = self.data_dir.resolve()
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir / 'studio.sqlite'}"
        return self
