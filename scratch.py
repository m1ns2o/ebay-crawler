import sys
sys.path.append('.')
from ebay_watch_bot.crawler import EbayHtmlFetcher
from ebay_watch_bot.config import Config
config = Config.from_env()

fetcher = EbayHtmlFetcher(
    target_url=config.target_url,
    user_agent=config.user_agent,
    timeout_seconds=config.request_timeout_seconds
)

html = fetcher.fetch()
with open("test_playwright.html", "w") as f:
    f.write(html)
