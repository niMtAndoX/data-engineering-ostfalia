import pandas as pd
import random


def erzeuge_datensatz(anzahl_zeilen: int, anzahl_duplikate: int) -> pd.DataFrame:
    """
    Erzeugt einen Datensatz mit einer festgelegten Anzahl an zusätzlichen Duplikaten.
    """

    if anzahl_zeilen <= 0:
        raise ValueError("Die Anzahl der Zeilen muss größer als 0 sein.")

    if anzahl_duplikate < 0:
        raise ValueError("Die Anzahl der Duplikate darf nicht negativ sein.")

    daten = []

    for i in range(anzahl_zeilen):
        zeile = [
            i + 1,                          # eindeutige ID
            random.randint(1, 9),           # ganze Zahl
            random.choice(["K", "L", "M", "N", "O"]),
            round(random.uniform(1.0, 9.9), 1),
            random.randint(10, 99)
        ]
        daten.append(zeile)

    df = pd.DataFrame(daten, columns=["A", "B", "C", "D", "E"])

    # Duplikate aus bestehenden Zeilen ziehen
    duplikate = df.sample(
        n=anzahl_duplikate,
        replace=True
    )

    # Originaldaten und Duplikate zusammenführen
    df_mit_duplikaten = pd.concat([df, duplikate], ignore_index=True)

    # Zeilen mischen
    df_mit_duplikaten = df_mit_duplikaten.sample(
        frac=1
    ).reset_index(drop=True)

    return df_mit_duplikaten


def entferne_duplikate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Entfernt vollständig identische Zeilen aus dem Datensatz.
    """
    return df.drop_duplicates().reset_index(drop=True)


def main():
    anzahl_zeilen = 7
    anzahl_duplikate = 3

    datensatz = erzeuge_datensatz(anzahl_zeilen, anzahl_duplikate)

    print("Datensatz mit Duplikaten:")
    print(datensatz)

    bereinigter_datensatz = entferne_duplikate(datensatz)

    print("\nDatensatz ohne Duplikate:")
    print(bereinigter_datensatz)

    print("\nAnzahl Zeilen vorher:", len(datensatz))
    print("Anzahl Zeilen nachher:", len(bereinigter_datensatz))


if __name__ == "__main__":
    main()