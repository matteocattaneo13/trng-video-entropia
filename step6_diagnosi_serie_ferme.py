#!/usr/bin/env python3
"""
STEP 6 - Diagnosi del calo in ordine "tempo"
============================================
Verifica due ipotesi sul perche' la stima SP 800-90B in ordine tempo e' piu'
bassa di quella in ordine spazio:
  1) fotogrammi ripetuti dal codec  -> conta i fotogrammi con molti campioni nulli
  2) serie ferme di singoli punti    -> serie di zeri piu' lunga per punto e
                                        correlazione con la stima in ordine tempo
Poi, per il camino, riesegue ea_non_iid togliendo i punti fermi per >= SOGLIA
fotogrammi (controprova diagnostica, non una nuova stima).

Uso (dalla cartella dei file .bin):
  python step6_diagnosi_serie_ferme.py --ea ./ea_non_iid --csv analisi/entropia_per_blocco.csv
"""
import argparse, json, re, subprocess
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr, wilcoxon

P, F = 880, 1137
SORGENTI = {"fireplace": "Camino", "rain": "Pioggia", "lava": "Lava lamp", "traffic": "Traffico"}

def serie_max(c):
    z = np.concatenate(([0], (c == 0).astype(np.int8), [0])); d = np.diff(z)
    s, e = np.where(d == 1)[0], np.where(d == -1)[0]
    return int((e - s).max()) if len(s) else 0

def ea(ea_bin, fn):
    out = subprocess.run([ea_bin, str(fn), "8"], capture_output=True, text=True).stdout
    return float(re.search(r"min\(H_original.*?: ([0-9.]+)", out).group(1))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ea", required=True, help="percorso di ea_non_iid")
    ap.add_argument("--csv", default="analisi/entropia_per_blocco.csv")
    ap.add_argument("--soglia", type=int, default=100)
    ap.add_argument("--out", default="analisi")
    a = ap.parse_args()
    H = pd.read_csv(a.csv); out = Path(a.out); out.mkdir(exist_ok=True)
    righe = []
    for pre, nome in SORGENTI.items():
        for b in range(30):
            x = np.fromfile(f"{pre}_full_b{b}_spazio.bin", dtype=np.uint8)
            n = len(x) // P; M = x[: n * P].reshape(n, P)          # fotogrammi x punti
            fz = (M == 0).mean(axis=1)
            sm = np.array([serie_max(M[:, j]) for j in range(P)])
            righe.append(dict(sorgente=pre, blocco=b, frame_tutti_zero=int((fz == 1).sum()),
                              frame_95=int((fz >= .95).sum()), max_frazione_zeri_frame=float(fz.max()),
                              serie_max=int(sm.max()), punti_fermi=int((sm >= a.soglia).sum())))
    D = pd.DataFrame(righe).merge(H[["sorgente", "blocco", "tempo"]], on=["sorgente", "blocco"])
    D.to_csv(out / "diagnosi_serie_ferme.csv", index=False)
    for pre, nome in SORGENTI.items():
        d = D[D.sorgente == pre]; r = spearmanr(d.serie_max, d.tempo)
        print(f"{nome:10} frame tutti zero {d.frame_tutti_zero.sum():4d}  max quota zeri in un frame {d.max_frazione_zeri_frame.max():.3f}  "
              f"rho(serie max, H tempo) = {r.statistic:+.2f} (p={r.pvalue:.1g})  punti fermi (mediana) {d.punti_fermi.median():.0f}")
    # controprova sul camino
    tmp = Path("tmp_filtro"); tmp.mkdir(exist_ok=True); cp = []
    for b in range(30):
        t = np.fromfile(f"fireplace_full_b{b}_tempo.bin", dtype=np.uint8)
        n = len(t) // F; M = t[: n * F].reshape(n, F)              # punti x fotogrammi
        sm = np.array([serie_max(M[j]) for j in range(n)]); k = sm < a.soglia
        Mk = M[k]; Mk.ravel().tofile(tmp / f"b{b}_tempo.bin"); Mk.T.ravel().tofile(tmp / f"b{b}_spazio.bin")
        h0 = H[(H.sorgente == "fireplace") & (H.blocco == b)].iloc[0]
        cp.append(dict(blocco=b, punti_tolti=int((~k).sum()), campioni=int(Mk.size),
                       spazio=h0.spazio, tempo=h0.tempo,
                       spazio_filtrato=ea(a.ea, tmp / f"b{b}_spazio.bin"),
                       tempo_filtrato=ea(a.ea, tmp / f"b{b}_tempo.bin")))
    C = pd.DataFrame(cp); C.to_csv(out / "camino_senza_punti_fermi.csv", index=False)
    print("\nCamino, mediane:", C[["punti_tolti", "spazio", "spazio_filtrato", "tempo", "tempo_filtrato"]].median().round(4).to_dict())
    print("Wilcoxon (tempo filtrato vs originale):", wilcoxon(C.tempo_filtrato, C.tempo))

if __name__ == "__main__":
    main()
