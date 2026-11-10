#!/usr/bin/env python3
"""
FIGURA PER IL CAPITOLO METODO
=============================
Per ognuna delle 4 sorgenti produce una colonna con tre immagini:
  riga 1: un fotogramma in grigio 640x360 con sopra la griglia dei 40x22 = 880 punti campionati;
  riga 2: la mappa delle differenze tra due fotogrammi consecutivi (cio' che diventa il campione);
  riga 3: l'"attivita'" di ogni punto della griglia su un intero blocco (1137 fotogrammi):
          la frazione di fotogrammi in cui il campione e' diverso da zero.
La riga 3 serve anche a verificare l'ipotesi dei "pixel fermi" (vedi i risultati stampati in console).

Uso (dalla cartella dove ci sono i 4 video):
  python figura_metodo.py --camino fireplace_video.mp4 --pioggia rain_40min.mp4 \
                          --lava lavalamp_40min.mp4 --traffico traffic_40min.mp4

Opzioni: --t SECONDI (istante del fotogramma, default 600 = 10:00), --uscita nome.png
Servono: pip install opencv-python numpy matplotlib
"""
import argparse
import csv
import sys

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

W, H, PASSO, FRAME_BLOCCO = 640, 360, 16, 1137


def grigio(fr):
    g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (W, H), interpolation=cv2.INTER_AREA)


def analizza(path, t):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"Impossibile aprire {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
    xs = np.arange(PASSO // 2, W, PASSO)
    ys = np.arange(PASSO // 2, H, PASSO)
    prev, frame0, diff0 = None, None, None
    attivo = np.zeros((len(ys), len(xs)))
    n = 0
    zeri = 0
    for _ in range(FRAME_BLOCCO + 1):
        ok, fr = cap.read()
        if not ok:
            break
        g = grigio(fr)
        if prev is not None:
            d = (g.astype(np.int16) - prev.astype(np.int16)) % 256
            dg = d[np.ix_(ys, xs)]                 # campioni sulla griglia
            attivo += (dg != 0)
            zeri += int((dg == 0).sum())
            n += 1
            if n == 1:
                frame0 = g.copy()
                diff0 = np.minimum(np.abs(g.astype(np.int16) - prev.astype(np.int16)), 255)
        prev = g
    if n == 0:
        sys.exit(f"Nessun fotogramma letto da {path}")
    return frame0, diff0, attivo / n, xs, ys, zeri / (n * len(xs) * len(ys))


def main():
    ap = argparse.ArgumentParser()
    for k in ("camino", "pioggia", "lava", "traffico"):
        ap.add_argument(f"--{k}", required=True)
    ap.add_argument("--t", type=float, default=600.0)
    ap.add_argument("--uscita", default="fig_metodo_griglia.png")
    a = ap.parse_args()
    fonti = [("Camino", a.camino), ("Pioggia", a.pioggia), ("Lava lamp", a.lava), ("Traffico (notte)", a.traffico)]

    fig, axs = plt.subplots(3, 4, figsize=(16, 8.6))
    righe = []
    for c, (nome, path) in enumerate(fonti):
        print(f"Analizzo {nome} ...")
        f0, d0, att, xs, ys, fz = analizza(path, a.t)
        gx, gy = np.meshgrid(xs, ys)
        ax = axs[0, c]
        ax.imshow(f0, cmap="gray", vmin=0, vmax=255)
        ax.scatter(gx.ravel(), gy.ravel(), s=3, c="#ff6b35")
        ax.set_title(nome, fontsize=13, fontweight="bold")
        ax = axs[1, c]
        ax.imshow(np.clip(d0 * 4, 0, 255), cmap="magma", vmin=0, vmax=255)
        ax = axs[2, c]
        im = ax.imshow(att, cmap="viridis", vmin=0, vmax=1, extent=(0, W, H, 0))
        for r in axs[:, c]:
            r.set_xticks([]); r.set_yticks([])
        poco = float((att < 0.05).mean())
        tutto = float((att > 0.95).mean())
        ax.set_xlabel(f"zeri: {fz*100:.1f}%  |  punti quasi fermi (<5%): {poco*100:.1f}%", fontsize=9)
        righe.append((nome, fz, poco, float(np.median(att)), tutto))
    axs[0, 0].set_ylabel("Fotogramma e griglia\n(40 x 22 = 880 punti)", fontsize=11)
    axs[1, 0].set_ylabel("|G_t - G_(t-1)| x 4\n(un fotogramma)", fontsize=11)
    axs[2, 0].set_ylabel("Attivita' dei punti\n(su 1137 fotogrammi)", fontsize=11)
    cb = fig.colorbar(im, ax=axs[2, :], orientation="horizontal", fraction=0.03, pad=0.14)
    cb.set_label("frazione di fotogrammi in cui il campione e' diverso da zero")
    fig.savefig(a.uscita, dpi=200, bbox_inches="tight")
    print(f"\nFigura salvata in {a.uscita}\n")
    print(f"{'Sorgente':18s} {'campioni=0':>11s} {'punti <5% attivi':>17s} {'attivita mediana':>17s}")
    with open("attivita_punti.csv", "w", newline="", encoding="utf8") as f:
        w = csv.writer(f); w.writerow(["sorgente", "frazione_zeri", "punti_quasi_fermi", "attivita_mediana", "punti_sempre_attivi"])
        for nome, fz, poco, med, tutto in righe:
            print(f"{nome:18s} {fz*100:10.1f}% {poco*100:16.1f}% {med:17.3f}")
            w.writerow([nome, round(fz, 4), round(poco, 4), round(med, 4), round(tutto, 4)])
    print("Scritto anche attivita_punti.csv")


if __name__ == "__main__":
    main()
