import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom


SUPPORTED_FORMATS = {"csv", "json", "xml"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"


# Ermittelt das Dateiformat aus der Dateiendung und validiert es.
def detect_format(file_name):
    # Die Dateiendung wird in Kleinbuchstaben umgewandelt, damit z. B. .CSV und .csv
    # gleich behandelt werden.
    file_format = Path(file_name).suffix.lower().lstrip(".")
    if file_format not in SUPPORTED_FORMATS:
        raise ValueError("Unterstuetzt werden nur CSV, JSON und XML.")
    return file_format


# Baut den Standardpfad fuer konvertierte Dateien im output/-Ordner.
def default_output_path(input_file_name, target_format):
    # Alle erzeugten Dateien landen bewusst zentral im output/-Ordner und nicht
    # neben der Quelldatei. So bleibt der data/-Ordner unveraendert.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return str(OUTPUT_DIR / f"{Path(input_file_name).stem}.{target_format.lower()}")


# Stellt sicher, dass das Zielverzeichnis beim Schreiben existiert.
def ensure_output_directory(output_file_name):
    # Falls spaeter ein anderer Ausgabeordner uebergeben wird, wird er hier automatisch
    # angelegt, damit das Schreiben nicht an einem fehlenden Verzeichnis scheitert.
    Path(output_file_name).parent.mkdir(parents=True, exist_ok=True)
    return output_file_name


# Bereitet XML-Tagnamen so auf, dass daraus gueltige Elementnamen werden.
def safe_tag(tag):
    # XML erlaubt nicht jedes beliebige Zeichen in Tag-Namen. Deshalb werden problematische
    # Zeichen ersetzt und Namen, die mit einer Ziffer beginnen, angepasst.
    tag = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(tag))
    if not tag or tag[0].isdigit():
        tag = f"key_{tag}"
    return tag


# Liest eine Datei fuer die Vorschau vollstaendig oder optional gekuerzt ein.
def preview_file(file_name, max_chars=None):
    # Fehlerhafte Zeichen werden ersetzt statt eine Vorschau komplett abbrechen zu lassen.
    with open(file_name, "r", encoding="utf-8", errors="replace") as file:
        content = file.read()
    # Fuer die Webansicht ist standardmaessig die komplette Datei hilfreich. Eine
    # Begrenzung bleibt aber optional moeglich.
    if max_chars is None or len(content) <= max_chars:
        return content
    return f"{content[:max_chars]}\n\n... Vorschau gekuerzt ..."


# Laedt JSON-Dateien mit einer klaren Fehlermeldung bei ungueltigem Inhalt.
def _load_json(input_file_name):
    try:
        # JSON wird direkt in Python-Datenstrukturen wie Dicts und Listen umgewandelt.
        with open(input_file_name, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Ungueltige JSON-Datei: {exc.msg} (Zeile {exc.lineno}, Spalte {exc.colno})."
        ) from exc


# Liest CSV-Daten robust mit mehreren moeglichen Encodings ein.
def _read_csv_rows(input_file_name):
    last_error = None
    # Manche CSV-Dateien liegen nicht in UTF-8 vor. Deshalb werden mehrere gaengige
    # Encodings nacheinander ausprobiert.
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(input_file_name, "r", encoding=encoding, newline="") as file:
                # DictReader erzeugt pro Zeile ein Dictionary mit Spaltenname -> Wert.
                rows = list(csv.DictReader(file))
            return [{key: value for key, value in row.items()} for row in rows]
        except UnicodeDecodeError as exc:
            last_error = exc
    raise ValueError(f"CSV-Datei konnte nicht gelesen werden: {last_error}") from last_error


