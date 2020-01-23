from glob import glob
from itertools import groupby
import re

from entry_io import (read_entry, write_token_entry)

OVERRIDES = {"Technical Documentation": "technical_doc"}


def update_key_format(k):
    human_k = re.sub(r' (\d+)$', '', k)
    return OVERRIDES.get(human_k, human_k.lower().replace(' ', '_'))


def convert_links(links):
    link_tuples = [(update_key_format(k), v) for (k, v) in links.items()]
    return {
        group_name: [value for (_, value) in name_value_tuples]
        for (group_name, name_value_tuples
             ) in groupby(sorted(link_tuples), key=lambda e: e[0])
    }


entry_files = sorted(glob("tokens/0x*.yaml"))
for entry in (read_entry(fn) for fn in entry_files):
    address = entry.pop("address")
    entry.update({
        "markets": [],
        "links": convert_links(entry['links']),
    })
    if "tags" in entry:
        del entry["tags"]
    del entry["website_slug"]
    write_token_entry(address, entry)
