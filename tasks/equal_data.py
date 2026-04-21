#!/usr/bin/env python3
import re
import sys
import json
from pathlib import Path
from collections import Counter

import pandas as pd
import xml.etree.ElementTree as ET


# Vereinheitlicht Einzelwerte, damit verschiedene Formate spaeter vergleichbar sind.
def normalize_value(value):
    # Fehlende Werte sollen in allen Formaten gleich wirken. Deshalb werden NaN-Werte
    # zu einem leeren String umgewandelt.
    if pd.isna(value):
        return ""
    # Booleans werden bewusst als "true"/"false" vereinheitlicht, damit sie beim
    # spaeteren String-Vergleich stabil bleiben.
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# Flaecht verschachtelte JSON- oder Dict-Strukturen in einfache Schluessel-Wert-Paare ab.
def flatten_dict(data, parent_key="", sep="."):
    items = {}

    if isinstance(data, dict):
        # Dictionaries werden rekursiv durchlaufen. Verschachtelte Schluessel wie
        # {"a": {"b": 1}} werden dabei zu "a.b".
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
            items.update(flatten_dict(value, new_key, sep=sep))

    elif isinstance(data, list):
        # Listen werden ueber ihren Index adressiert, damit die Position eines Eintrags
        # nicht verloren geht.
        for i, value in enumerate(data):
            new_key = f"{parent_key}[{i}]"
            items.update(flatten_dict(value, new_key, sep=sep))

    else:
        # Sobald kein weiteres Dict oder keine Liste mehr vorliegt, wird der eigentliche
        # Endwert gespeichert.
        items[parent_key if parent_key else "value"] = normalize_value(data)

    return items


# Flaecht XML rekursiv ab und nummeriert wiederholte Elemente eindeutig durch.
def flatten_xml_element(elem, parent_key=""):
    children = list(elem)

    if not children:
        # Blattknoten ohne weitere Unterelemente liefern direkt ihren Textwert.
        key = parent_key if parent_key else elem.tag
        return {key: elem.text if elem.text is not None else ""}

    result = {}
    # Bei XML koennen mehrere gleichnamige Kindelemente nebeneinander vorkommen.
    # counts und seen helfen dabei, diese spaeter eindeutig zu benennen.
    counts = Counter(child.tag for child in children)
    seen = Counter()

    for child in children:
        seen[child.tag] += 1

        if counts[child.tag] > 1:
            # Wiederholte Tags erhalten einen Index wie tag[0], tag[1], ...
            child_key = f"{parent_key}.{child.tag}[{seen[child.tag] - 1}]" if parent_key else f"{child.tag}[{seen[child.tag] - 1}]"
        else:
            child_key = f"{parent_key}.{child.tag}" if parent_key else child.tag

        # Danach wird der Unterbaum des Kindelements weiter rekursiv abgeflacht.
        result.update(flatten_xml_element(child, child_key))

    return result


# Laedt CSV-Dateien robust mit mehreren moeglichen Encodings.
def csv_to_df(file_path):
    # Nicht jede CSV-Datei ist gleich kodiert. Deshalb werden mehrere gaengige
    # Encodings nacheinander ausprobiert.
    for encoding in ("utf-8", "cp1252", "latin1"):
        try:
            df = pd.read_csv(file_path, dtype=str, encoding=encoding)
            # Fehlende Werte werden sofort vereinheitlicht, damit spaeter kein Vergleich
            # an NaN-Werten scheitert.
            return df.fillna("")
        except UnicodeDecodeError:
            continue

    raise ValueError(f"CSV-Datei konnte mit keinem unterstützten Encoding gelesen werden: {file_path}")


# Laedt JSON, entfernt optionale Kommentare und wandelt den Inhalt in ein DataFrame um.
def json_to_df(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="cp1252") as f:
            text = f.read()

    # Einige Beispieldateien enthalten Kommentare, obwohl das offiziell kein gueltiges
    # JSON ist. Diese werden vor dem Parsen entfernt.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)

    data = json.loads(text)

    if isinstance(data, list):
        # Eine JSON-Liste wird direkt als Liste von Datensaetzen interpretiert.
        records = data

    elif isinstance(data, dict):
        # suche nach einer Liste von Dicts als eigentliche Datensätze
        list_of_dicts = None
        for value in data.values():
            if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                list_of_dicts = value
                break

        if list_of_dicts is not None:
            # Falls im aeusseren Objekt eigentlich nur eine Datensatzliste verpackt ist,
            # wird genau diese Liste als Tabellenbasis verwendet.
            records = list_of_dicts
        else:
            # Sonst wird das gesamte Objekt abgeflacht und als eine Zeile dargestellt.
            records = [flatten_dict(data)]

    else:
        # Einzelwerte werden in eine einspaltige Tabellenform gebracht.
        records = [{"value": normalize_value(data)}]

    df = pd.DataFrame(records)
    return df.fillna("")


