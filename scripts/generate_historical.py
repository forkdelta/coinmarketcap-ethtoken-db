from bs4 import BeautifulSoup
import logging
import requests
from sys import argv

from helpers import (DEFAULT_HEADERS, process_listing)

CMC_LISTINGS_API_URL = "https://api.coinmarketcap.com/v2/listings/"


def get_listing_from_row(tr):
    assert (tr is not None)
    td = tr.find("td", class_="currency-name")
    assert (td is not None)
    print(td)

    # HACK: Dirty hack alert! The only place that seems to reference the
    # listing ID on the historical page seems to be the listing logo URL
    logo_img = td.find("img", class_="logo-sprite")
    logo_src = logo_img["src"]
    assert (
        logo_src.startswith("https://s2.coinmarketcap.com/static/img/coins/"))
    listing_id = int(logo_src.split("/")[-1].split(".")[0])

    # Listing name may also be truncated in the table. Pull from logo alt-text.
    name = logo_img["alt"]
    assert (name is not None and len(name) > 0)

    symbol = td.find("span", class_="currency-symbol").text.strip()

    asset_page_path = td.find("a", class_="currency-name-container")["href"]
    slug = asset_page_path.strip("/").split("/")[-1]

    return dict(id=listing_id, name=name, symbol=symbol, website_slug=slug)


def get_listings_from_historical(url):
    """
    Returns a list of listing entries like the one produced by /v2/listings
    API given a CoinMarketCap historical snapshot index webpage.
    """

    html_doc = requests.get(url, headers=DEFAULT_HEADERS).text
    soup = BeautifulSoup(html_doc, 'html.parser')

    return [
        get_listing_from_row(tr)
        for tr in soup.select("#currencies-all tbody tr")
    ]


if __name__ == "__main__":
    from time import sleep
    logging.getLogger().setLevel(logging.DEBUG)

    historical_url = argv[1]
    assert (historical_url.startswith("https://coinmarketcap.com/historical/"))

    for listing in get_listings_from_historical(historical_url):
        process_listing(listing)
