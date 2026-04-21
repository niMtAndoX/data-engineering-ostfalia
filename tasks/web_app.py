from pathlib import Path
import tempfile

from flask import Flask, render_template_string, request, send_file
from werkzeug.utils import secure_filename

from file_format_converter import (
    OUTPUT_DIR,
    convert_file,
    get_available_columns,
    preview_file,
)


# Initialisiert die minimale Flask-Anwendung und einen temporaeren Upload-Ordner.
app = Flask(__name__)
# Hochgeladene Dateien werden nicht im Projekt abgelegt, sondern nur temporaer gespeichert.
UPLOAD_DIR = Path(tempfile.gettempdir()) / "file_converter_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Das HTML-Template enthaelt die komplette, bewusst kleine Weboberflaeche inklusive Styling.
PAGE = """
<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8">
    <title>Dateiformat Konverter</title>
    <style>
      :root {
        --bg: #0b1220;
        --panel: #121826;
        --panel-soft: #1b2433;
        --border: #314158;
        --text: #e5e7eb;
        --muted: #9ca3af;
        --accent: #1e3a5f;
        --accent-strong: #274c77;
        --error: #fca5a5;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: linear-gradient(180deg, #060b14 0%, #0b1220 100%);
        color: var(--text);
        font-family: Arial, sans-serif;
      }
      .page {
        max-width: 920px;
        margin: 40px auto;
        padding: 0 16px 32px;
      }
      h1, h2 { margin-top: 0; }
      form, .box {
        background: var(--panel);
        border: 1px solid var(--border);
        padding: 18px;
        margin-bottom: 16px;
        border-radius: 12px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
      }
      label {
        display: block;
        margin-top: 10px;
        color: var(--muted);
      }
      input, select, button, textarea {
        width: 100%;
        margin-top: 6px;
        margin-bottom: 12px;
        padding: 10px 12px;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: var(--panel-soft);
        color: var(--text);
      }
      input::file-selector-button {
        background: var(--accent);
        color: var(--text);
        border: 0;
        border-radius: 6px;
        padding: 8px 12px;
        margin-right: 12px;
      }
      button {
        background: var(--accent);
        border: 1px solid var(--accent-strong);
        font-weight: 700;
        cursor: pointer;
      }
      button:hover {
        background: var(--accent-strong);
      }
      a {
        color: #bfdbfe;
      }
      .preview {
        height: 420px;
        resize: vertical;
        overflow: auto;
        white-space: pre;
        font-family: "Courier New", monospace;
        line-height: 1.45;
      }
      .error {
        color: var(--error);
      }
      .hint {
        color: var(--muted);
        font-size: 14px;
      }
      code {
        color: #dbeafe;
      }
    </style>
  </head>
  <body>
    <div class="page">
      <h1>Dateiformat Konverter</h1>
      <p class="hint">
        Datei per Upload oder Dateipfad angeben, Zielformat waehlen und optional Spalten
        als Komma-Liste einschränken. Die Ausgabedatei wird im Verzeichnis <code>output/</code> gespeichert.
      </p>

      <form method="post" enctype="multipart/form-data">
        <label>Dateipfad</label>
        <input type="text" name="file_path" value="{{ file_path or '' }}" placeholder="/pfad/zur/datei.csv">

        <label>Oder Datei hochladen</label>
        <input type="file" name="upload">

        <label>Zielformat</label>
        <select name="target_format">
          {% for option in ["csv", "json", "xml"] %}
            <option value="{{ option }}" {% if option == target_format %}selected{% endif %}>{{ option|upper }}</option>
          {% endfor %}
        </select>

        <label>Optionale Spalten</label>
        <input type="text" name="columns" value="{{ columns or '' }}" placeholder="z.B. Name, Alter, Stadt">

        {% if available_columns %}
          <div class="hint">Erkannte Spalten: {{ available_columns|join(", ") }}</div>
        {% endif %}

        <button type="submit">Konvertieren</button>
      </form>

      {% if error %}
        <div class="box error">{{ error }}</div>
      {% endif %}

      {% if result_path %}
        <div class="box">
          <p><strong>Gespeichert unter:</strong> {{ result_path }}</p>
          <p><a href="{{ download_url }}">Datei herunterladen</a></p>
        </div>

        <div class="box">
          <h2>Vollstaendige Vorschau</h2>
          <textarea class="preview" readonly>{{ preview }}</textarea>
        </div>
      {% endif %}
    </div>
  </body>
</html>
"""


