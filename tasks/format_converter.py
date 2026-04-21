import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def read_csv(path):
    with open(path, "r", encoding="iso-8859-1", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(data, path):
    if not data:
        return

    headers = list(data[0].keys())

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def read_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()
    data = []

    for person_elem in root.findall("person"):
        row = {}
        for field_elem in person_elem:
            row[field_elem.tag] = field_elem.text if field_elem.text is not None else ""
        data.append(row)

    return data


def write_xml(data, path):
    root = ET.Element("persons")

    for person in data:
        person_elem = ET.SubElement(root, "person")

        for key, value in person.items():
            safe_key = key.replace(" ", "_")
            field_elem = ET.SubElement(person_elem, safe_key)
            field_elem.text = str(value)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def convert(input_path, input_format, output_path, output_format):
    if input_format == "csv":
        data = read_csv(input_path)
    elif input_format == "json":
        data = read_json(input_path)
    elif input_format == "xml":
        data = read_xml(input_path)
    else:
        raise ValueError("Unbekanntes Eingabeformat")

    if output_format == "csv":
        write_csv(data, output_path)
    elif output_format == "json":
        write_json(data, output_path)
    elif output_format == "xml":
        write_xml(data, output_path)
    else:
        raise ValueError("Unbekanntes Ausgabeformat")


# Beispielaufrufe nur beim direkten Starten der Datei ausfuehren, nicht beim Import.
if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    convert(
        str(data_dir / "Personendaten_8Attribute.csv"),
        "csv",
        str(output_dir / "personen.json"),
        "json",
    )
    convert(
        str(output_dir / "personen.json"),
        "json",
        str(output_dir / "personen.xml"),
        "xml",
    )


