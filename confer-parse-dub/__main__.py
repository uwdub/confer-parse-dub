import argparse
import json
import operator
import yaml


def parse_confer(config):
    # Parse the json.
    #
    # Currently requires the file start with an opening bracket, manually stripping any 'entities ='
    with open(config['file_input'], 'r') as f:
        parsed_json = json.load(f)

    # Organize the items into a list
    items = parsed_json.items()
    filtered_items = []
    for key_current, item_current in items:
        # Store the id on the item
        item_current['id'] = key_current

        filtered_items.append(item_current)

    items = filtered_items

    # Go through to apply our includes
    #
    # This 'works enough' but is probably not robust or formally defined
    filtered_items = []
    for item_current in items:
        match_include = True

        for include_current in config['include']:
            if 'type' in include_current:
                match_include &= include_current['type'] == item_current['type']
            if 'affiliation' in include_current:
                match_affiliation = False
                for author_current in item_current['authors']:
                    if include_current['affiliation'] in author_current['affiliation']:
                        match_affiliation = True
                match_include &= match_affiliation

        if match_include:
            filtered_items.append(item_current)

    items = filtered_items

    # Go through to apply our excludes
    #
    # This 'works enough' but is probably not robust or formally defined
    filtered_items = []
    for item_current in items:
        match_exclude = False

        for exclude_current in config['exclude']:
            if 'id' in exclude_current:
                match_exclude |= exclude_current['id'] == item_current['id']

        if not match_exclude:
            filtered_items.append(item_current)

    items = filtered_items

    # Remove fields we do not use which could be confusing
    filtered_items = []
    for item_current in items:
        del item_current['id']
        del item_current['abstract']
        del item_current['cAndB']
        del item_current['keywords']
        del item_current['subtype']
        del item_current['type']

        for author_current in item_current['authors']:
            del author_current['familyName']
            del author_current['givenName']
            del author_current['middleInitial']

            del author_current['city']
            del author_current['country']
            del author_current['dept']
            del author_current['institution']
            del author_current['location']

        filtered_items.append(item_current)

    items = filtered_items

    return items


def normalize(config, items):
    # Clean up author affiliations
    for item_current in items:
        for author_current in item_current['authors']:
            # Check our approved affiliations, try to match one for this author
            matched = False
            matched_affiliation = author_current['affiliation']

            for affiliation_current in config['affiliations']:
                if affiliation_current['match']['affiliation'] and \
                   author_current['affiliation'] in affiliation_current['match']['affiliation']:
                    matched = True
                    matched_affiliation = affiliation_current['affiliation']
                if affiliation_current['match']['name'] and \
                   author_current['name'] in affiliation_current['match']['name']:
                    matched = True
                    matched_affiliation = affiliation_current['affiliation']

            if not matched:
                print(matched_affiliation)

            author_current['affiliation'] = matched_affiliation

    # Sort them
    items.sort(
        key=operator.itemgetter('title')
    )
    items.sort(
        key=operator.itemgetter('hm'),
        reverse=True
    )
    items.sort(
        key=operator.itemgetter('award'),
        reverse=True
    )

    return items


def output_yaml(config, items):
    data = {
        'papers': items
    }
    with open(config['file_output'], 'w') as f:
        yaml.dump(
            data,
            stream=f,
            default_flow_style=False
        )


def main():
    parser = argparse.ArgumentParser(description='Conference data parser for DUB')
    parser.add_argument('-f', required=True, dest='file_config')
    args = parser.parse_args()

    with open(args.file_config, 'r') as f:
        config = yaml.load(f)

    items = parse_confer(config)
    items = normalize(config, items)
    output_yaml(config, items)

    # print('{} papers'.format(len(items)))
    # print('{} best paper award'.format(len([item for item in items if item['award'] == True])))
    # print('{} best paper honorable mention'.format(len([item for item in items if item['hm'] == True])))


if __name__ == '__main__':
    main()
