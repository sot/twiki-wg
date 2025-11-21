"""
Generate a test trending page.
"""

from twiki_wg import ssawg_trending_scraper
from pathlib import Path
import argparse


def get_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "page",
        choices=[p.page for p in ssawg_trending_scraper.BasePage.page_classes],
    )
    parser.add_argument("--url")
    parser.add_argument("--url-current", default="")
    parser.add_argument("--output", type=Path, default="trending.html")
    return parser


def main():
    args = get_parser().parse_args()
    pages = {p.page: p for p in ssawg_trending_scraper.BasePage.page_classes}
    page_class = pages[args.page]

    print(f"Generating test trend page for {args.page}")
    print(f"from {args.url}")
    print(f"writing into {args.output}")

    class MyPage(page_class):
        def get_url(self):
            if not args.url:
                return super().get_url()
            return args.url, args.url_current

    ssawg_trending_scraper.scrape_pages([MyPage], args.output)


if __name__ == "__main__":
    main()
