from __future__ import annotations

import argparse
import logging
import random
import time
from datetime import datetime

from .config import Config
from .crawler import EbayHtmlFetcher, Watcher
from .notifier import TelegramNotifier
from .storage import Store


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = Config.from_env()
    target_url = args.url or config.target_url
    database_path = args.db or config.database_path
    interval = getattr(args, "interval", None) or config.check_interval_seconds
    jitter = getattr(args, "jitter", None)
    if jitter is None:
        jitter = config.check_interval_jitter_seconds
    heartbeat_interval = (
        getattr(args, "heartbeat_interval", None) or config.heartbeat_interval_seconds
    )

    if args.command == "test-telegram":
        notifier = TelegramNotifier(
            bot_token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
            timeout_seconds=config.request_timeout_seconds,
        )
        message = args.message or (
            "✅ eBay Watch Bot Telegram 테스트 메시지\n"
            f"전송 시각: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        notifier.send_text(message)
        logging.info("Telegram test message sent")
        return 0

    store = Store(database_path)
    fetcher = EbayHtmlFetcher(
        target_url=target_url,
        user_agent=config.user_agent,
        ebay_cookie=config.ebay_cookie,
        timeout_seconds=config.request_timeout_seconds,
    )
    notifier = TelegramNotifier(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        timeout_seconds=config.request_timeout_seconds,
    )
    watcher = Watcher(
        store=store,
        fetcher=fetcher,
        notifier=notifier,
        dry_run=getattr(args, "dry_run", False),
    )

    try:
        if args.command == "once":
            alerts = watcher.check_once()
            logging.info("Completed one check with %s alerts", len(alerts))
            return 0

        run_forever(
            watcher,
            interval_seconds=interval,
            jitter_seconds=jitter,
            heartbeat_interval_seconds=heartbeat_interval,
        )
        return 0
    finally:
        store.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ebay-watch-bot",
        description="Watch eBay search results and send Telegram restock alerts.",
    )
    parser.add_argument("--url", help="Override TARGET_URL from .env")
    parser.add_argument("--db", help="Override DATABASE_PATH from .env")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)
    once = subparsers.add_parser("once", help="Check once and exit")
    once.add_argument("--dry-run", action="store_true", help="Print alerts instead of Telegram")

    run = subparsers.add_parser("run", help="Check forever")
    run.add_argument("--dry-run", action="store_true", help="Print alerts instead of Telegram")
    run.add_argument(
        "--interval",
        type=int,
        help="Override CHECK_INTERVAL_SECONDS from .env",
    )
    run.add_argument(
        "--jitter",
        type=int,
        help="Override CHECK_INTERVAL_JITTER_SECONDS from .env",
    )
    run.add_argument(
        "--heartbeat-interval",
        type=int,
        help="Override HEARTBEAT_INTERVAL_SECONDS from .env",
    )
    test_telegram = subparsers.add_parser(
        "test-telegram",
        help="Send a Telegram test message and exit",
    )
    test_telegram.add_argument("--message", help="Override the default test message")
    return parser


def run_forever(
    watcher: Watcher,
    *,
    interval_seconds: int,
    jitter_seconds: int,
    heartbeat_interval_seconds: int,
) -> None:
    logger = logging.getLogger(__name__)
    backoff_seconds = 30
    logger.info(
        "Watcher started: check_interval=%s seconds, jitter=±%s seconds, heartbeat_interval=%s seconds",
        interval_seconds,
        jitter_seconds,
        heartbeat_interval_seconds,
    )

    while True:
        try:
            logger.info("Starting eBay check")
            alerts = watcher.check_once()
            next_interval = jittered_interval(interval_seconds, jitter_seconds=jitter_seconds)
            logger.info(
                "Check completed with %s alerts; next check in %s seconds",
                len(alerts),
                next_interval,
            )
            backoff_seconds = 30
            sleep_with_heartbeat(
                next_interval,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
                logger=logger,
                message="Waiting for next eBay check",
            )
        except KeyboardInterrupt:
            logger.info("Stopped by user")
            return
        except Exception:
            logger.exception("Check failed; retrying in %s seconds", backoff_seconds)
            sleep_with_heartbeat(
                backoff_seconds,
                heartbeat_interval_seconds=heartbeat_interval_seconds,
                logger=logger,
                message="Waiting before retry",
            )
            backoff_seconds = min(backoff_seconds * 2, 900)


def jittered_interval(interval_seconds: int, *, jitter_seconds: int) -> int:
    if jitter_seconds <= 0:
        return max(interval_seconds, 1)
    return max(interval_seconds + random.randint(-jitter_seconds, jitter_seconds), 1)


def sleep_with_heartbeat(
    total_seconds: int,
    *,
    heartbeat_interval_seconds: int,
    logger: logging.Logger,
    message: str,
) -> None:
    remaining_seconds = max(total_seconds, 0)
    heartbeat_interval_seconds = max(heartbeat_interval_seconds, 1)

    while remaining_seconds > 0:
        logger.info("%s: %s seconds remaining", message, remaining_seconds)
        sleep_seconds = min(heartbeat_interval_seconds, remaining_seconds)
        time.sleep(sleep_seconds)
        remaining_seconds -= sleep_seconds
