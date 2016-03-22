import argparse
import json
import operator
import yaml


def parse_confer(file_input):
    # Parse the json.
    #
    # Currently requires the file start with an opening bracket, manually stripping any 'entities ='
    with open(file_input, 'r') as f:
        parsed_json = json.load(f)

    # Go through items to see which we want
    json_items = parsed_json.items()
    filtered_json_items = []
    for key_current, item_current in json_items:
        # We only want papers
        if item_current['type'] != 'paper':
            continue

        # Check our desired affiliation
        AFFILIATIONS = [
            'Washington'
        ]

        KEYS_EXCLUDE = [
            'pn1007'
        ]

        if key_current in KEYS_EXCLUDE:
            continue

        matches_affiliation = False
        for author_current in item_current['authors']:
            for affiliation_test in AFFILIATIONS:
                if affiliation_test in author_current['affiliation']:
                    matches_affiliation = True
        if not matches_affiliation:
            continue

        filtered_json_items.append(item_current)
    json_items = filtered_json_items

    # Go through items to clean them up
    for item_current in json_items:
        del item_current['abstract']
        del item_current['cAndB']
        del item_current['keywords']
        del item_current['subtype']
        del item_current['type']

    # Go through authors to clean them up
    for item_current in json_items:
        for author_current in item_current['authors']:
            del author_current['familyName']
            del author_current['givenName']
            del author_current['middleInitial']

            AFFILIATIONS_CLEANED = {
                'UW Biomedical and Health Informatics': {
                    'affiliation': [
                        'Biomedical and Health Informatics, University of Washington',
                        'Biomedical Informatics and Medical Education, University of Washington'
                    ],
                    'name': [
                        'Andrew D Miller'
                    ]
                },
                'UW Communication': {
                    'affiliation': [
                        'Department of Communication, University of Washington'
                    ],
                    'name': [
                        'Charles Kiene'
                    ]
                },
                'UW Computer Science & Engineering': {
                    'affiliation': [
                        'Computer Science & Engineering , DUB Group',
                        'Computer Science & Engineering, University of Washington',
                        'Computer Science and Engineering, University of Washington',
                        'UW Computer Science & Engineering',
                        'Center for Game Science, Department of Computer Science & Engineering, University of Washington'
                    ],
                    'name': [
                        'Christy Ballweber',
                        'Gaetano Borriello',
                        'James Fogarty',
                        'Mayank Goel',
                        'Tadayoshi Kohno',
                        'Zoran Popovic',
                        'Eric Whitmire',
                        'Xiaoyi Zhang'
                    ]
                },
                'UW Computer Science & Engineering / UW Electrical Engineering': {
                    'affiliation': [
                        'UW Computer Science & Engineering / UW Electrical Engineering'
                    ],
                    'name': [
                        'Shwetak N Patel'
                    ]
                },
                'UW Computer Science & Engineering / UW Human Centered Design & Engineering': {
                    'affiliation': [
                    ],
                    'name': [
                        'Laura R Pina'
                    ]
                },
                'UW Division of Design': {
                    'affiliation': [
                    ],
                    'name': [
                        'Shaghayegh Ghassemian'
                    ]
                },
                'UW Electrical Engineering': {
                    'affiliation': [
                        'Electrical Engineering, University of Washington'
                    ],
                    'name': [
                        'Ke-Yu Chen',
                        'Josh Fromm',
                        'Elliot Saba'
                    ]
                },
                'UW Environmental Science': {
                    'affiliation': [
                    ],
                    'name': [
                        'Thomas Tran'
                    ]
                },
                'UW Human Centered Design & Engineering': {
                    'affiliation': [
                        'Department of Human Centered Design and Engineering, University of Washington',
                        'Human Centered Design & Engineering, University of Washington',
                        'Human Centered Design & Engineering, University of Washington, UW',
                        'Human Centered Design and Engineering, University of Washington',
                        'TAT Lab, University of Washington',
                        'UW Human Centered Design & Engineering',
                        'Human Centered Design & Engineering, University of Washington, Seattle, Washington, United States, University of Washington',
                        'University of Washington , Human Centered Design and Engineering'
                    ],
                    'name': [
                        'Hyewon Suh'
                    ]
                },
                'UW Information School': {
                    'affiliation': [
                        'Information School, University of Washington',
                        'Information School , University of Washington',
                        'School of Information, University of Washington',
                        'UW Information School',
                        'The Information School, University of Washington'
                    ],
                    'name': [
                        'Martez E Mott',
                        'Jacob Wobbrock',
                        'Jacob O Wobbrock',
                        'Wanda Pratt'
                    ]
                },
                'UW Mechanical Engineering': {
                    'affiliation': [
                        'Mechanical Engineering, University of Washington'
                    ],
                    'name': [
                    ]
                },
                'UW MHCI+D': {
                    'affiliation': [
                    ],
                    'name': [
                        'Nina Shahriaree'
                    ]
                },
                'UW School of Medicine': {
                    'affiliation': [
                        'Department of Pediatrics - School of Medicine, University of Washington'
                    ],
                    'name': [
                        'Ari H Pollack'
                    ]
                },
                'Arizona State University': {
                    'affiliation': [
                        'Arizona State University'
                    ],
                    'name': [
                    ]
                },
                'Carnegie Mellon University': {
                    'affiliation': [
                        'Human Computer Interaction, Carnegie Mellon University',
                        'Human-Computer Interaction Institute, Carnegie Mellon',
                        'Human-Computer Interaction Institute, Carnegie Mellon University',
                        'Human Computer Interaction Institute, Carnegie Mellon University',
                        'Human-Computer Interaction Institute, School of Computer Science, Carnegie Mellon University'
                    ],
                    'name': [
                    ]
                },
                'Cornell University': {
                    'affiliation': [
                        'Cornell University',
                        'Information Science, Cornell University'
                    ],
                    'name': [
                    ]
                },
                'Disney Research': {
                    'affiliation': [
                        'Disney Research',
                        'Disney Research Pittsburgh, Disney Research'
                    ],
                    'name': [
                    ]
                },
                'FX Palo Alto Laboratory': {
                    'affiliation': [
                        'FXPAL',
                        'FX Palo Alto Laboratory, Inc.'
                    ],
                    'name': [
                    ]
                },
                'Global Solidarity Corporation': {
                    'affiliation': [
                        'Global Solidarity Corporation'
                    ],
                    'name': [
                    ]
                },
                'Inglemoor High School': {
                    'affiliation': [
                        'Inglemoor High School'
                    ],
                    'name': [
                    ]
                },
                'Massachusetts Institute of Technology': {
                    'affiliation': [
                        'Massachusetts Institute of Technology'
                    ],
                    'name': [
                    ]
                },
                'North Carolina State University': {
                    'affiliation': [
                        'North Carolina State University'
                    ],
                    'name': [
                    ]
                },
                'Massachusetts Institute of Technology': {
                    'affiliation': [
                        'Massachusetts Institute of Technology',
                        'MIT Media Lab, Massachusetts Institute of Technology'
                    ],
                    'name': [
                    ]
                },
                'Microsoft Research': {
                    'affiliation': [
                        'Microsoft Research'
                    ],
                    'name': [
                    ]
                },
                'National Tsing Hua Unversity': {
                    'affiliation': [
                        'Electrical Engineering, National Tsing Hua Unversity'
                    ],
                    'name': [
                    ]
                },
                'Northeastern University': {
                    'affiliation': [
                        'CCIS, Northeastern University'
                    ],
                    'name': [
                    ]
                },
                'Oculus Research': {
                    'affiliation': [
                        'Oculus Research'
                    ],
                    'name': [
                    ]
                },
                'Oregon State University': {
                    'affiliation': [
                        'Oregon State University',
                        'School of EECS, Oregon State University'
                    ],
                    'name': [
                    ]
                },
                'Palo Alto Research Center': {
                    'affiliation': [
                        'Palo Alto Research Center',
                        'Palo Alto Research Center (PARC)'
                    ],
                    'name': [
                    ]
                },
                'Pennsylvania State University': {
                    'affiliation': [
                        'College of Information Sciences and Technology, The Pennsylvania State University',
                        'College of Information Sciences and Technology, Pennsylvania State University',
                        'Information Sciences and Technology/HCI, The Pennsylvania State University',
                        'College of Information Sciences and Technology, Penn State'
                    ],
                    'name': [
                    ]
                },
                'Seattle Pacific University': {
                    'affiliation': [
                        'Seattle Pacific University'
                    ],
                    'name': [
                    ]
                },
                'Stanford University': {
                    'affiliation': [
                        'Computer Science, Stanford University'
                    ],
                    'name': [
                    ]
                },
                'Southern Methodist University': {
                    'affiliation': [
                        'Computer Science and Engineering, Southern Methodist University'
                    ],
                    'name': [
                    ]
                },
                'Technion': {
                    'affiliation': [
                        'Technion - Israel Institute of Technology'
                    ],
                    'name': [
                    ]
                },
                'Tufts University': {
                    'affiliation': [
                        'Tufts University'
                    ],
                    'name': [
                    ]
                },
                'University of Colorado': {
                    'affiliation': [
                        'University of Colorado Boulder',
                        'Department of Computer Science, University of Colorado'
                    ],
                    'name': [
                    ]
                },
                'University of Dundee': {
                    'affiliation': [
                        'School of Computing, University of Dundee'
                    ],
                    'name': [
                    ]
                },
                'University of Maryland': {
                    'affiliation': [
                        'University of Maryland',
                        'College of Education, University of Maryland',
                        'College of Information Studies, University of Maryland',
                        'Human-Computer Interaction Lab, University of Maryland',
                        'Department of Teaching and Learning, Policy and Leadership, University of Maryland'
                    ],
                    'name': [
                        'Elizabeth Bonsignore'
                    ]
                },
                'University of Michigan': {
                    'affiliation': [
                        'School of Information , University of Michigan',
                        'School of Information, University of Michigan'
                    ],
                    'name': [
                    ]
                },
                'University Stefan cel Mare of Suceava': {
                    'affiliation': [
                        'University Stefan cel Mare of Suceava'
                    ],
                    'name': [
                    ]
                }
            }

            matched = False

            for affiliation_test_key, affiliation_test_value in AFFILIATIONS_CLEANED.items():
                if author_current['affiliation'] in affiliation_test_value['affiliation']:
                    matched_affiliation = affiliation_test_key
                    matched = True

            for affiliation_test_key, affiliation_test_value in AFFILIATIONS_CLEANED.items():
                if author_current['name'] in affiliation_test_value['name']:
                    matched_affiliation = affiliation_test_key
                    matched = True

            if matched:
                author_current['affiliation'] = matched_affiliation
                del author_current['city']
                del author_current['country']
                del author_current['dept']
                del author_current['institution']
                del author_current['location']
            else:
                print(author_current['affiliation'])

    # Sort them
    json_items.sort(
        key=operator.itemgetter('title')
    )
    json_items.sort(
        key=operator.itemgetter('hm'),
        reverse=True
    )
    json_items.sort(
        key=operator.itemgetter('award'),
        reverse=True
    )

    return json_items


def output_yaml(items, file_output):
    data = { 'papers': items }
    with open(file_output, 'w') as f:
        yaml.dump(
            data,
            stream=f,
            default_flow_style=False
        )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Confer JSON parser for DUB')
    parser.add_argument('-i', required=True, dest='file_input')
    parser.add_argument('-o', required=True, dest='file_output')
    args = parser.parse_args()

    items = parse_confer(args.file_input)
    output_yaml(items, args.file_output)

    print('{} papers'.format(len(items)))
    print('{} best paper award'.format(len([item for item in items if item['award'] == True])))
    print('{} best paper honorable mention'.format(len([item for item in items if item['hm'] == True])))
