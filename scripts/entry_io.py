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