# Laedt XML und behandelt sowohl einzelne Datensaetze als auch Listen von Datensaetzen.
def xml_to_df(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    children = list(root)

    if not children:
        # Ein XML-Dokument ohne Unterelemente wird als ein einzelner Wert behandelt.
        df = pd.DataFrame([{"value": root.text if root.text is not None else ""}])
        return df.fillna("")

    # Fall 1: Root ist selbst ein einzelner flacher Datensatz
    if all(len(list(child)) == 0 for child in children) and len({child.tag for child in children}) == len(children):
        # Wenn das Root-Element nur eindeutige Blattknoten enthaelt, ergibt das genau
        # eine Tabellenzeile.
        row = {child.tag: (child.text if child.text is not None else "") for child in children}
        df = pd.DataFrame([row])
        return df.fillna("")

    # Fall 2: Jedes direkte Kindelement von root ist ein Datensatz
    # Hier wird jeder Datensatz abgeflacht, damit auch verschachtelte XML-Strukturen
    # vergleichbar werden.
    rows = [flatten_xml_element(child) for child in children]
    df = pd.DataFrame(rows)
    return df.fillna("")


# Waehlt passend zur Dateiendung die richtige Ladefunktion aus.
def load_file_to_df(file_path):
    suffix = Path(file_path).suffix.lower()

    # Alle Formate werden in ein gemeinsames DataFrame-Zwischenformat ueberfuehrt.
    # Erst dadurch wird ein formatunabhaengiger Vergleich moeglich.
    if suffix == ".csv":
        return csv_to_df(file_path)
    if suffix == ".json":
        return json_to_df(file_path)
    if suffix == ".xml":
        return xml_to_df(file_path)

    raise ValueError(f"Nicht unterstütztes Dateiformat: {suffix}")


# Normalisiert Spalten, Werte und Reihenfolge, damit Dateiinhalte fair verglichen werden koennen.
def normalize_dataframe(df):
    df = df.copy()

    # alle Spaltennamen in Strings umwandeln
    # Unterschiedliche Formate koennen numerische oder gemischte Spaltennamen liefern.
    df.columns = [str(col) for col in df.columns]

    # fehlende Werte angleichen
    df = df.fillna("")

    # alle Werte als String
    # Der spaetere Vergleich soll nicht an verschiedenen Python-Typen scheitern.
    for col in df.columns:
        df[col] = df[col].map(normalize_value)

    # Spalten alphabetisch sortieren
    # Wenn dieselben Daten nur in anderer Spaltenreihenfolge vorliegen, sollen sie
    # trotzdem als gleich erkannt werden.
    df = df.reindex(sorted(df.columns), axis=1)

    # Zeilen sortieren, damit gleiche Daten in anderer Reihenfolge trotzdem gleich sind
    if len(df.columns) > 0 and len(df) > 0:
        # mergesort ist stabil und damit fuer reproduzierbare Ergebnisse gut geeignet.
        df = df.sort_values(by=list(df.columns), kind="mergesort").reset_index(drop=True)
    else:
        df = df.reset_index(drop=True)

    return df


# Vergleicht zwei Dateien unabhaengig vom Format auf inhaltliche Gleichheit.
def compare_files(file1, file2):
    # Beide Dateien werden zuerst eingelesen und in dasselbe Tabellenformat ueberfuehrt.
    df1 = load_file_to_df(file1)
    df2 = load_file_to_df(file2)

    # Danach werden Reihenfolge, fehlende Werte und Datentypen vereinheitlicht.
    df1 = normalize_dataframe(df1)
    df2 = normalize_dataframe(df2)

    # pandas.equals prueft dann, ob wirklich dieselben Inhalte vorliegen.
    return df1.equals(df2)


# Kommandozeilen-Einstieg fuer den direkten Vergleich zweier Dateien.
def main():
    if len(sys.argv) != 3:
        print("Verwendung: python compare_files.py <datei1> <datei2>")
        sys.exit(2)

    file1 = sys.argv[1]
    file2 = sys.argv[2]

    try:
        # compare_files kapselt die eigentliche Fachlogik. main kuemmert sich nur um
        # Eingaben, Ausgaben und Rueckgabecodes fuer die Kommandozeile.
        are_equal = compare_files(file1, file2)

        if are_equal:
            print("Daten sind gleich")
            sys.exit(0)
        else:
            print("Daten sind nicht gleich")
            sys.exit(1)

    except Exception as e:
        print(f"Fehler: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
