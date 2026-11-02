from pathlib import Path
from urllib.parse import urlparse
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OE_", env_file=".env", extra="ignore", hide_input_in_errors=True)
    data_dir: Path = Path(".data")
    database_url: str = ""
    mode: str = "local"
    team_origin: str = ""
    team_test_sqlite: bool = False
    team_allow_insecure_loopback: bool = False
    session_hours: int = Field(default=12, ge=1, le=168)
    embedded_worker: bool = False
    eager_jobs: bool = False
    service_token: str = ""
    llm_config_file: Path | None = None
    llm_default_profile: str | None = None
    llm_smoke_budget_file: Path | None = None
    llm_smoke_price_file: Path | None = None
    trustgraph_config_file: Path | None = None
    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0, le=20 * 1024 * 1024)

    @model_validator(mode="after")
    def local_only(self):
        if self.mode not in {"local", "team"}:
            raise ValueError("Mode must be local or team")
        self.data_dir = self.data_dir.resolve()
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir / 'studio.sqlite'}"
        if self.mode == "team":
            if not self.team_test_sqlite and not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise ValueError("Team mode requires PostgreSQL")
            if not self.team_origin and not self.team_test_sqlite:
                raise ValueError("Team mode requires OE_TEAM_ORIGIN")
            if self.team_origin:
                origin = urlparse(self.team_origin)
                loopback = origin.hostname in {"localhost", "127.0.0.1", "::1"}
                if (origin.scheme != "https" and not (self.team_allow_insecure_loopback and loopback and origin.scheme == "http")) or not origin.netloc or origin.path or origin.query or origin.fragment or origin.username or origin.password:
                    raise ValueError("Team origin must be an exact HTTPS origin (or explicitly enabled HTTP loopback)")
        return self
