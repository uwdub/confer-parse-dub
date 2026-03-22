import argparse
import json
import operator
import pprint
import pyperclip
import re
import string
import sys
import titlecase
import xmltodict
import yaml


def parse_config(config):
    assert(isinstance(config['file_input'], str))
    assert(isinstance(config['file_input_type'], str))
    assert(config['file_input_type'] in ['sigchi program'])
    assert(isinstance(config['file_output'], str))


def parse_sigchi_program(config):
    # Parse the json.
    #
    # Requires the file start with an opening bracket.
    with open(config['file_input'], 'r', encoding='utf-8') as f:
        parsed_json = json.load(f)

    # Populate these items
    items = parsed_json['contents']

    # Simplify for our needs
    for content_current in items:
        if 'abstract' in content_current:
            del content_current['abstract']
        if 'keywords' in content_current:
            del content_current['keywords']
        if 'tags' in content_current:
            del content_current['tags']

        if 'award' in content_current:
            if content_current['award'] == 'BEST_PAPER':
                content_current['bestpaper'] = True
            else:
                content_current['bestpaper'] = False

            if content_current['award'] == 'HONORABLE_MENTION':
                content_current['honorablemention'] = True
            else:
                content_current['honorablemention'] = False

            del content_current['award']
        else:
            content_current['bestpaper'] = False
            content_current['honorablemention'] = False

        if 'doi' in content_current:
            match = re.search('https://doi.org/(.+)', content_current['doi'])
            if match:
                content_current['doi'] = 'https://dl.acm.org/doi/abs/' + match.group(1)

        if 'videos' in content_current:
            for video_current in content_current['videos']:
                if video_current['type'] == 'Video preview':
                    content_current['videopreview'] = video_current['url']

            del content_current['videos']

    # Go through content to see which match our criteria
    filtered_items = []
    for content_current in items:
        if match_include(config, parsed_json, content_current):
            filtered_items.append(content_current)
    items = filtered_items

    # Go through to remove any excludes
    filtered_items = []
    for content_current in items:
        if not match_exclude(config, parsed_json, content_current):
            filtered_items.append(content_current)
    items = filtered_items

    # Expand names from personId
    for content_current in items:
        for author_current in content_current['authors']:
            author_match = next(author_test for author_test in parsed_json['people'] if author_test['id'] == author_current['personId'])

            author_names = []
            if 'firstName' in author_match:
                author_names.append(author_match['firstName'])
            if 'middleInitial' in author_match:
                author_names.extend(author_match['middleInitial'].strip('.').split('.'))
            if 'lastName' in author_match:
                author_names.append(author_match['lastName'])

            author_current['name'] = ' '.join(author_names)
            del author_current['personId']

    # Normalize names
    items = normalize_names(config, items)

    # Normalize affiliations
    items = normalize_affiliations(config, items)

    # Normalize title
    for content_current in items:
        content_current['title'] = normalize_title(content_current['title'])

    # Sort publications
    items = sort_items(config, items)

    # print(json.dumps(items, indent=2))

    # # Convert into a list of items
    # for key_current, item_current in parsed_json.items():
    #     item_current['id'] = key_current
    #     items.append(item_current)
    #
    # # There are a bunch of completely empty affiliations to remove
    # #
    # # In the CHI 2019 data, every author has a empty 'secondary', their affiliation is in 'primary'
    # for item_current in items:
    #     for author_current in item_current['authors']:
    #         author_current['affiliations'] = [author_current['primary']]
    #         if(
    #                 author_current['secondary']['dept'] != '' or
    #                 author_current['secondary']['institution'] != '' or
    #                 author_current['secondary']['city'] != '' or
    #                 author_current['secondary']['state'] != '' or
    #                 author_current['secondary']['country'] != ''
    #         ):
    #             author_current['affiliations'].append(author_current['secondary'])
    #
    #
    # # Normalize strings we care about to address Unicode, title case, and other consistency / format issues
    # for item_current in items:
    #     item_current['title'] = normalize_title(item_current['title'])
    #     for author_current in item_current['authors']:
    #         author_current['name'] = normalize_text(author_current['name'])
    #         for affiliation_current in author_current['affiliations']:
    #             affiliation_current['dept'] = normalize_text(affiliation_current['dept'])
    #             affiliation_current['institution'] = normalize_text(affiliation_current['institution'])
    #             affiliation_current['city'] = normalize_text(affiliation_current['city'])
    #             affiliation_current['country'] = normalize_text(affiliation_current['country'])
    #
    # # Do our main work
    # items = normalize_names(config=config, items=items)
    # items = normalize_affiliation(config=config, items=items)
    # items = sort_items(config=config, items=items)
    #
    # # Remove fields we do not further use which could be confusing
    # for item_current in items:
    #     del item_current['abstract']
    #     del item_current['acmLink']
    #     del item_current['cbStatement']
    #     del item_current['communities']
    #     del item_current['contactEmail']
    #     del item_current['contactName']
    #     del item_current['keywords']
    #     del item_current['session']
    #     del item_current['subtype']
    #     del item_current['venue']
    #
    #     for author_current in item_current['authors']:
    #         del author_current['familyName']
    #         del author_current['givenName']
    #         del author_current['middleInitial']
    #
    #         del author_current['affiliations']
    #         del author_current['authorId']
    #         del author_current['primary']
    #         del author_current['rank']
    #         del author_current['role']
    #         del author_current['secondary']
    #
    return items


