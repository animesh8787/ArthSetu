from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_BOOTSTRAP_PASSWORD = "arthsetu-admin"


class Settings(BaseSettings):
    APP_NAME: str = "ArthSetu"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    # Local dev defaults to a portable SQLite file. Override via the
    # DATABASE_URL env var (e.g. postgresql+psycopg2://user:pass@host/db).
    DATABASE_URL: str = "sqlite:///./arthsetu_dev.db"

    # Comma-separated list of allowed browser origins for CORS.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    LOG_LEVEL: str = "INFO"

    # Background jobs normally run on a worker thread pool. Tests (and any
    # environment that wants deterministic, synchronous execution) set this
    # to run jobs inline on the submitting thread instead.
    JOBS_SYNC: bool = False
    JOBS_MAX_WORKERS: int = 2

    # --- Auth (Firebase) ---------------------------------------------------
    # Paste the full contents of a Firebase service-account JSON here in any
    # non-local environment. Left empty locally, where FIREBASE_AUTH_EMULATOR_HOST
    # (set by `firebase emulators:start`) is used instead — firebase-admin
    # picks that up on its own, no credentials needed against the emulator.
    FIREBASE_CREDENTIALS_JSON: str = ""
    # Used to initialise the Admin SDK against the emulator (any placeholder
    # value works there) and must match the real project id in production.
    FIREBASE_PROJECT_ID: str = "arthsetu-dev"

    # First-run bootstrap admin (created by the seeder / on empty user table).
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@arthsetu.local"
    BOOTSTRAP_ADMIN_PASSWORD: str = _INSECURE_BOOTSTRAP_PASSWORD

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _refuse_insecure_production_config(self) -> "Settings":
        """Fail fast rather than silently serve a production deployment
        with no real Firebase project or the dev bootstrap admin password
        still in place."""
        if self.APP_ENV.lower() == "production":
            if not self.FIREBASE_CREDENTIALS_JSON:
                raise ValueError(
                    "FIREBASE_CREDENTIALS_JSON must be set when APP_ENV=production "
                    "(paste the Firebase service-account JSON)"
                )
            if self.BOOTSTRAP_ADMIN_PASSWORD == _INSECURE_BOOTSTRAP_PASSWORD:
                raise ValueError(
                    "BOOTSTRAP_ADMIN_PASSWORD must be overridden when APP_ENV=production"
                )
        return self


settings = Settings()
