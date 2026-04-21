from collections import Counter
import heapq
import pickle


# Repräsentiert einen Knoten im Huffman-Baum für Zeichen und Häufigkeiten.
class Node:
    def __init__(self, char=None, freq=0, left=None, right=None):
        # Ein Blattknoten enthaelt ein Zeichen. Innere Knoten enthalten meist kein
        # eigenes Zeichen, sondern nur die Summe der Haeufigkeiten ihrer Kinder.
        self.char = char
        self.freq = freq
        self.left = left
        self.right = right

    def __lt__(self, other):
        # heapq benoetigt einen Vergleichsoperator, um Knoten nach ihrer Haeufigkeit
        # in einer Prioritaetswarteschlange sortieren zu koennen.
        return self.freq < other.freq


# Baut aus einem Text den Huffman-Baum und liefert zusätzlich die Zeichenhäufigkeiten zurück.
def build_tree(text):
    # Zuerst wird gezaehlt, wie oft jedes Zeichen im Text vorkommt.
    freq = Counter(text)
    # Aus jeder Haeufigkeit wird ein Startknoten erzeugt. Der Heap sorgt dafuer,
    # dass immer die zwei seltensten Knoten zuerst entnommen werden.
    heap = [Node(char, count) for char, count in freq.items()]
    heapq.heapify(heap)

    if len(heap) == 1:
        # Spezialfall: Besteht der Text nur aus einem einzigen unterschiedlichen Zeichen,
        # braucht der Baum trotzdem eine gueltige Struktur mit einem Kind.
        only = heapq.heappop(heap)
        return Node(freq=only.freq, left=only), freq

    while len(heap) > 1:
        # Die beiden seltensten Teilbaeume werden zu einem neuen Elternknoten verbunden.
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        parent = Node(freq=left.freq + right.freq, left=left, right=right)
        heapq.heappush(heap, parent)

    # Am Ende bleibt genau ein Wurzelknoten uebrig: der fertige Huffman-Baum.
    return heap[0], freq


# Durchläuft den Huffman-Baum rekursiv und erzeugt die Bitcodes für alle Zeichen.
def build_codes(node, code="", codes=None):
    if codes is None:
        codes = {}

    if node.char is not None:
        # Ein Blattknoten steht fuer ein echtes Zeichen. Der bis hierhin aufgebaute
        # Pfad aus 0 und 1 ist sein Huffman-Code.
        codes[node.char] = code if code != "" else "0"
        return codes

    # Nach links wird eine 0 angehaengt, nach rechts eine 1. So entstehen fuer jedes
    # Zeichen eindeutige Binärcodes.
    build_codes(node.left, code + "0", codes)
    build_codes(node.right, code + "1", codes)
    return codes


# Kodiert den kompletten Text mithilfe der berechneten Huffman-Codes als Bitfolge.
def encode_text(text, codes):
    # Jedes Zeichen wird durch seinen kuerzeren Huffman-Code ersetzt und alle Codes
    # werden zu einer langen Bitfolge zusammengesetzt.
    return "".join(codes[ch] for ch in text)


# Baut den Huffman-Baum später nur aus den gespeicherten Häufigkeiten erneut auf.
def rebuild_tree(freq):
    # Die Rekonstruktion funktioniert gleich wie beim urspruenglichen Baumaufbau.
    # Deshalb reichen die gespeicherten Haeufigkeiten fuer die Dekompression aus.
    heap = [Node(char, count) for char, count in freq.items()]
    heapq.heapify(heap)

    if len(heap) == 1:
        # Auch hier muss der Spezialfall eines einzigen Zeichens abgefangen werden.
        only = heapq.heappop(heap)
        return Node(freq=only.freq, left=only)

    while len(heap) > 1:
        # Wieder werden Schritt fuer Schritt die seltensten Knoten zusammengefuehrt.
        left = heapq.heappop(heap)
        right = heapq.heappop(heap)
        parent = Node(freq=left.freq + right.freq, left=left, right=right)
        heapq.heappush(heap, parent)

    return heap[0]


# Dekodiert eine Bitfolge wieder in den ursprünglichen Text.
def decode_bits(bits, tree, text_length):
    result = []
    node = tree

    for bit in bits:
        # Jedes Bit entscheidet, ob im Baum nach links oder rechts gegangen wird.
        if bit == "0":
            node = node.left
        else:
            node = node.right

        if node.char is not None:
            # Sobald ein Blatt erreicht ist, wurde ein vollstaendiges Zeichen gelesen.
            result.append(node.char)
            if len(result) == text_length:
                # text_length verhindert, dass beim letzten ungenutzten Rest der Bitfolge
                # versehentlich zusaetzliche Zeichen gelesen werden.
                break
            # Danach beginnt die Suche fuer das naechste Zeichen wieder an der Wurzel.
            node = tree

    return "".join(result)


# Liest eine Datei ein, komprimiert ihren Inhalt per Huffman und speichert das Ergebnis binär.
def compress(input_file, output_file, encoding="utf-8"):
    # Der komplette Text wird zunaechst im angegebenen Encoding eingelesen.
    with open(input_file, "r", encoding=encoding) as f:
        text = f.read()

    # Aus dem Text werden Baum, Codes und schliesslich die eigentliche Bitfolge erzeugt.
    tree, freq = build_tree(text)
    codes = build_codes(tree)
    bits = encode_text(text, codes)

    # Gespeichert wird nicht der Baum selbst, sondern nur das, was fuer die spaetere
    # Rekonstruktion wirklich noetig ist.
    data = {
        "freq": dict(freq),
        "length": len(text),
        "bits": bits
    }

    # pickle speichert das Python-Dictionary binaer in eine Datei.
    with open(output_file, "wb") as f:
        pickle.dump(data, f)

    # Fuer die Auswertung wird die urspruengliche Dateigroesse in Bits mit der
    # eigentlichen Huffman-Bitfolge verglichen.
    original_bits = len(text.encode(encoding)) * 8
    compressed_bits = len(bits)
    compression_factor = compressed_bits / original_bits

    print("Datei:", input_file)
    print("Originalbits:", original_bits)
    print("Komprimierte Bits:", compressed_bits)
    print("Kompressionsfaktor:", round(compression_factor, 3))
    print()

    return compression_factor


# Stellt aus der gespeicherten Huffman-Struktur und Bitfolge den Originaltext wieder her.
def decompress(input_file, output_file, encoding="utf-8"):
    # Zuerst werden die beim Komprimieren gespeicherten Metadaten wieder geladen.
    with open(input_file, "rb") as f:
        data = pickle.load(f)

    # Daraus wird der Baum rekonstruiert und anschliessend die Bitfolge in Text uebersetzt.
    tree = rebuild_tree(data["freq"])
    text = decode_bits(data["bits"], tree, data["length"])

    # Zum Schluss wird der wiederhergestellte Text als normale Datei ausgegeben.
    with open(output_file, "w", encoding=encoding) as f:
        f.write(text)

    return text


# Beispielaufrufe zum Testen der Kompression und Dekompression mit den bereitgestellten Dateien.
# Diese Aufrufe zeigen, wie die Funktionen praktisch verwendet werden koennen.
compress("Kompression_Woerter.txt", "Kompression_Woerter.huff", encoding="cp1252")
decompress("Kompression_Woerter.huff", "Kompression_Woerter_restored.txt", encoding="cp1252")

compress("Kompression_Zahlen.csv", "Kompression_Zahlen.huff", encoding="utf-8")
decompress("Kompression_Zahlen.huff", "Kompression_Zahlen_restored.csv", encoding="utf-8")
