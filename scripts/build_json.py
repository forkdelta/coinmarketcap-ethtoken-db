from glob import glob
import json
import yaml

from helpers import read_entry

INDEX_KEYS = ["id", "address", "name", "symbol", "website_slug"]


def abridged_entry(entry):
    return {k: entry[k] for k in INDEX_KEYS}


if __name__ == "__main__":
    files = sorted(glob("tokens/0x*.yaml"))
    entries = list(read_entry(fn) for fn in files)
    for entry in entries:
        json_fn = "tokens/{}.json".format(entry["address"])
        with open(json_fn, "w") as outfile:
            json.dump(entry, outfile, separators=(',', ':'))

    with open("tokens/bundle.json", "w") as outfile:
        json.dump(entries, outfile, separators=(',', ':'))

    with open("tokens/index.json", "w") as outfile:
        json.dump(
            list(
                abridged_entry(entry) for entry in entries
                if not entry.get("_DEPRECATED", False)),
            outfile,
            separators=(',', ':'))

    with open("tokens/deprecated.json", "w") as outfile:
        json.dump(
            list(
                abridged_entry(entry) for entry in entries
                if entry.get("_DEPRECATED", False)),
            outfile,
            separators=(',', ':'))
