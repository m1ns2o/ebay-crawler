from __future__ import annotations

from datetime import datetime

import requests

from .models import Alert


class TelegramConfigurationError(RuntimeError):
    pass


class TelegramSendError(RuntimeError):
    pass


class TelegramNotifier:
    def __init__(
        self,
        *,
        bot_token: str | None,
        chat_id: str | None,
        timeout_seconds: int = 20,
        session: requests.Session | None = None,
    ) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def send_alert(self, alert: Alert, *, detected_at: datetime) -> None:
        self.send_text(compose_alert_message(alert, detected_at=detected_at))

    def send_text(self, message: str) -> None:
        if not self.bot_token or not self.chat_id:
            raise TelegramConfigurationError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required"
            )

        response = self.session.post(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data={
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": "false",
            },
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise TelegramSendError(
                f"Telegram sendMessage failed with HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        payload = response.json()
        if not payload.get("ok"):
            raise TelegramSendError(f"Telegram sendMessage returned not ok: {payload}")


def compose_alert_message(alert: Alert, *, detected_at: datetime) -> str:
    listing = alert.listing
    title = {
        "new": "🆕 eBay 신규 상품 감지",
        "restocked": "✅ eBay 재입고 감지",
        "stock_increase": "📦 eBay 추가입고 감지",
    }[alert.kind]

    lines = [
        title,
        f"상품명: {listing.title}",
        f"가격: {listing.price or '확인 필요'}",
        f"상태: {_format_availability(listing.availability)}",
    ]

    if listing.available_quantity is not None:
        quantity_text = f"수량: {listing.available_quantity}"
        if alert.kind == "stock_increase" and alert.previous_quantity is not None:
            quantity_text += f" (이전 {alert.previous_quantity})"
        lines.append(quantity_text)

    lines.extend(
        [
            f"감지 시각: {detected_at.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}",
            f"링크: {listing.url}",
        ]
    )
    return "\n".join(lines)


def _format_availability(value: str) -> str:
    return {
        "available": "구매 가능",
        "out_of_stock": "품절",
        "unknown": "확인 필요",
    }.get(value, value)
