from flask import Flask, render_template, request

app = Flask(__name__)


def caesar_verarbeitung(text: str, schluessel: int) -> str:
    """
    Verschiebt alle Buchstaben im Text um den angegebenen Schlüssel.
    Positive Schlüssel verschlüsseln, negative Schlüssel entschlüsseln.
    """
    ergebnis = ""

    for zeichen in text:
        if zeichen.isalpha():
            if zeichen.isupper():
                start = ord("A")
            else:
                start = ord("a")

            neue_position = (ord(zeichen) - start + schluessel) % 26
            neues_zeichen = chr(start + neue_position)
            ergebnis += neues_zeichen
        else:
            ergebnis += zeichen

    return ergebnis


def verschluesseln(text: str, schluessel: int) -> str:
    return caesar_verarbeitung(text, schluessel)


def entschluesseln(text: str, schluessel: int) -> str:
    return caesar_verarbeitung(text, -schluessel)

def kryptoanalyse_brute_force(text: str) -> list[tuple[int, str]]:
    """
    Führt eine Brute-Force-Kryptoanalyse der Cäsar-Verschlüsselung durch.
    Es werden alle 26 möglichen Schlüssel ausprobiert.
    """
    moegliche_texte = []

    for schluessel in range(26):
        entschluesselter_text = entschluesseln(text, schluessel)
        moegliche_texte.append((schluessel, entschluesselter_text))

    return moegliche_texte


@app.route("/", methods=["GET", "POST"])
def index():
    text = ""
    schluessel = 3
    modus = "verschluesseln"
    ergebnis = ""
    fehler = ""
    analyse_ergebnisse = []

    if request.method == "POST":
        text = request.form.get("text", "")
        modus = request.form.get("modus", "verschluesseln")

        try:
            schluessel = int(request.form.get("schluessel", "0"))

            if modus == "entschluesseln":
                ergebnis = entschluesseln(text, schluessel)

            elif modus == "kryptoanalyse":
                analyse_ergebnisse = kryptoanalyse_brute_force(text)

            else:
                ergebnis = verschluesseln(text, schluessel)

        except ValueError:
            fehler = "Der Schlüssel muss eine ganze Zahl sein."

    return render_template(
        "index.html",
        text=text,
        schluessel=schluessel,
        modus=modus,
        ergebnis=ergebnis,
        fehler=fehler,
        analyse_ergebnisse=analyse_ergebnisse
    )

if __name__ == "__main__":
    app.run(debug=True)