def match_exclude(config, parsed_json, content_current):
    for exclude_current in config['exclude']:
        match_current = True

        if match_current and 'id' in exclude_current:
            match_current &= 'id' in content_current and exclude_current['id'] == content_current['id']

        if match_current:
            return True

    return False

    # # Go through to apply our excludes
    # #
    # # This 'works enough' but is probably not robust or formally defined
    # filtered_items = []
    # for item_current in items:
    #     match_exclude = False
    #
    #     if config['exclude']:
    #         for exclude_current in config['exclude']:
    #             if 'id' in exclude_current:
    #                 match_exclude |= exclude_current['id'] == item_current['id']
    #
    #     if not match_exclude:
    #         filtered_items.append(item_current)
    #
    # return filtered_items


def match_include(config, parsed_json, content_current):
    for include_current in config['include']:
        match_current = True

        if match_current and 'id' in include_current:
            match_current &= 'id' in content_current and include_current['id'] == content_current['id']

        if match_current and 'affiliation' in include_current:
            match_affiliation = False
            for author_current in content_current['authors']:
                for affiliation_current in author_current['affiliations']:
                    if include_current['affiliation'].casefold() in affiliation_current['institution'].casefold():
                        match_affiliation = True
            match_current &= match_affiliation

        # For debugging, print content that matches affiliation
        # if match_affiliation:
        #     print('Content matched affiliation:')
        #     print(json.dumps(content_current, indent=2))

        if match_current and 'trackId' in include_current:
            match_current &= 'trackId' in content_current and include_current['trackId'] == content_current['trackId']

        # if match_current and 'typeId' in include_current:
        #     match_current &= 'typeId' in content_current and include_current['typeId'] == content_current['typeId']

        if match_current:
            return True

        # For debugging, print content that matches affiliation but was then rejected
        # if match_affiliation:
        #     print('Content matched affiliation but was then rejected:')
        #     print(json.dumps(content_current, indent=2))

    return False


def normalize_names(config, items):
    unmatched_authors = []

    # Clean up author names
    for item_current in items:
        for author_current in item_current['authors']:
            # Clean it up
            author_current['name'] = normalize_text(author_current['name'])

            # Check our approved authors, try to match one for this author
            matches_found = []

            for standard_name_current in config['names']:
                # Exact match
                if author_current['name'] == standard_name_current['name']:
                    matches_found.append(standard_name_current)
                # Exact match to any in our list of alternatives
                elif 'match' in standard_name_current:
                    for match_current in standard_name_current['match']:
                        if author_current['name'] == match_current['name']:
                            matches_found.append(standard_name_current)

            if len(matches_found) == 1:
                # For debugging, print name matches
                # print(
                #     'Name Match:  "{}" matched to known name "{}"'.format(
                #         author_current['name'],
                #         matches_found[0]['name']
                #     )
                # )

                author_current['name'] = matches_found[0]['name']
            elif len(matches_found) == 0:
                print('No Author Match:')
                print(author_current)

                unmatched_authors.append(author_current)
            else:
                print('Multiple Author Match:')
                print(author_current)
                print(matches_found)

                assert False

    if unmatched_authors:
        unmatched_authors = sorted(
            unmatched_authors,
            key=lambda author_sort: author_sort["name"],
        )

        pyperclip.copy(
            '\n'.join(
                [
                    "  - name: '{}'".format(author_current['name'])
                    for author_current in unmatched_authors
                ]
            )
        )

    assert len(unmatched_authors) == 0

    return items


