import re
from rapidfuzz.distance import Levenshtein


TEXT = """
An einem sonnigen Tag beschloss ich, einen Spaziergang durch den Park zu machen.
In dem Momend, als ich die grünen Wiesen betrat, hörte ich das Zwitschern der
Voegel in den Bäumen. Die Sonne strahlte hell vom Himmel und der Wint wehte sanft
durch die Blätter. Ich genoss die frische Luft, die Sonne, das Zwitschern der Vögel
und das Gefühl der Freiheit, während ich meinen Weg fortsetzte. Es war ein perfekter
Moment, um die Schönheit der Natur zu würdigen und dem stressigen Alltag für eine
Weile zu entfliehen.
"""


def text_in_woerter_zerlegen(text: str) -> list[str]:
    """
    Entfernt Satzzeichen und gibt alle Wörter in Kleinschreibung zurück.
    """
    return re.findall(r"[A-Za-zÄÖÜäöüß]+", text.lower())


def fuzzy_dubletten_finden(
    text: str,
    maximale_distanz: int = 2,
    minimale_aehnlichkeit: float = 0.65
) -> list[tuple[str, str, int, float]]:
    """
    Findet ähnliche, aber nicht identische Wörter im Text.
    """
    woerter = text_in_woerter_zerlegen(text)
    eindeutige_woerter = sorted(set(woerter))

    fuzzy_dubletten = []

    for i in range(len(eindeutige_woerter)):
        for j in range(i + 1, len(eindeutige_woerter)):
            wort1 = eindeutige_woerter[i]
            wort2 = eindeutige_woerter[j]

            distanz = Levenshtein.distance(wort1, wort2)
            aehnlichkeit = Levenshtein.normalized_similarity(wort1, wort2)

            if (
                0 < distanz <= maximale_distanz
                and aehnlichkeit >= minimale_aehnlichkeit
            ):
                fuzzy_dubletten.append(
                    (wort1, wort2, distanz, aehnlichkeit)
                )

    return fuzzy_dubletten


def main():
    dubletten = fuzzy_dubletten_finden(TEXT)

    print("Gefundene Fuzzy-Dubletten:")
    print("--------------------------")

    if not dubletten:
        print("Keine Fuzzy-Dubletten gefunden.")
        return

    for wort1, wort2, distanz, aehnlichkeit in dubletten:
        print(
            f"{wort1} ↔ {wort2} | "
            f"Levenshtein-Distanz: {distanz} | "
            f"Ähnlichkeit: {aehnlichkeit:.2f}"
        )


if __name__ == "__main__":
    main()