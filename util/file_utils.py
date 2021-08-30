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
                    row[value] = row[key]
                    del row[key]

    with open(json_file, 'w') as json_file:
        json.dump(rows, json_file)


flat_csv_to_json('./data/csv/test.csv', './data/train/test.json', attribute_mappings = {'Story': 'text'})
