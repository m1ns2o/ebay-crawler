from datetime import UTC, datetime
import unittest

from ebay_watch_bot.models import Alert, Listing
from ebay_watch_bot.notifier import TelegramNotifier, compose_alert_message


class FakeResponse:
    status_code = 200
    text = '{"ok": true}'

    def json(self):
        return {"ok": True}


class FakeSession:
    def __init__(self) -> None:
        self.calls = []

    def post(self, url, data, timeout):
        self.calls.append((url, data, timeout))
        return FakeResponse()


class NotifierTests(unittest.TestCase):
    def test_composes_alert_message(self) -> None:
        alert = Alert(
            kind="restocked",
            listing=Listing(
                item_id="123456789012",
                title="Apple Magic Keyboard MWR53LL/A",
                url="https://www.ebay.com/itm/123456789012",
                price="US $229.99",
                availability="available",
                available_quantity=2,
            ),
        )

        message = compose_alert_message(
            alert,
            detected_at=datetime(2026, 5, 6, 1, 2, 3, tzinfo=UTC),
        )

        self.assertIn("재입고", message)
        self.assertIn("Apple Magic Keyboard", message)
        self.assertIn("US $229.99", message)
        self.assertIn("https://www.ebay.com/itm/123456789012", message)

    def test_sends_telegram_message(self) -> None:
        session = FakeSession()
        notifier = TelegramNotifier(
            bot_token="token",
            chat_id="chat",
            session=session,
            timeout_seconds=5,
        )

        notifier.send_text("hello")

        self.assertEqual(len(session.calls), 1)
        url, data, timeout = session.calls[0]
        self.assertEqual(url, "https://api.telegram.org/bottoken/sendMessage")
        self.assertEqual(data["chat_id"], "chat")
        self.assertEqual(data["text"], "hello")
        self.assertEqual(timeout, 5)


if __name__ == "__main__":
    unittest.main()
