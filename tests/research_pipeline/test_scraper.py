import unittest

from product_engineering.scraper import parse_html


class ScraperTests(unittest.TestCase):
    def test_extracts_metadata_and_nested_heading_text(self) -> None:
        html = """
        <html lang="en"><head>
          <meta content="Useful product" name="description">
          <title>Example &amp; Co</title>
        </head><body>
          <h1>Plan <span>faster</span></h1>
          <h2>Features</h2><h2>Features</h2>
        </body></html>
        """
        data = parse_html(html, url="https://example.com/")
        self.assertEqual(data["title"], "Example & Co")
        self.assertEqual(data["description"], "Useful product")
        self.assertEqual(data["lang"], "en")
        self.assertEqual(data["h1"], ["Plan faster"])
        self.assertEqual(data["h2"], ["Features"])


if __name__ == "__main__":
    unittest.main()
