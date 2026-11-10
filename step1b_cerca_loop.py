#!/usr/bin/env python3
"""
STEP 1b - Controllo rapido anti-loop
====================================
Molti video "1 ORA di pioggia/camino/lava" sono una clip breve (es. 1 minuto)
ripetuta in serie. In quel caso hai pochi secondi di dati veri, non un'ora.

Questo script confronta il video con se stesso spostato nel tempo: se esiste un
periodo P tale che il frame al tempo t assomiglia al frame al tempo t+P,
trova P. Basta analizzare i primi 5 minuti (circa 4-5 minuti di calcolo).

Uso:
  python step1b_cerca_loop.py rainywindow_video.mp4
  python step1b_cerca_loop.py video.mp4 --durata 300 --lag-min 10 --lag-max 150

Interpretazione della "prominenza" del picco migliore (quanto spicca sul fondo):
  > 0.4     loop quasi certo (stessa clip ripetuta)
  0.2-0.4   sospetto: guarda a occhio i due istanti indicati
  0.05-0.2  periodicita' debole (fenomeno fisico ciclico), non e' un loop
  < 0.05    nessuna periodicita'
"""
import argparse
import math
import sys

import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float, default=0)
    ap.add_argument("--durata", type=float, default=300)
    ap.add_argument("--lag-min", type=float, default=10, help="periodo minimo cercato (s)")
    ap.add_argument("--lag-max", type=float, default=150, help="periodo massimo cercato (s)")
    ap.add_argument("--campioni-al-secondo", type=float, default=10)
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.video)
    if not cap.isOpened():
        sys.exit(f"Impossibile aprire {a.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if a.start > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, a.start * 1000)
    passo = max(1, int(round(fps / a.campioni_al_secondo)))
    dt = passo / fps                                   # secondi tra due campioni
    n_frame = int(a.durata * fps)
    print(f"{a.video}: {fps:.2f} fps, analizzo {a.durata:.0f} s (1 frame ogni {passo})...", flush=True)

    thumbs = []
    for i in range(n_frame):
        if i % passo == 0:
            ok, fr = cap.read()
            if not ok:
                break
            g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
            thumbs.append(cv2.resize(g, (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32).ravel())
        else:
            if not cap.grab():
                break
        if i and i % 3000 == 0:
            print(f"  ...{i} frame", flush=True)
    cap.release()
    T = np.array(thumbs)
    n = len(T)
    print(f"Campioni: {n} (durata coperta {n*dt:.0f} s)")
    if n * dt < 2 * a.lag_min + 10:
        sys.exit("Video analizzato troppo corto per questo intervallo di periodi.")

    # toglie lo sfondo fisso e la luminosita' media di ogni frame
    T -= np.median(T, axis=0)
    T -= T.mean(axis=1, keepdims=True)

    # autocorrelazione nel tempo, sommata su tutti i pixel (via FFT, a blocchi)
    N = 1 << int(math.ceil(math.log2(2 * n)))
    pot = np.zeros(N // 2 + 1)
    for c in range(0, T.shape[1], 512):
        F = np.fft.rfft(T[:, c:c + 512], N, axis=0)
        pot += (F * np.conj(F)).real.sum(axis=1)
    acf = np.fft.irfft(pot, N)[:n]
    acf = acf / (n - np.arange(n))                     # media sulle coppie disponibili
    acf = acf / acf[0]

    lo, hi = int(a.lag_min / dt), min(int(a.lag_max / dt), n - 1)
    zona = acf[lo:hi + 1]
    # Un loop vero e' un picco STRETTO e alto. Una lenta decadenza della somiglianza
    # (fiamme, luce che cambia piano) NON e' un loop: la tolgo sottraendo la mediana locale.
    w = max(5, int(20 / dt)) | 1
    pad = np.pad(zona, w // 2, mode="edge")
    base = np.median(np.lib.stride_tricks.sliding_window_view(pad, w), axis=1)
    prom = zona - base
    cand = [i for i in range(1, len(zona) - 1) if prom[i] > prom[i - 1] and prom[i] >= prom[i + 1]]
    cand.sort(key=lambda i: -prom[i])
    print("\nPicchi di somiglianza (periodo, correlazione, prominenza del picco):")
    visti = []
    for i in cand:
        per = (lo + i) * dt
        if any(abs(per - p) < 3 for p in visti):
            continue
        visti.append(per)
        print(f"  periodo ~ {per:6.1f} s   correlazione = {zona[i]:5.2f}   prominenza = {prom[i]:5.2f}")
        if len(visti) == 5:
            break
    if not visti:
        print("  (nessun picco)")
        return
    vmax = prom[cand[0]]
    # tra i picchi alti quasi quanto il migliore prende il periodo PIU' BREVE (gli altri sono multipli)
    primo = min((i for i in cand if prom[i] >= vmax - 0.05), key=lambda i: i)
    best, per = prom[primo], (lo + primo) * dt
    print()
    if best > 0.4:
        print(f"==> LOOP QUASI CERTO: il video si ripete ogni ~{per:.0f} s.")
        print(f"    Dati realmente diversi: circa {per:.0f} s, non {a.durata/60:.0f} minuti. Cambia video.")
    elif best > 0.2:
        print(f"==> SOSPETTO: somiglianza a ~{per:.0f} s. Apri il video in VLC a t=0:30 e t={int(30+per)//60}:{int(30+per)%60:02d}"
              " e confronta a occhio.")
    elif best > 0.05:
        print(f"==> Nessun loop. Periodicita' debole a ~{per:.0f} s: probabile fenomeno fisico ciclico"
              " (es. semaforo, onde). Da citare in tesi, non e' un difetto del video.")
    else:
        print("==> Nessun loop evidente nei primi minuti.")


if __name__ == "__main__":
    main()
