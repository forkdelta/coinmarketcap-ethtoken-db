from glob import glob
from itertools import groupby
import logging
from os import environ
import requests

from helpers import (DEFAULT_HEADERS, process_listing)
from entry_io import (read_entry, write_token_entry, update_token_entry)

CMC_LISTINGS_API_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"


def get_api_listings():
    """
    Returns a list of CoinMarketCap-listed currencies via /v2/listings/ API endpoint.

    Returns: a list of dicts like so:
        [{'id': 1, 'name': 'Bitcoin', 'symbol': 'BTC', 'website_slug': 'bitcoin'}, ...]
    """
    r = requests.get(CMC_LISTINGS_API_URL, headers={**DEFAULT_HEADERS, "X-CMC_PRO_API_KEY": environ["CMC_PRO_API_KEY"]})
    return r.json()["data"]


def map_entries_to_sets(files, key, exclude_deprecated=True):
    """
    Returns a dict keyed by CoinMarketCap asset ID with sets of values for
    the given key known to be associated with that asset ID.
    """
    entries = ((entry["id"], entry[key])
               for entry in (read_entry(fn) for fn in files)
               if not (exclude_deprecated and entry.get("_DEPRECATED", False)))

    return {
        e[0]: set(g[1] for g in e[1])
        for e in groupby(sorted(entries), key=lambda e: e[0])
    }


def map_entries_to_discrete(files, key, exclude_deprecated=True):
    return {
        entry["id"]: entry[key]
        for entry in (read_entry(fn) for fn in files)
        if not (exclude_deprecated and entry.get("_DEPRECATED", False))
    }


def main():
    from time import sleep

    existing_files = sorted(glob("tokens/0x*.yaml"))
    id_to_addresses = map_entries_to_sets(existing_files, "address")
    slugs = map_entries_to_discrete(existing_files, "slug")

    api_listings = get_api_listings()
    api_slugs = {e["id"]: e["slug"] for e in api_listings}

    slugs.update(api_slugs)

    for (asset_id, asset_website_slug) in slugs.items():
        try:
            result = process_listing(asset_website_slug)
        except:
            logging.exception(
                "Final error when trying to process listing for '%s'",
                 asset_website_slug)
            continue

        (listing, current_addresses) = result

        if listing:
            assert listing["id"] == asset_id

            if asset_website_slug != listing["slug"]:
                logging.warning("'%s' redirected to slug '%s' when queried",
                                asset_website_slug, listing['slug'])

        existing_addresses = id_to_addresses.get(asset_id, set())
        # Deal with delisted assets and deprecated addresses
        if existing_addresses and listing is None:
            # listing is None when the page failed to fetch (404ed)
            logging.warning("'%s' has been delisted", asset_website_slug)
            for address in existing_addresses:
                update_token_entry(address, {
                    "status": "delisted",
                    "markets": [],
                    "rank": None
                })
        else:
            for address in existing_addresses - current_addresses:
                logging.warning("'%s' has deprecated %s", asset_website_slug,
                                address)
                update_token_entry(
                    address, {
                        "_DEPRECATED": True,
                        "status": "deprecated",
                        "markets": [],
                        "rank": None
                    })

        for address in current_addresses:
            write_token_entry(address, listing)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    main()
