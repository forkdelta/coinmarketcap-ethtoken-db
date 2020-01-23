import copy
import json
import logging
from os.path import getmtime, isfile, join
import re
from time import time, sleep
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from eth_utils import is_hex_address, to_checksum_address
import requests
import yaml

USER_AGENT = "CoinMarketCap Ethereum Tokens DB Builder (https://github.com/freeatnet/coinmarketcap-ethtoken-db)"
DEFAULT_HEADERS = {"User-Agent": USER_AGENT}

##
# Etherscan helpers

ETHERSCAN_TOKEN_URL = "https://etherscan.io/token/{}"


def get_etherescan_redirect_url(from_url):
    return requests.head(
        ETHERSCAN_TOKEN_URL.format(from_url),
        allow_redirects=True,
        headers=DEFAULT_HEADERS).url


##
# CoinMarketCap helpers

CACHE_PATH = ".cache"
CMC_LISTING_PAGE_URL = "https://coinmarketcap.com/currencies/{slug}/"
CMC_LISTING_PAGE_CACHE_AGE = 18 * 3600
MAX_FETCH_RETRIES = 3
FETCH_ERROR_DELAY = 8

requests_session = requests.Session()


def fetch_currency_page_with_requests(slug, cache=True, cache_file=None):
    logging.debug("Fetching page for '%s'", slug)

    page_url = CMC_LISTING_PAGE_URL.format(slug=slug)
    r = requests_session.get(page_url, headers=DEFAULT_HEADERS)
    r.raise_for_status()  # Raise error if status is not 200

    text = r.text

    if cache:
        with open(cache_file, "w") as f:
            f.write(text)
    return text


def fetch_currency_page(slug,
                        cache=True,
                        cache_only=False,
                        max_cache_age=CMC_LISTING_PAGE_CACHE_AGE):
    """
    Returns HTML content of the CoinMarketCap currency page given its slug.
    Optionally, uses and/or writes cache.
    """
    cache_file = join(CACHE_PATH, "{}.html".format(slug))
    if isfile(cache_file) and getmtime(cache_file) > time() - max_cache_age:
        logging.debug("Using cache for '%s'", slug)
        with open(cache_file) as f:
            return f.read()
    elif cache_only:
        raise Exception("cache_only and no cache file available")

    html_doc = None
    retries = 0

    sleep(6)  # Ensure we sleep before making network requests

    while not html_doc:
        try:
            html_doc = fetch_currency_page_with_requests(
                slug, cache, cache_file)
        except requests.HTTPError as err:
            retries += 1
            logging.exception(
                "Error occurred while fetching page for '%s', sleeping %i, %s",
                slug, FETCH_ERROR_DELAY**retries,
                "retrying" if retries <= MAX_FETCH_RETRIES else "aborting")
            # Sleep even if we are aborting
            sleep(FETCH_ERROR_DELAY**retries)

            if retries > 1 and err.response.status_code == 404:
                raise
            if retries <= MAX_FETCH_RETRIES:
                sleep(FETCH_ERROR_DELAY)
                continue
            else:
                raise
    return html_doc


def resolve_tracker_addresses(trackers):
    """
    Given a list of Ethereum tracker URLs, returns a set of lowercased,
    0x-prefixed Ethereum hex addresses.
    """
    addresses = set()
    for tracker in trackers:
        path = urlparse(tracker).path
        presumed_address = path.split('/')[-1]
        if is_hex_address(presumed_address):
            addresses.add(presumed_address.lower())
        elif "etherscan.io" in tracker:
            logging.debug(
                "Trying to resolve '%s' as a custom etherscan.io address",
                tracker)
            redirect_url = get_etherescan_redirect_url(presumed_address)
            resolved_address = redirect_url.strip('/').split('/')[-1]
            if is_hex_address(resolved_address):
                logging.debug("Resolved '%s' as %s", tracker, resolved_address)
                addresses.add(resolved_address.lower())
            else:
                logging.error("Could not resolve etherscan.io: '%s'", tracker)
        else:
            logging.warning("Unknown tracker URL format: %s", tracker)

    return {to_checksum_address(address) for address in addresses}


KNOWN_TRACKER_SUFFIXES = (
    "ethplorer.io/address",
    "ethplorer.io/token",
    "etherscan.io/address",
    "etherscan.io/token",
    "etherscan.io/token",
    "blockchair.com/ethereum/erc-20/token",
)


