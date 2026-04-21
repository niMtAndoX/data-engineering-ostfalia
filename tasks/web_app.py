from pathlib import Path
import tempfile

from flask import Flask, render_template_string, request, send_file
from werkzeug.utils import secure_filename

from format_converter import convert


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "file_converter_uploads"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)


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
        Datei per Upload oder Dateipfad angeben, Zielformat waehlen und konvertieren.
        Die Ausgabedatei wird im Verzeichnis <code>output/</code> gespeichert.
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


def detect_format(file_name):
    suffix = Path(file_name).suffix.lower().lstrip(".")
    if suffix not in {"csv", "json", "xml"}:
        raise ValueError("Unterstuetzt werden nur CSV-, JSON- und XML-Dateien.")
    return suffix


def default_output_path(input_file_name, target_format):
    return OUTPUT_DIR / f"{Path(input_file_name).stem}.{target_format.lower()}"


def preview_file(file_name):
    with open(file_name, "r", encoding="utf-8", errors="replace") as file:
        return file.read()


def _resolve_input_file():
    uploaded_file = request.files.get("upload")
    input_path = (request.form.get("file_path") or "").strip()

    if uploaded_file and uploaded_file.filename:
        file_name = secure_filename(uploaded_file.filename)
        saved_path = UPLOAD_DIR / file_name
        uploaded_file.save(saved_path)
        return saved_path

    if input_path:
        return Path(input_path)

    raise ValueError("Bitte waehle eine Datei aus oder gib einen Dateipfad an.")


@app.route("/", methods=["GET", "POST"])
def index():
    context = {
        "error": None,
        "result_path": None,
        "preview": "",
        "download_url": None,
        "file_path": "",
        "target_format": "json",
    }

    if request.method == "POST":
        target_format = (request.form.get("target_format") or "json").lower()
        context["target_format"] = target_format

        try:
            input_file = _resolve_input_file()
            context["file_path"] = str(input_file)

            input_format = detect_format(input_file)
            if input_format == target_format:
                raise ValueError("Quelldatei und Zielformat sind identisch.")

            result_path = default_output_path(input_file, target_format)

            # Die eigentliche Konvertierung wird ausschliesslich ueber format_converter.py ausgefuehrt.
            convert(str(input_file), input_format, str(result_path), target_format)

            context["result_path"] = str(result_path)
            context["preview"] = preview_file(result_path)
            context["download_url"] = f"/download/{result_path.name}"
        except Exception as exc:
            context["error"] = str(exc)

    return render_template_string(PAGE, **context)


@app.route("/download/<path:file_name>")
def download(file_name):
    return send_file(OUTPUT_DIR / Path(file_name).name, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