def normalize_affiliations(config, items):
    unmatched_authors = []

    for item_current in items:
        for author_current in item_current['authors']:
            # Check for a canonical affiliation for this author
            matches_found = []

            # Normalize strings before normalizing structure
            for affiliation_author_current in author_current['affiliations']:
                affiliation_author_current['institution'] = normalize_text(affiliation_author_current['institution'])
                affiliation_author_current['dsl'] = normalize_text(affiliation_author_current['dsl'])

            for normalized_affiliation_current in config['affiliations']:
                # # Single-affiliation exact match (can't happen anymore, multiple fields in the json)
                # if [normalized_affiliation_current['canonical']] == author_current['affiliations']:
                #     matches_found.append(normalized_affiliation_current)

                # If a match field exists, match to any pattern found in the list
                if 'match' in normalized_affiliation_current:
                    for match_pattern_current in normalized_affiliation_current['match']:
                        # Within a particular pattern, match everything that is specified
                        match_current = True

                        # Match to a specific person
                        if 'name' in match_pattern_current:
                            match_current &= match_pattern_current['name'] == author_current['name']

                        # Match to an affiliation list, requires matching all affiliations in both lists
                        if 'affiliations' in match_pattern_current:
                            matched_affiliations = []

                            for affiliation_author_current in author_current['affiliations']:
                                for affiliation_pattern_current in match_pattern_current['affiliations']:
                                    # Require a match on everything
                                    affiliation_match_current = True

                                    if 'institution' in affiliation_pattern_current:
                                        affiliation_match_current &= affiliation_pattern_current['institution'] == affiliation_author_current['institution']
                                    if 'dsl' in affiliation_pattern_current:
                                        affiliation_match_current &= affiliation_pattern_current['dsl'] == affiliation_author_current['dsl']

                                    # If we match this pattern, track that and stop further matching of it
                                    if affiliation_match_current:
                                        matched_affiliations.append(affiliation_author_current)
                                        break

                            match_current &= (
                                len(matched_affiliations) == len(match_pattern_current['affiliations']) and
                                len(matched_affiliations) == len(author_current['affiliations'])
                            )

                        # Track how many we match
                        if match_current:
                            # If we match the same affiliation via multiple patterns,
                            # that only counts as one match
                            if normalized_affiliation_current not in matches_found:
                                matches_found.append(normalized_affiliation_current)

                # If no match field exists, treat this as a shortcut
                # It can match if there is exactly one affiliation with an exactly matching institution
                else:
                    match_current = True
                    match_current &= len(author_current['affiliations']) == 1
                    match_current &= normalized_affiliation_current['canonical'] == author_current['affiliations'][0]['institution']

                    # Track how many we match
                    if match_current:
                        matches_found.append(normalized_affiliation_current)

            # Apply any exclusion
            for match_current in matches_found:
                if "reject" in match_current:
                    for reject_pattern_current in match_current["reject"]:
                        if "name" in reject_pattern_current:
                            if author_current["name"] == reject_pattern_current["name"]:
                                matches_found.remove(match_current)

            if len(matches_found) == 1:
                del author_current['affiliations']
                author_current['affiliation'] = matches_found[0]['canonical']
            elif len(matches_found) == 0:
                print('No Affiliation Match:')
                pprint.pprint(author_current)

                unmatched_authors.append(author_current)
            else:
                print('Multiple Affiliation Match:')
                pprint.pprint(author_current)
                pprint.pprint(matches_found)

                assert False

    if unmatched_authors:
        unmatched_authors = sorted(
            unmatched_authors,
            key=lambda author_sort: author_sort["affiliations"][0]["institution"],
        )

        pyperclip.copy(
            '\n'.join(
                [
                    '\n'.join(
                        [
                            "  - canonical: '{}'".format(author_current["affiliations"][0]["institution"]),
                            "    match:",
                            "    - name: '{}'".format(author_current['name']),
                            "      affiliations:",
                            "\n".join(
                                [
                                    "\n".join(
                                        [
                                            "      - institution: '{}'".format(affiliation_current["institution"]),
                                            "        dsl: '{}'".format(affiliation_current["dsl"]),
                                        ]
                                    )
                                    for affiliation_current in author_current["affiliations"]
                                ]
                            )
                        ]
                    )
                    for author_current in unmatched_authors
                ]
            )
        )

    assert len(unmatched_authors) == 0

    return items


def normalize_text(text):
    while '  ' in text:
        text = text.replace('  ', ' ')

    text = text.replace('–', '-')

    text = text.replace('\u2019', '\'')
    text = text.replace('\u201C', '"')
    text = text.replace('\u201D', '"')

    text = text.strip()

    return text


def normalize_title(title):
    title = normalize_text(title)

    title = titlecase.titlecase(title)

    title = title.replace('in Situ', 'In Situ')
    title = title.replace('Human-Ai', 'Human-AI')

    return title


def normalize_title_sort(title):
    return (''.join(c for c in title if c in string.ascii_letters + string.digits)).casefold()


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
        key=operator.itemgetter('honorablemention'),
        reverse=True
    )
    items.sort(
        key=operator.itemgetter('bestpaper'),
        reverse=True
    )

    return items


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

    if config['file_input_type'] == 'sigchi program':
        items = parse_sigchi_program(config)

    output_yaml(config, items)

    print('{} papers'.format(len(items)))
    print('{} best paper award'.format(len([item for item in items if item['bestpaper']])))
    print('{} best paper honorable mention'.format(len([item for item in items if item['honorablemention']])))


if __name__ == '__main__':
    main()
