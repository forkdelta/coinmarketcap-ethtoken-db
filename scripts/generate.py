import logging
import requests

from helpers import (DEFAULT_HEADERS, process_listing)

CMC_LISTINGS_API_URL = "https://api.coinmarketcap.com/v2/listings/"


def get_listings():
    """
    Returns a list of CoinMarketCap-listed currencies via /v2/listings/ API endpoint.

    Returns: a list of dicts like so:
        [{'id': 1, 'name': 'Bitcoin', 'symbol': 'BTC', 'website_slug': 'bitcoin'}, ...]
    """
    r = requests.get(CMC_LISTINGS_API_URL, headers=DEFAULT_HEADERS)
    return r.json()["data"]


if __name__ == "__main__":
    from time import sleep
    logging.getLogger().setLevel(logging.DEBUG)

    for listing in get_listings():
        process_listing(listing)
