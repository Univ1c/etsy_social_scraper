import unittest
from unittest.mock import patch
from etsy_scraper.scraping import scrape_social_links
class TestScraper(unittest.TestCase):
    @patch("requests.get")
    def test_scrape_social_links(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = '<a href="https://instagram.com/test">Instagram</a>'
        result = scrape_social_links("https://www.etsy.com/shop/test")
        self.assertEqual(result["instagram"], "https://instagram.com/test")
if __name__ == "__main__":
    unittest.main()
