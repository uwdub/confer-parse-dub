import argparse
import json
import operator
import string
import sys
import titlecase
import xmltodict
import yaml


def parse_config(config):
    assert(isinstance(config['file_input'], str))
    assert(isinstance(config['file_input_type'], str))
    assert(config['file_input_type'] in ['confer'])
    assert(isinstance(config['file_output'], str))

    # for entry_name in config['names']:
    #     assert(isinstance(entry_name['name'], str))
    #     if 'match' in entry_name:
    #         assert(isinstance(entry_name['match'], list))
    #         for entry_name_match in entry_name['match']:
    #             assert(isinstance(entry_name_match, str))
    #
    # for entry_affiliation in config['affiliations']:
    #     assert(isinstance(entry_affiliation['affiliation'], str))
    #     if 'match' in entry_affiliation:
    #         assert(isinstance(entry_affiliation['match'], dict))
    #         if 'affiliation' in entry_affiliation['match']:
    #             assert (isinstance(entry_affiliation['match']['affiliation'], list))
    #             for entry_affiliation_match in entry_affiliation['match']['affiliation']:
    #                 assert(isinstance(entry_affiliation_match, str))
    #         if 'name' in entry_affiliation['match']:
    #             assert (isinstance(entry_affiliation['match']['name'], list))
    #             for entry_affiliation_match in entry_affiliation['match']['name']:
    #                 assert(isinstance(entry_affiliation_match, str))


def parse_confer(config):
    # Parse the json.
    #
    # Currently requires the file start with an opening bracket, need to manually strip any 'entities=' before that.
    with open(config['file_input'], 'r', encoding='utf-8') as f:
        parsed_json = json.load(f)

    # Convert into a list of items
    items = []
    for key_current, item_current in parsed_json.items():
        item_current['id'] = key_current
        items.append(item_current)

    # There are a bunch of completely empty affiliations to remove
    #
    # In the CHI 2019 data, every author has a empty 'secondary', their affiliation is in 'primary'
    for item_current in items:
        for author_current in item_current['authors']:
            author_current['affiliations'] = [author_current['primary']]
            if(
                author_current['secondary']['dept'] != '' or
                author_current['secondary']['institution'] != '' or
                author_current['secondary']['city'] != '' or
                author_current['secondary']['state'] != '' or
                author_current['secondary']['country'] != ''
            ):
                author_current['affiliations'].append(author_current['secondary'])

    # The CHI 2019 does not include a 'name' field, so construct it from components
    for item_current in items:
        for author_current in item_current['authors']:
            author_current['name'] = author_current['givenName']
            if author_current['middleInitial'] != '':
                author_current['name'] = '{} {}'.format(author_current['name'], author_current['middleInitial'])
            author_current['name'] = '{} {}'.format(author_current['name'], author_current['familyName'])
            author_current['name'] = author_current['name'].strip()

    # Apply our includes and excludes
    items = match_include(config, items)
    print('Matched {} includes'.format(len(items)))

    len_before_excludes = len(items)
    items = match_exclude(config, items)
    print('Matched {} excludes'.format(len_before_excludes - len(items)))

    # Normalize strings we care about to address Unicode, title case, and other consistency / format issues
    for item_current in items:
        item_current['title'] = normalize_title(item_current['title'])
        for author_current in item_current['authors']:
            author_current['name'] = normalize_text(author_current['name'])
            for affiliation_current in author_current['affiliations']:
                affiliation_current['dept'] = normalize_text(affiliation_current['dept'])
                affiliation_current['institution'] = normalize_text(affiliation_current['institution'])
                affiliation_current['city'] = normalize_text(affiliation_current['city'])
                affiliation_current['country'] = normalize_text(affiliation_current['country'])

    # Do our main work
    items = normalize_names(config=config, items=items)
    items = normalize_affiliation(config=config, items=items)
    items = sort_items(config=config, items=items)

    # Remove fields we do not further use which could be confusing
    for item_current in items:
        del item_current['abstract']
        del item_current['acmLink']
        del item_current['cbStatement']
        del item_current['communities']
        del item_current['contactEmail']
        del item_current['contactName']
        del item_current['keywords']
        del item_current['session']
        del item_current['subtype']
        del item_current['venue']

        for author_current in item_current['authors']:
            del author_current['familyName']
            del author_current['givenName']
            del author_current['middleInitial']

            del author_current['affiliations']
            del author_current['authorId']
            del author_current['primary']
            del author_current['rank']
            del author_current['role']
            del author_current['secondary']

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

        for include_current in config['include']:
            match_current = True
            if 'affiliation' in include_current:
                match_affiliation = False
                for author_current in item_current['authors']:
                    for affiliation_current in author_current['affiliations']:
                        if include_current['affiliation'].casefold() in affiliation_current['dept'].casefold():
                            match_affiliation = True
                        if include_current['affiliation'].casefold() in affiliation_current['institution'].casefold():
                            match_affiliation = True
                match_current &= match_affiliation
            if 'venue' in include_current:
                match_current &= include_current['venue'] == item_current['venue']
            if 'id' in include_current:
                match_current &= include_current['id'] == item_current['id']

            match_found |= match_current

        if match_found:
            filtered_items.append(item_current)

    return filtered_items


