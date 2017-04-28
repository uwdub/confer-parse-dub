import argparse
import json
import operator
import sys
import titlecase
import xmltodict
import yaml


def parse_confer(config):
    # Parse the json.
    #
    # Currently requires the file start with an opening bracket, manually stripping any 'entities ='
    with open(config['file_input'], 'r', encoding='utf-8') as f:
        parsed_json = json.load(f)

    # Organize the file into a list as expected
    items = parsed_json.items()
    filtered_items = []
    for key_current, item_current in items:
        # Store the id on the item
        item_current['id'] = key_current

        filtered_items.append(item_current)

    items = filtered_items

    # Apply our includes and excludes
    items = match_include(config, items)
    items = match_exclude(config, items)

    # Remove fields we do not use which could be confusing
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

    # Normalize strings to deal with Unicode, title case, and other issues
    for item_current in items:
        item_current['title'] = normalize_title(item_current['title'])
        for author_current in item_current['authors']:
            author_current['name'] = normalize_text(author_current['name'])
            author_current['affiliation'] = normalize_text(author_current['affiliation'])

    return items


def parse_proceedings(config):
    # Parse the proceedings xml file.
    with open(config['file_input'], 'rb') as f:
        parsed_xml = xmltodict.parse(f, encoding='utf-8')

    # Get our paper list from the XML
    items = parsed_xml['proceedings']['paper_list']['paper']

    # Organize the file into a list as expected
    filtered_items = []
    for item_current in items:
        # Rename @id to id for consistency
        item_current['id'] = item_current['@id']
        del item_current['@id']

        # Rename author to authors for consistency
        item_current['authors'] = item_current['author']
        del item_current['author']
        # Make single-author papers still have a list of authors
        if isinstance(item_current['authors'], dict):
            item_current['authors'] = [item_current['authors']]
        # Convert the ordereddict to a base dict
        item_current['authors'] = [dict(author_current) for author_current in item_current['authors']]

        # No award info in this file
        item_current['award'] = False
        item_current['hm'] = False

        # Convert the ordereddict to a base dict
        filtered_items.append(dict(item_current))

    items = filtered_items

    # Apply our includes and excludes
    items = match_include(config, items)
    items = match_exclude(config, items)

    # Remove fields we do not use which could be confusing
    for item_current in items:
        del item_current['id']
        del item_current['abstract']
        del item_current['startpage']

    # Normalize strings to deal with Unicode, title case, and other issues
    for item_current in items:
        item_current['title'] = normalize_title(item_current['title'])
        for author_current in item_current['authors']:
            author_current['name'] = normalize_text(author_current['name'])
            author_current['affiliation'] = normalize_text(author_current['affiliation'])

    return items


def match_exclude(config, items):
    # Go through to apply our excludes
    #
    # This 'works enough' but is probably not robust or formally defined
    filtered_items = []
    for item_current in items:
        match_exclude = False

        if config['exclude']:
            for exclude_current in config['exclude']:
                if 'id' in exclude_current:
                    match_exclude |= exclude_current['id'] == item_current['id']

        if not match_exclude:
            filtered_items.append(item_current)

    return filtered_items


def match_include(config, items):
    # Go through to apply our includes
    #
    # This 'works enough' but is probably not robust or formally defined
    filtered_items = []
    for item_current in items:
        match_found = False

        if config['include']:
            for include_current in config['include']:
                match_current = True
                if 'type' in include_current:
                    match_current &= include_current['type'] == item_current['type']
                if 'affiliation' in include_current:
                    match_affiliation = False
                    for author_current in item_current['authors']:
                        if include_current['affiliation'] in author_current['affiliation']:
                            match_affiliation = True
                    match_current &= match_affiliation
                if 'id' in include_current:
                    match_current &= include_current['id'] == item_current['id']

                match_found |= match_current

        if match_found:
            filtered_items.append(item_current)

    return filtered_items


def normalize_items(config, items):
    # Clean up author names
    for item_current in items:
        for author_current in item_current['authors']:
            # Check our approved authors, try to match one for this author
            matched = False
            matched_name = author_current['name']

            for name_current in config['names']:
                if author_current['name'] == name_current['name']:
                    matched = True
                if name_current.get('match', None) and \
                   author_current['name'] in name_current['match']:
                    matched = True
                    matched_name = name_current['name']

            if not matched:
                print(
                    'No Name Match:  ' + author_current['name'].encode(sys.getdefaultencoding(), 'backslashreplace').decode()
                )

            author_current['name'] = matched_name

    # Clean up author affiliations
    for item_current in items:
        for author_current in item_current['authors']:
            # Check our approved affiliations, try to match one for this author
            matched = False
            matched_affiliation = author_current['affiliation']

            if not matched:
                for affiliation_current in config['affiliations']:
                    test_names = affiliation_current.get('match', {}).get('name', [])
                    test_names = test_names if test_names is not None else []

                    if author_current['name'] in test_names:
                        matched = True
                        matched_affiliation = affiliation_current['affiliation']

            if not matched:
                for affiliation_current in config['affiliations']:
                    test_affiliations = affiliation_current.get('match', {}).get('affiliation', [])
                    test_affiliations = test_affiliations if test_affiliations is not None else []

                    if author_current['affiliation'] in test_affiliations:
                        matched = True
                        matched_affiliation = affiliation_current['affiliation']

            if not matched:
                for affiliation_current in config['affiliations']:
                    if author_current['affiliation'] == affiliation_current['affiliation']:
                        matched = True

            if not matched:
                print(
                    'No Affiliation Match:  ' + repr(author_current).encode(sys.getdefaultencoding(), 'backslashreplace').decode()
                )

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


def normalize_text(text):
    text = text.replace('\u2019', '\'')
    text = text.replace('\u201C', '"')
    text = text.replace('\u201D', '"')
    return text


def normalize_title(title):
    title = normalize_text(title)
    title = titlecase.titlecase(title)
    title = title.strip()
    title = title.replace('in Situ', 'In Situ')
    return title


def output_yaml(config, items):
    data = {
        'papers': items
    }
    with open(config['file_output'], 'w', encoding='utf-8') as f:
        yaml.safe_dump(
            data,
            stream=f,
            default_flow_style=False
        )


def main():
    parser = argparse.ArgumentParser(description='Conference data parser for DUB')
    parser.add_argument('-f', required=True, dest='file_config')
    args = parser.parse_args()

    with open(args.file_config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    if config['file_input_type'] == 'confer':
        items = parse_confer(config)
    elif config['file_input_type'] == 'proceedings':
        items = parse_proceedings(config)

    items = normalize_items(config, items)
    output_yaml(config, items)

    # print('{} papers'.format(len(items)))
    # print('{} best paper award'.format(len([item for item in items if item['award'] == True])))
    # print('{} best paper honorable mention'.format(len([item for item in items if item['hm'] == True])))


if __name__ == '__main__':
    main()
