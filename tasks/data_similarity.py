#!/usr/bin/env python3

import sys
import json
import re
from pathlib import Path
import pandas as pd
import xml.etree.ElementTree as ET


# Entfernt JavaScript-aehnliche Kommentare aus JSON-Texten vor dem Parsen.
def strip_json_comments(text):
    # Manche Beispieldateien enthalten Kommentare wie in JavaScript. Diese sind in
    # echtem JSON nicht erlaubt und werden daher vor dem Parsen entfernt.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    return text


# Laedt CSV-Dateien robust mit mehreren Encodings und automatischer Trennzeichenerkennung.
def load_csv(path):
    # Unterschiedliche CSV-Dateien koennen sowohl unterschiedliche Zeichencodierungen
    # als auch unterschiedliche Trennzeichen benutzen.
    for enc in ("utf-8", "cp1252", "latin1"):
        try:
            # sep=None mit engine="python" laesst pandas das Trennzeichen automatisch erraten.
            return pd.read_csv(path, dtype=str, sep=None, engine="python", encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"CSV konnte nicht gelesen werden: {path}")


# Laedt JSON-Dateien und formt verschiedene JSON-Strukturen in ein DataFrame um.
def load_json(path):
    # Genau wie bei CSV werden mehrere Encodings ausprobiert, damit typische
    # Windows- und UTF-8-Dateien gelesen werden koennen.
    for enc in ("utf-8", "cp1252", "latin1"):
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"JSON konnte nicht gelesen werden: {path}")

    # Vor dem Parsen werden moegliche Kommentare entfernt.
    text = strip_json_comments(text)
    data = json.loads(text)

    if isinstance(data, dict):
        # Haeufig ist die eigentliche Datensatzliste nur unter einem Schluessel verpackt.
        for value in data.values():
            if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                return pd.DataFrame(value)
        # Wenn keine Datensatzliste gefunden wird, wird das gesamte Objekt als eine Zeile behandelt.
        return pd.DataFrame([data])

    if isinstance(data, list):
        # Eine Liste wird direkt als Tabelle interpretiert.
        return pd.DataFrame(data)

    # Einzelwerte werden in eine einspaltige Tabellenstruktur ueberfuehrt.
    return pd.DataFrame([{"value": data}])


# Laedt einfache XML-Datensatzlisten in ein DataFrame.
def load_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()

    rows = []
    # Jedes direkte Kindelement des Root-Elements wird als ein Datensatz gelesen.
    for record in root:
        row = {}
        for child in record:
            row[child.tag] = child.text
        rows.append(row)

    return pd.DataFrame(rows)


# Waehlt passend zur Dateiendung die richtige Ladefunktion aus.
def load_to_df(path):
    suffix = Path(path).suffix.lower()

    # Egal ob CSV, JSON oder XML: am Ende soll immer ein DataFrame entstehen, damit
    # die Aehnlichkeitsberechnung formatunabhaengig arbeiten kann.
    if suffix == ".csv":
        return load_csv(path)
    if suffix == ".json":
        return load_json(path)
    if suffix == ".xml":
        return load_xml(path)

    raise ValueError(f"Nicht unterstütztes Format: {suffix}")


# Berechnet die Aehnlichkeit numerischer Werte auf Basis ihres Abstandes im Wertebereich.
def numeric_similarity(x, y, col_min, col_max):
    # Fehlende Werte werden gesondert behandelt, damit kein mathematischer Fehler entsteht.
    if pd.isna(x) and pd.isna(y):
        return 1.0
    if pd.isna(x) or pd.isna(y):
        return 0.0

    # Der Abstand zweier Zahlen wird relativ zum gesamten Wertebereich der Spalte bewertet.
    rng = col_max - col_min
    if rng == 0:
        return 1.0 if x == y else 0.0

    dist = abs(x - y)
    return max(0.0, 1.0 - min(dist / rng, 1.0))


# Berechnet fuer Textwerte eine einfache Jaccard-Aehnlichkeit auf Zeichenbasis.
def jaccard_similarity(a, b):
    # Auch hier werden fehlende und leere Werte zunaechst sauber abgefangen.
    if pd.isna(a) and pd.isna(b):
        return 1.0
    if pd.isna(a) or pd.isna(b):
        return 0.0

    # Gross-/Kleinschreibung und ueberfluessige Leerzeichen sollen keinen unfairen
    # Einfluss auf die Aehnlichkeit haben.
    a = str(a).strip().lower()
    b = str(b).strip().lower()

    if a == "" and b == "":
        return 1.0
    if a == "" or b == "":
        return 0.0

    # Die Zeichenmengen beider Texte werden verglichen. Je groesser die Ueberschneidung,
    # desto aehnlicher sind die beiden Werte.
    set_a = set(a)
    set_b = set(b)

    union = set_a | set_b
    intersection = set_a & set_b

    if len(union) == 0:
        return 1.0

    return len(intersection) / len(union)


