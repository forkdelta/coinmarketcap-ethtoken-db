import yaml

YAML_WIDTH = 100
YAML_INDENT = 2


def read_entry(fn):
    with open(fn) as infile:
        return yaml.safe_load(infile)


def write_token_entry(address, listing):
    with open("tokens/{}.yaml".format(address), "w") as outfile:
        outfile.write(
            yaml.dump(
                dict(
                    address=address,
                    **{k: v
                       for (k, v) in listing.items() if v}),
                explicit_start=True,
                width=YAML_WIDTH,
                indent=YAML_INDENT,
                default_flow_style=False,
                allow_unicode=True))


def update_token_entry(address, partial_update):
    old_listing = read_entry("tokens/{}.yaml".format(address))
    old_listing.update(partial_update)
    del old_listing["address"]
    write_token_entry(address, old_listing)
