import csv
import json
import os

def flat_csv_to_json(csv_file, json_file, attribute_mappings=None):
    """
    Reads a CSV file and writes a JSON file.
    """
    with open(csv_file, 'r') as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)

        for row in rows:
            for key, value in attribute_mappings.items():
                if key in row:
                    # if value is None, then delete the key
                    if value is not None:
                        row[value] = row[key]
                    del row[key]

    with open(json_file, 'w') as json_file:
        json.dump(rows, json_file)


flat_csv_to_json('./data/csv/mem_contradictions.csv', './data/train/mem_contradictions.json', attribute_mappings = {'Story': 'text', 
                                                                                                                    'Memory': 'alt', 
                                                                                                                    'Contradictory continuation': None,
                                                                                                                    'Non-contradictory continuation': None})
