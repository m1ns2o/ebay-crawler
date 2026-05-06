import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ebay_watch_bot import cli

FIXTURES = Path(__file__).parent / "fixtures"


class CliTests(unittest.TestCase):
    def test_once_command_accepts_default_interval_without_crashing(self) -> None:
        html = (FIXTURES / "search_initial.html").read_text()

        class FakeFetcher:
            def __init__(self, **kwargs) -> None:
                pass

            def fetch(self) -> str:
                return html

        with tempfile.TemporaryDirectory() as directory:
            database_path = str(Path(directory) / "watch.sqlite3")
            with patch("ebay_watch_bot.cli.EbayHtmlFetcher", FakeFetcher):
                exit_code = cli.main(["--db", database_path, "once", "--dry-run"])

        self.assertEqual(exit_code, 0)

    def test_jittered_interval_stays_inside_expected_range(self) -> None:
        values = {cli.jittered_interval(900, jitter_seconds=120) for _ in range(100)}

        self.assertGreaterEqual(min(values), 780)
        self.assertLessEqual(max(values), 1020)

    def test_jittered_interval_can_be_disabled(self) -> None:
        self.assertEqual(cli.jittered_interval(900, jitter_seconds=0), 900)

    def test_telegram_test_command_sends_message(self) -> None:
        sent_messages = []

        class FakeNotifier:
            def __init__(self, **kwargs) -> None:
                pass

            def send_text(self, message: str) -> None:
                sent_messages.append(message)

        with patch("ebay_watch_bot.cli.TelegramNotifier", FakeNotifier):
            exit_code = cli.main(["test-telegram", "--message", "hello"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(sent_messages, ["hello"])


if __name__ == "__main__":
    unittest.main()
