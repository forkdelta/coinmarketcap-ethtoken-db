from glob import glob
from itertools import groupby
import logging
import requests

from helpers import (DEFAULT_HEADERS, process_listing)
from entry_io import (read_entry, write_token_entry)

CMC_LISTINGS_API_URL = "https://api.coinmarketcap.com/v2/listings/"


def get_listings():
    """
    Returns a list of CoinMarketCap-listed currencies via /v2/listings/ API endpoint.

    Returns: a list of dicts like so:
        [{'id': 1, 'name': 'Bitcoin', 'symbol': 'BTC', 'website_slug': 'bitcoin'}, ...]
    """
    r = requests.get(CMC_LISTINGS_API_URL, headers=DEFAULT_HEADERS)
    return r.json()["data"]


def map_existing_entries(files, exclude_deprecated=True):
    """
    Returns a hash keyed by CoinMarketCap asset ID with sets of Ethereum addresses
    known to be associated with that asset ID.
    """
    entries = ((entry["id"], entry["address"])
               for entry in (read_entry(fn) for fn in files)
               if not (exclude_deprecated and entry.get("_DEPRECATED", False)))

    return {
        e[0]: set(g[1] for g in e[1])
        for e in groupby(sorted(entries), key=lambda e: e[0])
    }


def deprecate_token_entry(address):
    old_listing = read_entry("tokens/{}.yaml".format(address))
    old_listing.update({"_DEPRECATED": True})
    del old_listing["address"]
    write_token_entry(address, old_listing)


def main(listings):
    from time import sleep

    id_to_address = map_existing_entries(sorted(glob("tokens/0x*.yaml")))

    for api_listing in listings:
        try:
            result = process_listing(api_listing)
        except:
            logging.exception(
                "Final error when trying to process listing for '%s'",
                api_listing["website_slug"])
            continue

        (listing, current_addresses) = result

        existing_addresses = id_to_address.get(api_listing["id"], set())
        for address in existing_addresses - current_addresses:
            logging.warning("'%s' has deprecated %s",
                            api_listing["website_slug"], address)
            deprecate_token_entry(address)

        for address in current_addresses:
            write_token_entry(address, listing)

    listings_ids = [e["id"] for e in listings]
    ids_removed_from_listings = id_to_address.keys() - listings_ids
    for removed_id in ids_removed_from_listings:
        for removed_asset_address in id_to_address[removed_id]:
            deprecate_token_entry(removed_asset_address)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)

    main(get_listings())
