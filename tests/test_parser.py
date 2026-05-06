from pathlib import Path
import unittest

from ebay_watch_bot.parser import describe_search_page, page_has_no_results, parse_search_results

FIXTURES = Path(__file__).parent / "fixtures"


class ParserTests(unittest.TestCase):
    def test_parses_ebay_search_items(self) -> None:
        html = (FIXTURES / "search_initial.html").read_text()
        listings = parse_search_results(html)

        self.assertEqual(len(listings), 2)
        self.assertEqual(listings[0].item_id, "111111111111")
        self.assertEqual(listings[0].title, "Apple Magic Keyboard MWR53LL/A")
        self.assertEqual(listings[0].price, "US $229.99")
        self.assertEqual(listings[0].availability, "available")
        self.assertEqual(listings[0].available_quantity, 1)
        self.assertEqual(listings[1].availability, "out_of_stock")
        self.assertEqual(listings[1].available_quantity, 0)

    def test_detects_no_results_page(self) -> None:
        html = (FIXTURES / "no_results.html").read_text()
        self.assertTrue(page_has_no_results(html))
        self.assertEqual(parse_search_results(html), [])

    def test_parses_current_s_card_ebay_layout(self) -> None:
        html = (FIXTURES / "search_s_card.html").read_text()
        listings = parse_search_results(html)

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].item_id, "136534139720")
        self.assertEqual(
            listings[0].title,
            "Apple MWR53LL/A Magic Keyboard For iPad Pro 13inch (M4) - Black",
        )
        self.assertEqual(listings[0].price, "KRW363,875.52")
        self.assertEqual(listings[0].availability, "available")

    def test_describes_unparsed_page_shape(self) -> None:
        html = (FIXTURES / "search_s_card.html").read_text()
        description = describe_search_page(html)

        self.assertIn("s_card_count=2", description)
        self.assertIn("itm_link_count=", description)


if __name__ == "__main__":
    unittest.main()
