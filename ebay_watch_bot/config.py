from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_TARGET_URL = (
    "https://www.ebay.com/sch/i.html?_dkr=1&iconV2Request=true"
    "&_blrs=recall_filtering&_ssn=vipoutlet&store_cat=0"
    "&store_name=vipoutlet&_oac=1&_nkw=mwr53ll%2Fa"
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)


@dataclass(frozen=True)
class Config:
    target_url: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    check_interval_seconds: int
    check_interval_jitter_seconds: int
    heartbeat_interval_seconds: int
    user_agent: str
    database_path: str
    ebay_cookie: str | None
    request_timeout_seconds: int = 20

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        return cls(
            target_url=os.getenv("TARGET_URL", DEFAULT_TARGET_URL),
            telegram_bot_token=_blank_to_none(os.getenv("TELEGRAM_BOT_TOKEN")),
            telegram_chat_id=_blank_to_none(os.getenv("TELEGRAM_CHAT_ID")),
            check_interval_seconds=_positive_int(
                os.getenv("CHECK_INTERVAL_SECONDS"),
                default=900,
                name="CHECK_INTERVAL_SECONDS",
            ),
            check_interval_jitter_seconds=_non_negative_int(
                os.getenv("CHECK_INTERVAL_JITTER_SECONDS"),
                default=120,
                name="CHECK_INTERVAL_JITTER_SECONDS",
            ),
            heartbeat_interval_seconds=_positive_int(
                os.getenv("HEARTBEAT_INTERVAL_SECONDS"),
                default=60,
                name="HEARTBEAT_INTERVAL_SECONDS",
            ),
            user_agent=os.getenv("USER_AGENT", DEFAULT_USER_AGENT),
            database_path=os.getenv("DATABASE_PATH", "ebay_watch.sqlite3"),
            ebay_cookie=_blank_to_none(os.getenv("EBAY_COOKIE")),
            request_timeout_seconds=_positive_int(
                os.getenv("REQUEST_TIMEOUT_SECONDS"),
                default=20,
                name="REQUEST_TIMEOUT_SECONDS",
            ),
        )


def _blank_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def _positive_int(value: str | None, *, default: int, name: str) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _non_negative_int(value: str | None, *, default: int, name: str) -> int:
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be greater than or equal to zero")
    return parsed
