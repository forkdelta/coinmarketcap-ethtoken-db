# coinmarketcap-ethtoken-db
A database of Ethereum tokens on [CoinMarketCap.com](https://coinmarketcap.com) in a machine-friendly format. Contains CoinMarketCap 
listings that link to an Ethereum tracker. Each entry includes basic information (name, symbol, CoinMarketCap 
ID and slug), links (including Twitter, Reddit, when available), and markets links. Not intended as a source for 
market data (see [CoinMarketCap API](https://coinmarketcap.com/api/) for that).

Contributions welcome.

## How to access the data

The base of the URLs for the following examples is https://forkdelta.github.io/.

## REST-like API

### `GET /coinmarketcap-ethtoken-db/tokens/index.json`
The `index.json` file contains abridged entries for every token, sorted by token address (effectively random).

Request:
```
GET /coinmarketcap-ethtoken-db/tokens/index.json
```

Response:
```json
[
  {
    "id": 2617,
    "address": "0x001f0aa5da15585e5b2305dbab2bac425ea71007",
    "name": "IP Exchange",
    "symbol": "IPSX",
    "website_slug": "ip-exchange"
  },
  …
]
```

### `GET /coinmarketcap-ethtoken-db/tokens/:address.json`
A separate JSON file is available for every token, accessible as `:address.json`:

Request:
```
GET /coinmarketcap-ethtoken-db/tokens/0x001f0aa5da15585e5b2305dbab2bac425ea71007.json
```

Response:
```json
{
  "address": "0x001f0aa5da15585e5b2305dbab2bac425ea71007",
  "id": 2617,
  "links": {
    "Announcement": "https://bitcointalk.org/index.php?topic=2897132.new#new",
    "Chat": "https://t.me/IPExchange",
    "Explorer": "https://etherscan.io/token/0x001f0aa5da15585e5b2305dbab2bac425ea71007",
    "Explorer 2": "https://ethplorer.io/address/0x001f0aa5da15585e5b2305dbab2bac425ea71007",
    "Reddit": "https://www.reddit.com/r/IPSX",
    "Twitter": "https://twitter.com/ipexchange1",
    "Website": "https://ip.sx/"
  },
  "markets": [
    {
      "exchange_name": "Bibox",
      "pair": "IPSX/ETH",
      "url": "https://www.bibox.com/exchange?coinPair=IPSX_ETH"
    }
    …
  ],
  "name": "IP Exchange",
  "symbol": "IPSX",
  "website_slug": "ip-exchange"
}
```

## One-shot API
The entire database is available as `bundle.json`, which contains a JSON array of all data included 
in the individual files.

Request:
```
GET /coinmarketcap-ethtoken-db/tokens/bundle.json
```

Response:
```json
[
  {
    "address": "0x001f0aa5da15585e5b2305dbab2bac425ea71007",
    "id": 2617,
    "links": {
      …
    },
    "markets": [
      …
    ],
    "name": "IP Exchange",
    "symbol": "IPSX",
    "website_slug": "ip-exchange"
  },
  {
    "address": "0x006bea43baa3f7a6f765f14f10a1a1b08334ef45",
    "id": 1861,
    "links": {
      …
    },
    "markets": [
      …
    ],
    "name": "Stox",
    "symbol": "STX",
    "website_slug": "stox"
  },
  …
]
```


## Attribution
Data provided by coinmarketcap.com. If you use data contained in this repository, you must clearly cite 
coinmarketcap.com as the original source.

> Am I allowed to use content (screenshots, data, graphs, etc.) for one of my personal projects and/or commercial use? 
> Absolutely! Feel free to use any content as you see fit. We kindly ask that you cite us as a source.
— https://coinmarketcap.com/faq/