# Nimmt entweder einen Dateipfad aus dem Formular oder speichert einen Upload temporaer ab.
def _resolve_input_file():
    # Die Weboberflaeche erlaubt zwei Wege: einen lokalen Pfad eintippen oder eine Datei
    # direkt im Browser hochladen.
    uploaded_file = request.files.get("upload")
    input_path = (request.form.get("file_path") or "").strip()

    if uploaded_file and uploaded_file.filename:
        # Der Dateiname wird bereinigt, damit keine problematischen Sonderzeichen oder
        # Pfadangaben aus dem Browser uebernommen werden.
        file_name = secure_filename(uploaded_file.filename)
        saved_path = UPLOAD_DIR / file_name
        uploaded_file.save(saved_path)
        return str(saved_path)

    # Wenn kein Upload vorhanden ist, wird der manuell eingegebene Pfad verwendet.
    if input_path:
        return input_path

    raise ValueError("Bitte waehle eine Datei aus oder gib einen Dateipfad an.")


# Rendert das Formular und fuehrt bei POST die Konvertierung inklusive Vorschau aus.
@app.route("/", methods=["GET", "POST"])
def index():
    # context sammelt alle Werte, die im HTML-Template angezeigt werden sollen.
    # Dadurch bleibt die Darstellung zentral steuerbar.
    context = {
        "error": None,
        "result_path": None,
        "preview": "",
        "download_url": None,
        "file_path": "",
        "target_format": "json",
        "columns": "",
        "available_columns": [],
    }

    if request.method == "POST":
        # Die Benutzereingaben werden aus dem Formular gelesen und in ein einheitliches
        # Format gebracht.
        target_format = (request.form.get("target_format") or "json").lower()
        columns_raw = (request.form.get("columns") or "").strip()
        columns = [item.strip() for item in columns_raw.split(",") if item.strip()]

        # Diese Werte werden zurueck ins Template gegeben, damit das Formular nach dem
        # Absenden weiter ausgefuellt bleibt.
        context["target_format"] = target_format
        context["columns"] = columns_raw

        try:
            # Zuerst wird die Eingabedatei aufgeloest, egal ob sie aus einem Upload oder
            # aus einem Dateipfad stammt.
            input_file = _resolve_input_file()
            context["file_path"] = input_file

            # Vor der eigentlichen Konvertierung werden die erkannten Spalten geladen,
            # damit der Benutzer nachvollziehen kann, welche Namen verfuegbar sind.
            context["available_columns"] = get_available_columns(input_file)

            # Die Konvertierung selbst passiert ausschliesslich in file_format_converter.py.
            result_path = convert_file(
                input_file,
                target_format,
                selected_columns=columns or None,
            )

            # Danach werden Speicherort, Vorschau und Download-Link fuer die Ausgabe
            # vorbereitet, damit alles direkt im Browser sichtbar ist.
            context["result_path"] = result_path
            context["preview"] = preview_file(result_path)
            context["download_url"] = f"/download/{Path(result_path).name}"
        except Exception as exc:
            # Fachliche und technische Fehler werden als Text zur Seite durchgereicht,
            # damit der Benutzer eine verstaendliche Rueckmeldung erhaelt.
            context["error"] = str(exc)

    # Am Ende wird immer dieselbe Seite gerendert. Je nach Inhalt von context erscheinen
    # dort Formular, Fehler, Ergebnis oder Vorschau.
    return render_template_string(PAGE, **context)


# Stellt die erzeugte Datei aus dem output/-Ordner zum Download bereit.
@app.route("/download/<path:file_name>")
def download(file_name):
    # Der Dateiname wird auf seinen reinen Namen reduziert, damit nur Dateien aus dem
    # vorgesehenen output/-Ordner ausgeliefert werden.
    return send_file(OUTPUT_DIR / Path(file_name).name, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