def normalize_names(config, items):
    # Clean up author names
    for item_current in items:
        for author_current in item_current['authors']:
            # Check our approved authors, try to match one for this author
            matches_found = []

            for standard_name_current in config['names']:
                if author_current['name'] == standard_name_current['name']:
                    matches_found.append(standard_name_current)
                elif 'match' in standard_name_current:
                    for match_current in standard_name_current['match']:
                        if author_current['name'] == match_current['name']:
                            matches_found.append(standard_name_current)

            if len(matches_found) == 1:
                # print(
                #     'Name Match:  "{}" matched to known name "{}"'.format(
                #         author_current['name'],
                #         matches_found[0]['name']
                #     )
                # )

                author_current['name'] = matches_found[0]['name']
            elif len(matches_found) == 0:
                print(
                    'No Name Match:'
                )
                print(
                    author_current['name'].encode(sys.getdefaultencoding(), 'backslashreplace').decode()
                )
            else:
                print(
                    'Multiple Name Matches:'
                )
                print(
                    author_current['name'].encode(sys.getdefaultencoding(), 'backslashreplace').decode()
                )

    return items


def normalize_affiliation(config, items):
    # Clean up author affiliations
    for item_current in items:
        for author_current in item_current['authors']:
            standardized_affiliations = []

            for affiliation_current in author_current['affiliations']:
                # Check our approved affiliations, try to match one for this author
                matches_found = []

                for standard_affiliation_current in config['affiliations']:
                    exclude_found = False
                    if 'exclude' in standard_affiliation_current:
                        for exclude_current in standard_affiliation_current['exclude']:
                            exclude_current_matches = True

                            if 'name' in exclude_current:
                                exclude_current_matches &= author_current['name'] == exclude_current['name']

                            exclude_found |= exclude_current_matches

                    if not exclude_found:
                        match_found = False

                        for match_current in standard_affiliation_current['match']:
                            match_current_matches = True

                            if 'name' in match_current:
                                match_current_matches &= author_current['name'] == match_current['name']
                            if 'affiliation' in match_current:
                                if 'dept' in match_current['affiliation']:
                                    match_current_matches &= affiliation_current['dept'] == match_current['affiliation']['dept']
                                if 'institution' in match_current['affiliation']:
                                    match_current_matches &= affiliation_current['institution'] == match_current['affiliation']['institution']

                            match_found |= match_current_matches

                        if match_found:
                            matches_found.append(standard_affiliation_current)

                if len(matches_found) == 1:
                    standard_affiliation_current = matches_found[0]['affiliation']
                    if standard_affiliation_current != '--ignore--':
                        standardized_affiliations.append(standard_affiliation_current)
                elif len(matches_found) == 0:
                    print(
                        'No Affiliation Match:  ' + author_current['name'] + ' ' + repr(affiliation_current).encode(sys.getdefaultencoding(), 'backslashreplace').decode()
                    )
                elif len(matches_found) > 1:
                    print(
                        'Multiple Affiliation Match:  ' + author_current['name'] + ' ' + json.dumps(affiliation_current, indent=2).encode(sys.getdefaultencoding(), 'backslashreplace').decode() + ' ' + json.dumps(matches_found, indent=2)
                    )

            if len(standardized_affiliations) > 1:
                for multiple_affiliation_current in config['multiple_affiliations']:
                    for match_current in multiple_affiliation_current['match']:
                        match_current_matches = True

                        if 'name' in match_current:
                            match_current_matches &= author_current['name'] == match_current['name']
                        if 'affiliations' in match_current:
                            match_current_matches &= set(standardized_affiliations) == set(match_current['affiliations'])

                        if match_current_matches:
                            standardized_affiliations = [multiple_affiliation_current['affiliation']]

            if len(standardized_affiliations) == 1:
                author_current['affiliation'] = standardized_affiliations[0]
            elif len(standardized_affiliations) == 0:
                print('No Standardized Affiliation:  ' + author_current['name'])
            elif len(standardized_affiliations) > 1:
                print('Multiple Standardized Affiliations:  ' + author_current['name'] + ' ' + repr(standardized_affiliations))

    return items


def sort_items(config, items):
    # Sort them
    for item_current in items:
        item_current['title_sort'] = normalize_title_sort(item_current['title'])
    items.sort(
        key=operator.itemgetter('title_sort')
    )
    for item_current in items:
        del item_current['title_sort']

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
    title = title.replace('Human-Ai', 'Human-AI')
    return title


def normalize_title_sort(title):
    return (''.join(c for c in title if c in string.ascii_letters + string.digits)).casefold()


def output_yaml(config, items):
    data = {
        'papers': items
    }
    with open(config['file_output'], 'w', encoding='utf-8') as f:
        yaml.safe_dump(
            data,
            stream=f,
            allow_unicode=True,
            default_flow_style=False
        )


def main():
    parser = argparse.ArgumentParser(description='Conference data parser for DUB')
    parser.add_argument('-f', required=True, dest='file_config')
    args = parser.parse_args()

    with open(args.file_config, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        parse_config(config)

    if config['file_input_type'] == 'confer':
        items = parse_confer(config)

#    items = normalize_items(config, items)
    output_yaml(config, items)

    print('{} papers'.format(len(items)))
    print('{} best paper award'.format(len([item for item in items if item['award'] == True])))
    print('{} best paper honorable mention'.format(len([item for item in items if item['hm'] == True])))


if __name__ == '__main__':
    main()
