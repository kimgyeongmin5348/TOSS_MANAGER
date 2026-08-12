"""Environment-based configuration. Secrets never appear in source code."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    api_base_url: str = "https://openapi.tossinvest.com"
    database_url: str | None = None

    @classmethod
    def from_env(cls, *, require_database: bool = False) -> "Settings":
        load_dotenv()
        client_id = os.getenv("TOSS_CLIENT_ID", "").strip()
        client_secret = os.getenv("TOSS_CLIENT_SECRET", "").strip()
        database_url = os.getenv("TIDB_DATABASE_URL", "").strip() or None
        missing = [name for name, value in {
            "TOSS_CLIENT_ID": client_id,
            "TOSS_CLIENT_SECRET": client_secret,
        }.items() if not value]
        if require_database and not database_url:
            missing.append("TIDB_DATABASE_URL")
        if missing:
            raise ValueError(f".env에 다음 값을 설정하세요: {', '.join(missing)}")
        return cls(
            client_id=client_id,
            client_secret=client_secret,
            api_base_url=os.getenv("TOSS_API_BASE_URL", "https://openapi.tossinvest.com").rstrip("/"),
            database_url=database_url,
        )
