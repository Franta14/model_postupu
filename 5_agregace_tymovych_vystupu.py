import glob
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Kolik % odchylky od mediánu terénu ještě ponechat.
MAX_ODCHYLKA_PROCENT = 30.0


def nacti_vsechny_tabulky():
    soubory = sorted(glob.glob("vystup_tymova_analytika*.xlsx"))
    if not soubory:
        raise FileNotFoundError("Nebyl nalezen žádný soubor 'vystup_tymova_analytika*.xlsx'.")

    vse = []
    for soubor in soubory:
        df = pd.read_excel(soubor, index_col=0)
        # Odstraní souhrnný sloupec bez ohledu na diakritiku/kódování.
        sloupce_keep = [c for c in df.columns if "CELKOV" not in str(c).upper()]
        df = df[sloupce_keep]

        df_reset = df.reset_index()
        prvni_sloupec = df_reset.columns[0]
        df_reset = df_reset.rename(columns={prvni_sloupec: "TEREN"})

        long_df = (
            df_reset
            .melt(id_vars=["TEREN"], var_name="ZdrojSloupec", value_name="Hodnota")
        )
        long_df["Soubor"] = Path(soubor).name
        vse.append(long_df)

    spojene = pd.concat(vse, ignore_index=True)
    spojene = spojene.dropna(subset=["Hodnota"]).copy()
    return soubory, spojene


def odfiltruj_odlehle_hodnoty(df):
    out = df.copy()
    mediany = out.groupby("TEREN")["Hodnota"].transform("median")
    out["OdchylkaPct"] = np.where(
        mediany > 0,
        (out["Hodnota"] - mediany).abs() / mediany * 100.0,
        0.0,
    )
    out["Ponechat"] = out["OdchylkaPct"] <= MAX_ODCHYLKA_PROCENT
    return out


def vytvor_finalni_tabulku(df):
    filtrovane = df[df["Ponechat"]].copy()
    souhrn = (
        filtrovane.groupby("TEREN")["Hodnota"]
        .agg(FINALNI_PRUMER="mean", MEDIAN="median", SM_ODCHYLKA="std", POCET="count")
        .round(3)
    )

    pocty_pred = df.groupby("TEREN")["Hodnota"].size().rename("POCET_PUVODNI")
    pocty_po = filtrovane.groupby("TEREN")["Hodnota"].size().rename("POCET_PO_FILTRU")
    souhrn = souhrn.join(pocty_pred, how="left").join(pocty_po, how="left")
    souhrn["VYRAZENO"] = (souhrn["POCET_PUVODNI"] - souhrn["POCET_PO_FILTRU"]).astype(int)
    return filtrovane, souhrn.sort_values("FINALNI_PRUMER")


def main():
    soubory, spojene = nacti_vsechny_tabulky()
    oznacene = odfiltruj_odlehle_hodnoty(spojene)
    filtrovane, finalni = vytvor_finalni_tabulku(oznacene)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    vystup = f"vystup_tymova_agregace_{ts}.xlsx"

    with pd.ExcelWriter(vystup) as writer:
        finalni.to_excel(writer, sheet_name="Finalni souhrn")
        filtrovane.to_excel(writer, sheet_name="Filtrovana dlouha data", index=False)
        oznacene.to_excel(writer, sheet_name="Vsechna data s filtrem", index=False)

    print(f"Nalezeno souborů: {len(soubory)}")
    print(f"Limit odchylky: {MAX_ODCHYLKA_PROCENT:.1f}% od mediánu terénu")
    print(f"Uloženo: {vystup}")
    print("\nFinální tabulka:")
    print(finalni.to_string())


if __name__ == "__main__":
    main()
