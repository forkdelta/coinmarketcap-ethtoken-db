from glob import glob
from itertools import groupby
import logging
import requests

from helpers import (DEFAULT_HEADERS, process_listing)
from entry_io import (read_entry, write_token_entry)

CMC_LISTINGS_API_URL = "https://api.coinmarketcap.com/v2/listings/"


def get_api_listings():
    """
    Returns a list of CoinMarketCap-listed currencies via /v2/listings/ API endpoint.

    Returns: a list of dicts like so:
        [{'id': 1, 'name': 'Bitcoin', 'symbol': 'BTC', 'website_slug': 'bitcoin'}, ...]
    """
    r = requests.get(CMC_LISTINGS_API_URL, headers=DEFAULT_HEADERS)
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


def deprecate_token_entry(address):
    old_listing = read_entry("tokens/{}.yaml".format(address))
    old_listing.update({"_DEPRECATED": True, "markets": [], "rank": None})
    del old_listing["address"]
    write_token_entry(address, old_listing)


def main():
    from time import sleep

    existing_files = sorted(glob("tokens/0x*.yaml"))
    slugs = map_entries_to_discrete(existing_files, "slug")

    api_listings = get_api_listings()
    api_slugs = {e["id"]: e["website_slug"] for e in api_listings}

    slugs.update(api_slugs)

    id_to_addresses = map_entries_to_sets(existing_files, "address")

    for (asset_id, asset_website_slug) in slugs.items():
        try:
            result = process_listing(asset_website_slug)
        except:
            logging.exception(
                "Final error when trying to process listing for '%s'",
                asset_website_slug)
            continue

        (listing, current_addresses) = result
        assert not listing or listing["id"] == asset_id

        existing_addresses = id_to_addresses.get(asset_id, set())
        for address in existing_addresses - current_addresses:
            logging.warning("'%s' has deprecated %s", asset_website_slug,
                            address)
            deprecate_token_entry(address)

        for address in current_addresses:
            write_token_entry(address, listing)

    # TODO: Update website slugs in older fies when


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    main()