def get_ethereum_addresses(next_data):
    """
    Returns a set of Ethereum addresses for a list of explorer links. The
    set may be empty if the CoinMarketCap listing does not link to any supported
    Ethereum chain browsers. The set may contain more than one element if the
    CoinMarketCap listing contains tracker URLs that resolve to different
    Ethereum addresses.

    Ethereum addresses are returned in checksummed 0x-prefixed hex format.
    """
    tracker_url_predicate = lambda url: any(True for s in KNOWN_TRACKER_SUFFIXES if s in url)

    base_data = get_asset_data(next_data, "info")
    explorer_links = base_data["urls"]["explorer"]

    ethereum_addresses = resolve_tracker_addresses(
        filter(tracker_url_predicate, explorer_links))

    if base_data["platform"] and base_data["platform"]["name"] == "Ethereum":
        token_address = base_data["platform"]["token_address"]
        if is_hex_address(token_address):
            ethereum_addresses.add(to_checksum_address(token_address))

    return ethereum_addresses


import bleach

STUB_DESCRIPTION_DETERMINANT = "is a cryptocurrency token and operates on the Ethereum platform"


def get_listing_description(asset_data):
    description = asset_data["description"]
    if STUB_DESCRIPTION_DETERMINANT in description:
        return None

    bleached_content = bleach.clean(description, strip=True)
    return bleached_content.strip()


def get_links(asset_data):
    return {k: v for (k, v) in asset_data["urls"].items() if v}


MARKET_PAIRS_API_URL = "https://web-api.coinmarketcap.com/v1/cryptocurrency/market-pairs/latest?aux=market_url,notice&id={asset_id}&limit=100&sort=cmc_rank"
NO_MARKETS_MESSAGE = "No matching markets found."


def fetch_markets(asset_id):
    markets_url = MARKET_PAIRS_API_URL.format(asset_id=asset_id)
    try:
        r = None
        retries = 0
        while not r:
            try:
                r = requests_session.get(markets_url, headers=DEFAULT_HEADERS)
                r.raise_for_status()
            except requests.HTTPError as err:
                retries += 1
                logging.exception(
                    "Error occurred while fetching markets for '%i', sleeping %i, %s",
                    asset_id, FETCH_ERROR_DELAY**retries,
                    "retrying" if retries <= MAX_FETCH_RETRIES else "aborting")
                # Sleep even if we are aborting
                sleep(FETCH_ERROR_DELAY**retries)

                if retries > 1 and err.response.status_code in (400, 404):
                    raise
                if retries <= MAX_FETCH_RETRIES:
                    sleep(FETCH_ERROR_DELAY)
                    continue
                else:
                    raise

        response_json = r.json()
        return response_json["data"]["market_pairs"]
    except requests.exceptions.HTTPError:
        if NO_MARKETS_MESSAGE in r.text:
            return []
        raise


def get_markets(asset_id):
    markets = fetch_markets(asset_id)
    return [
        dict(
            exchange_id=v["exchange"]["id"],
            exchange_name=v["exchange"]["name"],
            pair=v["market_pair"],
            url=v["market_url"],
            base=v["market_pair_base"],
            quote=v["market_pair_quote"],
        ) for v in markets
    ]


BASE_DATA_KEYS = (
    "id",
    "name",
    "symbol",
    "slug",
    "notice",
    "date_added",
    "tags",
    "category",
    "status",
)


def get_listing_details(next_data):
    base_data = get_asset_data(next_data, "info")
    links = get_links(base_data)
    description = get_listing_description(base_data)

    quotes_latest_data = get_asset_data(next_data, "quotesLatest")
    rank = None
    markets = []
    if quotes_latest_data:
        rank = quotes_latest_data["cmc_rank"]
    if quotes_latest_data and quotes_latest_data["num_market_pairs"] > 0:
        markets = get_markets(base_data["id"])

    base_details = {k: base_data[k] for k in BASE_DATA_KEYS if base_data[k]}
    details = dict(
        **base_details,
        links=links,
        description=description,
        markets=markets,
        rank=rank)

    return details


def get_next_data(soup):
    next_data_json = soup.find("script", id="__NEXT_DATA__").text
    next_data = json.loads(next_data_json)
    return next_data


def get_asset_data(next_data, key):
    data_container = next_data["props"]["initialState"]["cryptocurrency"][key]
    asset_container = data_container.get("data") or {}
    asset_data = next(iter(asset_container.values()), None)
    return asset_data


def process_listing(slug):
    try:
        html_doc = fetch_currency_page(slug)
    except requests.exceptions.HTTPError as err:
        logging.info("'%s' returned code %i", slug, err.response.status_code)
        return (None, set())

    soup = BeautifulSoup(html_doc, 'html.parser')

    next_data = get_next_data(soup)
    eth_addresses = get_ethereum_addresses(next_data)
    if not eth_addresses:
        logging.debug("'%s' has no Ethereum address", slug)
        return ({}, set())
    if len(eth_addresses) > 1:
        logging.info("'%s' has %i Ethereum addresses", slug,
                     len(eth_addresses))

    return (get_listing_details(next_data), eth_addresses)
