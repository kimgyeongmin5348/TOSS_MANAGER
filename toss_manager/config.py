"""Environment-based application and database configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv
from sqlalchemy import URL


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class DatabaseSettings:
    """TiDB connection settings normalized to a SQLAlchemy URL."""

    url: str | URL

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        load_dotenv()
        if database_url := _env("TIDB_DATABASE_URL"):
            return cls(database_url)

        values = {
            "DB_HOST": _env("DB_HOST"),
            "DB_PORT": _env("DB_PORT", "4000"),
            "DB_USERNAME": _env("DB_USERNAME"),
            "DB_PASSWORD": _env("DB_PASSWORD"),
            "DB_DATABASE": _env("DB_DATABASE"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f".env에 다음 DB 값을 설정하세요: {', '.join(missing)}")
        try:
            port = int(values["DB_PORT"])
        except ValueError as exc:
            raise ValueError("DB_PORT는 숫자여야 합니다.") from exc

        query: dict[str, str] = {"charset": "utf8mb4"}
        if _env("DB_SSL", "true").lower() not in {"0", "false", "no"}:
            query["ssl_verify_cert"] = "true"
            query["ssl_verify_identity"] = "true"
        return cls(URL.create(
            "mysql+pymysql",
            username=values["DB_USERNAME"],
            password=values["DB_PASSWORD"],
            host=values["DB_HOST"],
            port=port,
            database=values["DB_DATABASE"],
            query=query,
        ))


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    api_base_url: str = "https://openapi.tossinvest.com"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        values = {
            "TOSS_CLIENT_ID": _env("TOSS_CLIENT_ID"),
            "TOSS_CLIENT_SECRET": _env("TOSS_CLIENT_SECRET"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError(f".env에 다음 값을 설정하세요: {', '.join(missing)}")
        return cls(
            client_id=values["TOSS_CLIENT_ID"],
            client_secret=values["TOSS_CLIENT_SECRET"],
            api_base_url=_env("TOSS_API_BASE_URL", "https://openapi.tossinvest.com").rstrip("/"),
        )
