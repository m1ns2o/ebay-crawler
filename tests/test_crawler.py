from pathlib import Path
import tempfile
import unittest

from ebay_watch_bot.crawler import Watcher
from ebay_watch_bot.models import Alert
from ebay_watch_bot.storage import Store

FIXTURES = Path(__file__).parent / "fixtures"


class FakeFetcher:
    def __init__(self, pages: list[str]) -> None:
        self.pages = pages

    def fetch(self) -> str:
        if len(self.pages) == 1:
            return self.pages[0]
        return self.pages.pop(0)


class FakeNotifier:
    def __init__(self) -> None:
        self.alerts: list[Alert] = []

    def send_alert(self, alert: Alert, *, detected_at) -> None:
        self.alerts.append(alert)


class WatcherTests(unittest.TestCase):
    def test_first_run_stores_baseline_without_alerts(self) -> None:
        initial = (FIXTURES / "search_initial.html").read_text()
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "watch.sqlite3")
            notifier = FakeNotifier()
            watcher = Watcher(
                store=store,
                fetcher=FakeFetcher([initial]),
                notifier=notifier,
            )

            alerts = watcher.check_once()

            self.assertEqual(alerts, [])
            self.assertEqual(notifier.alerts, [])
            self.assertTrue(store.is_initialized())
            self.assertEqual(len(store.get_items()), 2)
            store.close()

    def test_detects_new_restocked_and_stock_increase(self) -> None:
        initial = (FIXTURES / "search_initial.html").read_text()
        updated = (FIXTURES / "search_updated.html").read_text()
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "watch.sqlite3")
            notifier = FakeNotifier()
            watcher = Watcher(
                store=store,
                fetcher=FakeFetcher([initial, updated]),
                notifier=notifier,
            )

            self.assertEqual(watcher.check_once(), [])
            alerts = watcher.check_once()

            self.assertEqual([alert.kind for alert in alerts], ["stock_increase", "restocked", "new"])
            self.assertEqual([alert.kind for alert in notifier.alerts], ["stock_increase", "restocked", "new"])
            store.close()

    def test_missing_item_is_marked_out_and_reappearance_is_restock(self) -> None:
        initial = (FIXTURES / "search_initial.html").read_text()
        no_results = (FIXTURES / "no_results.html").read_text()
        updated = (FIXTURES / "search_updated.html").read_text()
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "watch.sqlite3")
            notifier = FakeNotifier()
            watcher = Watcher(
                store=store,
                fetcher=FakeFetcher([initial, no_results, updated]),
                notifier=notifier,
            )

            self.assertEqual(watcher.check_once(), [])
            self.assertEqual(watcher.check_once(), [])
            alerts = watcher.check_once()

            self.assertIn("restocked", [alert.kind for alert in alerts])
            store.close()


if __name__ == "__main__":
    unittest.main()