# Vergleicht zwei DataFrames spaltenweise und berechnet daraus eine prozentuale Gesamtaehnlichkeit.
def similarity_percentage(df1, df2, key="id"):
    df1 = df1.copy()
    df2 = df2.copy()

    # Die Schluesselspalte dient dazu, fachlich gleiche Datensaetze aus beiden Dateien
    # miteinander zu paaren.
    if key not in df1.columns or key not in df2.columns:
        raise ValueError(f"Schlüsselspalte '{key}' fehlt in mindestens einer Datei.")

    df1[key] = df1[key].astype(str)
    df2[key] = df2[key].astype(str)

    # Beide Tabellen werden auf dieselbe Spaltenmenge gebracht, damit spaeter wirklich
    # alle relevanten Werte verglichen werden.
    all_cols = sorted(set(df1.columns).union(df2.columns))
    df1 = df1.reindex(columns=all_cols)
    df2 = df2.reindex(columns=all_cols)

    # Durch den Outer Join bleiben auch Datensaetze erhalten, die nur in einer Datei
    # vorkommen. Das macht die Aehnlichkeit realistischer.
    merged = df1.merge(df2, on=key, how="outer", suffixes=("_a", "_b"))

    compare_cols = [c for c in all_cols if c != key]
    similarities = []

    for col in compare_cols:
        # Jede Fachspalte liegt nach dem Merge doppelt vor: einmal aus Datei A und einmal aus Datei B.
        a_col = f"{col}_a"
        b_col = f"{col}_b"

        # Es wird ausprobiert, ob sich die Werte sinnvoll als Zahlen interpretieren lassen.
        a_num = pd.to_numeric(merged[a_col], errors="coerce")
        b_num = pd.to_numeric(merged[b_col], errors="coerce")

        # numeric_share misst, wie oft in dieser Spalte wenigstens eine Seite numerisch ist.
        # Dadurch wird heuristisch entschieden, ob eher ein Zahlen- oder Textvergleich passt.
        numeric_share = ((~a_num.isna()) | (~b_num.isna())).mean()

        if numeric_share > 0.8:
            # Fuer ueberwiegend numerische Spalten wird ein abstandsbasierter Vergleich verwendet.
            col_min = pd.concat([a_num, b_num]).min()
            col_max = pd.concat([a_num, b_num]).max()

            for x, y in zip(a_num, b_num):
                similarities.append(numeric_similarity(x, y, col_min, col_max))
        else:
            # Fuer textuelle Spalten wird eine einfache Zeichenmengen-Aehnlichkeit berechnet.
            for x, y in zip(merged[a_col], merged[b_col]):
                similarities.append(jaccard_similarity(x, y))

    if not similarities:
        # Wenn es ausser der ID keine inhaltlichen Spalten gibt, werden die Daten als
        # vollstaendig aehnlich betrachtet.
        return 100.0

    # Der Endwert ist der Durchschnitt aller Einzelvergleiche in Prozent.
    return sum(similarities) / len(similarities) * 100.0


# Kommandozeilen-Einstieg fuer die Aehnlichkeitsbewertung zweier Dateien.
def main():
    if len(sys.argv) != 3:
        print("Verwendung: python similar_data.py <datei1> <datei2>")
        sys.exit(2)

    file1 = sys.argv[1]
    file2 = sys.argv[2]

    try:
        # Die CLI kuemmert sich nur um Dateieinlesung und Ausgabe. Die eigentliche
        # Bewertung steckt in similarity_percentage.
        df1 = load_to_df(file1)
        df2 = load_to_df(file2)

        sim = similarity_percentage(df1, df2, key="id")
        print(f"Ähnlichkeit: {sim:.2f}%")

        if sim == 100.0:
            print("Die Daten sind vollständig ähnlich.")
        elif sim >= 80:
            print("Die Daten sind stark ähnlich.")
        elif sim >= 50:
            print("Die Daten sind teilweise ähnlich.")
        else:
            print("Die Daten sind eher unähnlich.")

    except Exception as e:
        print(f"Fehler: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
