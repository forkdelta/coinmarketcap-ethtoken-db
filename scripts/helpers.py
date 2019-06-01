from bs4 import BeautifulSoup
import copy
from eth_utils import is_hex_address, to_checksum_address
import logging
from os.path import getmtime, isfile, join
import re
import requests
from time import time, sleep
from urllib.parse import urlparse
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
    Returns HTML content of the CoinMarketCap
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
        except requests.HTTPError:
            retries += 1
            logging.exception(
                "Error occurred while fetching page for '%s', sleeping %i, %s",
                slug, FETCH_ERROR_DELAY**retries,
                "retrying" if retries <= MAX_FETCH_RETRIES else "aborting")
            sleep(FETCH_ERROR_DELAY**retries)  # Sleep even if we are aborting

            if retries <= MAX_FETCH_RETRIES:
                continue
            else:
                raise
    return html_doc


def get_links_block(soup):
    selector = ".details-panel-item--links"
    links_block = soup.select(selector)
    assert (links_block is not None and len(links_block) == 1)
    return links_block[0]


KNOWN_TRACKER_SUFFIXES = (
    "ethplorer.io/address",
    "ethplorer.io/token",
    "etherscan.io/address",
    "etherscan.io/token",
)


def get_tracker_links(soup):
    """
    Returns a list of URls
    """
    tracker_url_predicate = lambda url: any(True for s in KNOWN_TRACKER_SUFFIXES if s in url)

    links_block = get_links_block(soup)
    trackers = filter(tracker_url_predicate,
                      (a["href"]
                       for a in links_block.find_all('a', href=True)))
    return list(trackers)


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
            logging.warn("Unknown tracker URL format: %s", tracker)

    return set([to_checksum_address(address) for address in addresses])


def get_ethereum_addresses(slug, soup=None):
    """
    Returns a set of Ethereum addresses for a CoinMarketCap-listed currency. The
    set may be empty if the CoinMarketCap listing does not link to any supported
    Ethereum chain browsers. The set may contain more than one element if the
    CoinMarketCap listing contains tracker URLs that resolve to different
    Ethereum addresses.

    Ethereum addresses are returned in lowercased 0x-prefixed hex format.
    """

    if soup is None:
        html_doc = fetch_currency_page(slug)
        soup = BeautifulSoup(html_doc, 'html.parser')

    tracker_links = get_tracker_links(soup)
    return resolve_tracker_addresses(tracker_links)


def get_listing_links(slug, soup=None):
    if soup is None:
        html_doc = fetch_currency_page(slug)
        soup = BeautifulSoup(html_doc, 'html.parser')

    links_block = get_links_block(soup)
    get_text_href_tuple = lambda node: (node.text.strip(), node["href"])
    return list(map(get_text_href_tuple, links_block.find_all('a', href=True)))


import bleach


def get_listing_description(slug, soup=None):
    if soup is None:
        html_doc = fetch_currency_page(slug)
        soup = BeautifulSoup(html_doc, 'html.parser')

    description_header_predicate = lambda tag: tag.name == "h2" and "About " in tag.text
    about_container = soup.find(description_header_predicate)
    if about_container:
        about_html_content = "\n".join(
            [str(el) for el in about_container.parent.find_all("p")])
        bleached_content = bleach.clean(about_html_content, strip=True)
        return bleached_content.strip()
    logging.debug("Unable to find description for '%s'", slug)


def get_listing_tags(slug, soup=None):
    if soup is None:
        html_doc = fetch_currency_page(slug)
        soup = BeautifulSoup(html_doc, 'html.parser')

    links_block = get_links_block(soup)
    return list(
        map(lambda node: node.text.strip(),
            links_block.find_all('span', class_="label-warning")))


def get_listing_rank(slug, soup=None):
    if soup is None:
        html_doc = fetch_currency_page(slug)
        soup = BeautifulSoup(html_doc, 'html.parser')

    links_block = get_links_block(soup)
    rank_text = links_block.find('span', class_="label-success")
    if rank_text:
        rank_value = rank_text.text.strip().split(' ')[-1]
        return int(rank_value)


def get_markets(slug, soup=None):
    if soup is None:
        html_doc = fetch_currency_page(slug)
        soup = BeautifulSoup(html_doc, 'html.parser')

    market_rows = soup.select("#markets-table tbody tr")
    markets = []
    for row in market_rows:
        cells = row.select("td")
        exchange_link = cells[1].find("a")
        pair_link = cells[2].find("a")
        markets.append({
            "exchange_name": exchange_link.text.strip(),
            "pair": pair_link.text.strip(),
            "url": pair_link["href"]
        })
    return sorted(markets, key=lambda m: m["exchange_name"] + m["pair"])


REDDIT_URL_RE = re.compile('reddit.com/(?:u|r)/(.+)\.embed', re.I)


def get_social(slug, soup=None):
    if soup is None:
        html_doc = fetch_currency_page(slug)
        soup = BeautifulSoup(html_doc, 'html.parser')

    social_links = []

    twitter_link = soup.find(id="social").find("a", class_="twitter-timeline")
    if twitter_link is not None:
        social_links.append(("Twitter", twitter_link["href"]))

    # Dirty hack to get reddit link out
    reddit_link = REDDIT_URL_RE.search(str(soup))
    if reddit_link is not None:
        subreddit_slug = reddit_link.group(1)
        social_links.append(
            ("Reddit", "https://www.reddit.com/r/{}".format(subreddit_slug)))

    return social_links


def read_entry(fn):
    with open(fn) as infile:
        return yaml.safe_load(infile)


YAML_WIDTH = 100
YAML_INDENT = 2


def write_token_entry(address, listing):
    with open("tokens/{}.yaml".format(address), "w") as outfile:
        outfile.write(
            yaml.dump(
                dict(address=address, **listing),
                explicit_start=True,
                width=YAML_WIDTH,
                indent=YAML_INDENT,
                default_flow_style=False,
                allow_unicode=True))


def get_listing_details(slug, soup):
    description = get_listing_description(slug, soup=soup)
    listing_links = get_listing_links(slug, soup=soup)
    social_links = get_social(slug, soup=soup)
    markets = get_markets(slug, soup=soup)
    rank = get_listing_rank(slug, soup=soup)
    tags = get_listing_tags(slug, soup=soup)

    details = dict(
        links=dict(**dict(listing_links), **dict(social_links)),
        tags=tags,
        rank=rank,
        markets=markets)

    if description:
        details["description"] = description

    return details


def process_listing(listing):
    slug = listing["website_slug"]

    html_doc = None
    retries = 0
    while not html_doc:
        try:
            html_doc = fetch_currency_page(slug)
        except requests.HTTPError:
            retries += 1
            logging.exception(
                "Error occurred while fetching page for '%s', sleeping %i, %s",
                slug, FETCH_ERROR_DELAY**retries,
                "retrying" if retries <= MAX_FETCH_RETRIES else "aborting")
            sleep(FETCH_ERROR_DELAY**retries)  # Sleep even if we are aborting

            if retries <= MAX_FETCH_RETRIES:
                continue
            else:
                raise

    soup = BeautifulSoup(html_doc, 'html.parser')

    eth_addresses = set(get_ethereum_addresses(slug, soup=soup))
    if len(eth_addresses) == 0:
        logging.debug("'%s' has no Ethereum address", slug)
        return (copy.deepcopy(listing), set())
    if len(eth_addresses) > 1:
        logging.info("'%s' has %i Ethereum addresses", slug,
                     len(eth_addresses))

    updated_listing = copy.deepcopy(listing)
    updated_listing.update(get_listing_details(slug, soup))
    return (updated_listing, eth_addresses)