# Wandelt verschachtelte Dict-Strukturen in flache Key-Value-Paare um.
def _flatten_dict(data, prefix=""):
    flat = {}
    for key, value in data.items():
        # Verschachtelte Inhalte wie {"adresse": {"stadt": "Berlin"}} werden zu
        # flachen Schluesseln wie "adresse.stadt". Das ist fuer CSV und Tabellenansichten
        # deutlich einfacher zu verarbeiten.
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(_flatten_dict(value, full_key))
        elif isinstance(value, list):
            # Listen werden hier als JSON-String gespeichert. So geht keine Information
            # verloren, auch wenn eine Tabelle keine echte Listenstruktur kennt.
            flat[full_key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            flat[full_key] = ""
        else:
            flat[full_key] = str(value)
    return flat


# Normalisiert JSON-Inhalte in tabellarische Zeilen fuer CSV und Spaltenanzeige.
def _extract_json_rows(data):
    # Viele JSON-Dateien haben einen aeusseren Wrapper wie {"employees": [...]}. Solange
    # nur eine einzige Schluessel-Ebene vorhanden ist, wird weiter nach innen gegangen.
    while isinstance(data, dict) and len(data) == 1:
        next_value = next(iter(data.values()))
        if isinstance(next_value, (dict, list)):
            data = next_value
            continue
        break

    if isinstance(data, list):
        # Eine Liste entspricht typischerweise mehreren Datensaetzen bzw. Zeilen.
        rows = []
        for item in data:
            if isinstance(item, dict):
                rows.append(_flatten_dict(item))
            else:
                # Auch einfache Listenwerte werden in eine tabellarische Form gebracht.
                rows.append({"value": "" if item is None else str(item)})
        return rows

    if isinstance(data, dict):
        # Ein flaches Dictionary wird als genau eine Tabellenzeile behandelt.
        if all(not isinstance(value, (dict, list)) for value in data.values()):
            return [{key: "" if value is None else str(value) for key, value in data.items()}]
        # Ein verschachteltes Dictionary wird erst abgeflacht und dann als eine Zeile geliefert.
        return [_flatten_dict(data)]

    # Auch einzelne primitive Werte werden als Mini-Tabelle mit einer Spalte "value" abgebildet.
    return [{"value": "" if data is None else str(data)}]


# Rekonstruiert XML rekursiv als Python-Datenstruktur.
def _element_to_data(element):
    children = list(element)
    if not children:
        # Ein Blatt-Element ohne weitere Kinder liefert direkt seinen Textinhalt.
        return (element.text or "").strip()

    grouped = {}
    for child in children:
        # Jedes Kind wird rekursiv gelesen. Mehrfach vorkommende Tags werden gesammelt.
        child_value = _element_to_data(child)
        grouped.setdefault(child.tag, []).append(child_value)

    result = {}
    for tag, values in grouped.items():
        # Ein einzelnes Unterelement bleibt ein Einzelwert, mehrere gleichnamige Elemente
        # werden als Liste gespeichert.
        result[tag] = values[0] if len(values) == 1 else values
    return result


# Laedt die komplette XML-Datei als verschachteltes Python-Objekt.
def _read_xml_data(input_file_name):
    # Bei XML ist das Wurzelelement oft fachlich wichtig. Deshalb bleibt es in der
    # Rueckgabe als oberster Schluessel erhalten.
    root = ET.parse(input_file_name).getroot()
    return {root.tag: _element_to_data(root)}


# Extrahiert XML-Datensaetze zeilenweise fuer tabellarische Konvertierungen.
def _extract_xml_rows(input_file_name):
    root = ET.parse(input_file_name).getroot()
    rows = []
    # Jedes direkte Kind des Root-Elements wird hier als eigener Datensatz verstanden.
    for record in root:
        row = {}
        for child in list(record):
            if list(child):
                # Verschachtelte XML-Strukturen werden zuerst als Dict gelesen und dann
                # fuer die Tabellenansicht abgeflacht.
                row.update(_flatten_dict({child.tag: _element_to_data(child)}))
            else:
                row[child.tag] = (child.text or "").strip()
        if row:
            rows.append(row)
    if not rows:
        raise ValueError("Aus der XML-Datei konnten keine tabellarischen Datensaetze gelesen werden.")
    return rows


# Vereinheitlicht CSV-, JSON- und XML-Inhalte in ein tabellarisches Zwischenformat.
def load_tabular_data(input_file_name):
    source_format = detect_format(input_file_name)
    # Alle Formate werden auf dieselbe Zwischenstruktur gebracht: eine Liste von Zeilen.
    # Das vereinfacht Spaltenauswahl und CSV-Ausgabe erheblich.
    if source_format == "csv":
        return _read_csv_rows(input_file_name)
    if source_format == "json":
        return _extract_json_rows(_load_json(input_file_name))
    if source_format == "xml":
        return _extract_xml_rows(input_file_name)
    raise ValueError("Format wird nicht unterstuetzt.")


# Liefert alle erkannten Spalten fuer die optionale Benutzerauswahl im UI.
def get_available_columns(input_file_name):
    rows = load_tabular_data(input_file_name)
    columns = []
    # Die Spalten werden in der Reihenfolge gesammelt, in der sie erstmals auftauchen.
    # Das wirkt fuer Benutzer oft natuerlicher als eine strenge Sortierung.
    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(key)
    return columns


# Filtert die tabellarischen Daten auf die vom Benutzer gewaehlten Spalten.
def _select_columns(rows, selected_columns=None):
    if not selected_columns:
        return rows

    available_columns = []
    # Vor dem Filtern wird geprueft, welche Spalten ueberhaupt existieren, damit bei
    # Tippfehlern eine verstaendliche Fehlermeldung moeglich ist.
    for row in rows:
        for key in row.keys():
            if key not in available_columns:
                available_columns.append(key)

    missing = [column for column in selected_columns if column not in available_columns]
    if missing:
        raise ValueError(f"Folgende Spalten wurden nicht gefunden: {', '.join(missing)}")

    # Jede Zeile wird auf genau die gewuenschten Spalten reduziert. Fehlende Werte werden
    # mit einem leeren String aufgefuellt, damit die Struktur konsistent bleibt.
    return [{column: row.get(column, "") for column in selected_columns} for row in rows]


# Leitet aus dem Quelldateinamen einen sauberen Basisnamen fuer XML/JSON ab.
def _sanitize_name_from_path(input_file_name, fallback):
    # Der Dateiname dient als Default fuer Root-Tags oder Root-Keys, wird aber zuvor
    # XML- und JSON-freundlich bereinigt.
    name = safe_tag(Path(input_file_name).stem)
    return name or fallback


# Formatiert XML fuer lesbare Ausgabe mit Einrueckungen.
def _prettify_xml(root):
    # Das XML wird zuerst technisch erzeugt und danach fuer Menschen lesbarer formatiert.
    xml_bytes = ET.tostring(root, encoding="utf-8")
    return minidom.parseString(xml_bytes).toprettyxml(indent="  ")


# Schreibt ein aufgebautes XML-Element sauber in eine Datei.
def _write_xml(root, output_file_name):
    ensure_output_directory(output_file_name)
    # Die XML-Datei wird immer als Textdatei mit UTF-8 gespeichert.
    with open(output_file_name, "w", encoding="utf-8") as file:
        file.write(_prettify_xml(root))
    return output_file_name


# Schreibt tabellarische Zeilen als CSV-Datei.
def _write_csv(rows, output_file_name):
    ensure_output_directory(output_file_name)
    fieldnames = []
    # Nicht jede Zeile muss exakt dieselben Schluessel haben. Deshalb wird zuerst die
    # Gesamtmenge aller vorkommenden Spalten gesammelt.
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(output_file_name, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        # Zuerst wird die Kopfzeile geschrieben, danach folgen die eigentlichen Datensaetze.
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return output_file_name


# Schreibt Python-Datenstrukturen als formatierte JSON-Datei.
def _write_json(data, output_file_name):
    ensure_output_directory(output_file_name)
    # Die JSON-Datei wird mit Einrueckungen gespeichert, damit sie in der Vorschau und
    # beim manuellen Oeffnen leicht lesbar bleibt.
    with open(output_file_name, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
    return output_file_name


# Baut rekursiv XML aus Dict-, List- und Einzelwerten auf.
def build_xml(parent, data, list_item_name="item"):
    if isinstance(data, dict):
        # Dictionaries werden zu Unterelementen mit benannten Tags.
        for key, value in data.items():
            child = ET.SubElement(parent, safe_tag(key))
            build_xml(child, value, list_item_name=list_item_name)
    elif isinstance(data, list):
        # Listen haben meist keinen eigenen Schluesselnamen pro Eintrag. Deshalb wird
        # fuer jedes Element ein generischer Tag wie <item> erzeugt.
        for item in data:
            child = ET.SubElement(parent, list_item_name)
            build_xml(child, item, list_item_name=list_item_name)
    elif data is None:
        parent.text = ""
    else:
        # Primitive Werte wie Strings oder Zahlen landen direkt als Text im XML-Element.
        parent.text = str(data)


# Konvertiert XML in JSON und speichert das Ergebnis im output/-Ordner.
def xml_to_json(input_file_name, output_file_name=None):
    # Falls kein Zielpfad vorgegeben wurde, wird automatisch ein Name im output/-Ordner erzeugt.
    output_file_name = output_file_name or default_output_path(input_file_name, "json")
    # XML wird zuerst als allgemeine Python-Struktur gelesen und danach als JSON geschrieben.
    data = _read_xml_data(input_file_name)
    _write_json(data, output_file_name)
    return data


# Konvertiert XML in CSV und beruecksichtigt optional eine Spaltenauswahl.
def xml_to_csv(input_file_name, output_file_name=None, selected_columns=None):
    output_file_name = output_file_name or default_output_path(input_file_name, "csv")
    # XML wird hier in tabellarische Zeilen umgewandelt, damit daraus eine CSV-Datei
    # mit Spalten und Zeilen entstehen kann.
    rows = _select_columns(_extract_xml_rows(input_file_name), selected_columns)
    _write_csv(rows, output_file_name)
    return rows


# Konvertiert JSON in XML und erzeugt bei Bedarf ein passendes Wurzelelement.
def json_to_xml(json_file, xml_file=None, default_root="root", list_item_name="item"):
    xml_file = xml_file or default_output_path(json_file, "xml")
    data = _load_json(json_file)

    if isinstance(data, dict) and len(data) == 1:
        # Hat das JSON bereits genau einen obersten Schluessel, wird dieser als
        # Root-Element uebernommen. Das wirkt meist fachlich natuerlicher.
        root_key, root_value = next(iter(data.items()))
        root = ET.Element(safe_tag(root_key))
        build_xml(root, root_value, list_item_name=list_item_name)
    else:
        # Sonst wird ein neutraler Root-Name verwendet, damit jedes JSON in gueltiges
        # XML eingebettet werden kann.
        root = ET.Element(safe_tag(default_root))
        build_xml(root, data, list_item_name=list_item_name)

    _write_xml(root, xml_file)
    return xml_file


# Konvertiert JSON in ein tabellarisches CSV-Format.
def json_to_csv(input_file_name, output_file_name=None, selected_columns=None):
    output_file_name = output_file_name or default_output_path(input_file_name, "csv")
    # JSON wird zuerst in Tabellenzeilen normalisiert und danach wie eine normale CSV
    # geschrieben.
    rows = _select_columns(_extract_json_rows(_load_json(input_file_name)), selected_columns)
    _write_csv(rows, output_file_name)
    return rows


# Konvertiert CSV in XML und erstellt fuer jede Zeile ein record-Element.
def csv_to_xml(input_file_name, output_file_name=None, selected_columns=None, root_name=None, row_name="record"):
    output_file_name = output_file_name or default_output_path(input_file_name, "xml")
    root_name = root_name or _sanitize_name_from_path(input_file_name, "records")
    rows = _select_columns(_read_csv_rows(input_file_name), selected_columns)

    root = ET.Element(safe_tag(root_name))
    for row in rows:
        # Jede CSV-Zeile wird als eigener Datensatz im XML angelegt.
        row_element = ET.SubElement(root, safe_tag(row_name))
        for key, value in row.items():
            # Jede Spalte der Zeile wird zu einem Unterelement innerhalb dieses Datensatzes.
            child = ET.SubElement(row_element, safe_tag(key))
            child.text = "" if value is None else str(value)

    _write_xml(root, output_file_name)
    return output_file_name


# Konvertiert CSV in JSON und kapselt die Zeilen unter einem Root-Key.
def csv_to_json(input_file_name, output_file_name=None, selected_columns=None, root_key=None):
    output_file_name = output_file_name or default_output_path(input_file_name, "json")
    root_key = root_key or _sanitize_name_from_path(input_file_name, "records")
    rows = _select_columns(_read_csv_rows(input_file_name), selected_columns)
    # Die Zeilen werden als Liste unter einem benannten Root-Key gespeichert, damit
    # das JSON auch bei mehreren Datensaetzen eine klare Struktur hat.
    return _write_json({safe_tag(root_key): rows}, output_file_name)


# Zentrale Einstiegsmethode, die je nach Quell- und Zielformat die passende Konvertierung startet.
def convert_file(input_file_name, target_format, output_file_name=None, selected_columns=None):
    # Zuerst werden Quell- und Zielformat vereinheitlicht und auf gueltige Werte geprueft.
    source_format = detect_format(input_file_name)
    target_format = target_format.lower()

    if target_format not in SUPPORTED_FORMATS:
        raise ValueError("Unterstuetzt werden nur CSV, JSON und XML.")
    if source_format == target_format:
        raise ValueError("Quelldatei und Zielformat sind identisch.")

    # Wenn kein Zielpfad uebergeben wurde, wird automatisch ein Dateiname im output/-Ordner erzeugt.
    output_file_name = output_file_name or default_output_path(input_file_name, target_format)

    # Anschliessend wird die passende Fachfunktion fuer genau diese Kombination aufgerufen.
    if source_format == "xml" and target_format == "json":
        xml_to_json(input_file_name, output_file_name=output_file_name)
    elif source_format == "xml" and target_format == "csv":
        xml_to_csv(input_file_name, output_file_name=output_file_name, selected_columns=selected_columns)
    elif source_format == "json" and target_format == "xml":
        json_to_xml(
            input_file_name,
            xml_file=output_file_name,
            default_root=_sanitize_name_from_path(input_file_name, "root"),
        )
    elif source_format == "json" and target_format == "csv":
        json_to_csv(input_file_name, output_file_name=output_file_name, selected_columns=selected_columns)
    elif source_format == "csv" and target_format == "xml":
        csv_to_xml(
            input_file_name,
            output_file_name=output_file_name,
            selected_columns=selected_columns,
            root_name=_sanitize_name_from_path(input_file_name, "records"),
        )
    elif source_format == "csv" and target_format == "json":
        csv_to_json(
            input_file_name,
            output_file_name=output_file_name,
            selected_columns=selected_columns,
            root_key=_sanitize_name_from_path(input_file_name, "records"),
        )
    else:
        raise ValueError("Diese Konvertierung wird nicht unterstuetzt.")

    # Zurueckgegeben wird der Pfad der erzeugten Ausgabedatei, damit UI oder Web-App
    # direkt Vorschau und Download anbieten koennen.
    return output_file_name
