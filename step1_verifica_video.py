#!/usr/bin/env python3
"""
STEP 1 - Verifica di qualita' di un video sorgente per il TRNG
==============================================================
Cosa fa (NON estrae nessun bit casuale, controlla solo il video):
  1. registra l'impronta SHA-256 del file (per citarla in tesi: riproducibilita')
  2. legge i metadati (codec, risoluzione, fps, bitrate) con ffprobe
  3. scorre il video e cerca i problemi che falsano un esperimento:
       - frame duplicati (es. video a 30 fps convertito a 60 fps)
       - tagli di scena
       - tratti accelerati / rallentati
       - tratti ripetuti (loop)
  4. propone il segmento "pulito" piu' lungo e il comando ffmpeg per ritagliarlo
Cosa NON vede: scritte, loghi o intro. Guarda a occhio i primi/ultimi minuti.

Uso:
  python step1_verifica_video.py video.mp4
  python step1_verifica_video.py video.mp4 --start 60 --durata 1800   (solo un pezzo)
Produce: <video>_verifica.txt e <video>_verifica.png
"""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blocco in iter(lambda: f.read(1 << 20), b""):
            h.update(blocco)
    return h.hexdigest()


def info_ffprobe(path):
    if not shutil.which("ffprobe"):
        return None
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries",
           "stream=codec_name,profile,width,height,r_frame_rate,avg_frame_rate,bit_rate,nb_frames,pix_fmt"
           ":format=duration,bit_rate,format_name",
           "-of", "json", str(path)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        return json.loads(out)
    except Exception:
        return None


def analizza(path, start, durata):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        sys.exit(f"Impossibile aprire {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if start > 0:
        cap.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    max_frame = int(durata * fps) if durata else None
    stride_thumb = max(int(round(fps)),
                       math.ceil((max_frame or tot) / 4000))  # max ~4000 miniature

    ok, prev = cap.read()
    if not ok:
        sys.exit("Video vuoto o illeggibile")
    prev = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    mean_diff, frac_changed, thumbs = [], [], []
    n = 0
    while True:
        ok, fr = cap.read()
        if not ok or (max_frame and n >= max_frame):
            break
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        d = cv2.absdiff(g, prev)
        mean_diff.append(float(d.mean()))
        frac_changed.append(cv2.countNonZero(d) / d.size)
        if n % stride_thumb == 0:
            thumbs.append(cv2.resize(g, (64, 36), interpolation=cv2.INTER_AREA).astype(np.float32).ravel())
        prev = g
        n += 1
        if n % 5000 == 0:
            print(f"  ...{n} frame analizzati", flush=True)
    cap.release()
    return fps, np.array(mean_diff), np.array(frac_changed), np.array(thumbs), stride_thumb


def per_secondo(x, fps):
    s = int(round(fps))
    k = len(x) // s
    return x[: k * s].reshape(k, s)


def trova_loop(thumbs, stride_thumb, fps, soglia=0.98, gap_s=30, run=5):
    """Cerca tratti di video quasi identici a tratti molto precedenti."""
    if len(thumbs) < run + 2:
        return []
    T = thumbs - np.median(thumbs, axis=0)           # toglie lo sfondo fisso
    T = T - T.mean(axis=1, keepdims=True)
    nrm = np.linalg.norm(T, axis=1, keepdims=True)
    nrm[nrm < 1e-6] = 1e-6
    T = T / nrm
    C = T @ T.T
    n = len(T)
    gap = max(1, int(gap_s * fps / stride_thumb))
    M = np.triu(C > soglia, k=gap)
    L = n - run + 1
    R = M[:L, :L].copy()
    for k in range(1, run):
        R &= M[k:L + k, k:L + k]
    coppie = np.argwhere(R)
    res, visti = [], set()
    for i, j in coppie:
        if (j - i) in visti:
            continue
        visti.add(j - i)
        res.append((i * stride_thumb / fps, j * stride_thumb / fps))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--start", type=float, default=0, help="secondo da cui iniziare")
    ap.add_argument("--durata", type=float, default=0, help="secondi da analizzare (0 = tutto)")
    a = ap.parse_args()
    p = Path(a.video)
    righe = []

    def out(s=""):
        print(s)
        righe.append(s)

    out(f"=== VERIFICA VIDEO: {p.name} ===")
    out(f"SHA-256 file : {sha256_file(p)}")
    info = info_ffprobe(p)
    if info and info.get("streams"):
        s, f = info["streams"][0], info.get("format", {})
        out(f"Codec        : {s.get('codec_name')} ({s.get('profile')})  pix_fmt={s.get('pix_fmt')}")
        out(f"Risoluzione  : {s.get('width')}x{s.get('height')}")
        out(f"Frame rate   : {s.get('avg_frame_rate')}  (r={s.get('r_frame_rate')})")
        br = s.get("bit_rate") or f.get("bit_rate")
        out(f"Bitrate      : {int(br)/1e6:.2f} Mbit/s" if br else "Bitrate      : n/d")
        out(f"Durata       : {float(f.get('duration', 0))/60:.1f} min")
    else:
        out("(ffprobe non disponibile: metadati omessi)")

    out("\nAnalisi dei frame in corso (puo' richiedere diversi minuti)...")
    fps, md, fc, thumbs, st = analizza(p, a.start, a.durata)
    n = len(md)
    out(f"Frame analizzati: {n}  ({n/fps/60:.1f} min a {fps:.2f} fps)")

    # --- 1. duplicati
    # esatti: nessun pixel cambiato. Quasi-identici: delta < 15% del delta tipico di quel secondo
    # (i video compressi spesso ripetono un frame con piccolissime differenze).
    blocchi = per_secondo(md, fps)
    tipico = np.percentile(blocchi, 75, axis=1, keepdims=True)
    dup_blocchi = blocchi < 0.15 * tipico
    dup = np.zeros(len(md), dtype=bool)
    dup[: dup_blocchi.size] = dup_blocchi.ravel()
    dup |= fc == 0
    dup_ratio = dup.mean()
    out(f"\n[1] Frame identici o quasi identici al precedente: {100*dup_ratio:.2f}%"
        f"  (di cui esattamente identici: {100*(fc == 0).mean():.2f}%)")
    if dup_ratio > 0.40:
        out("    ATTENZIONE: ~meta' dei frame e' duplicata -> video convertito a fps piu' alto."
            " Il delta dei frame pari e' ~zero: conviene sotto-campionare (1 frame ogni 2).")
    elif dup_ratio > 0.01:
        out("    ATTENZIONE: duplicati diffusi o sporadici (conversione fps parziale, pause/lag della sorgente).")
    else:
        out("    OK")

    # --- 2. tagli e accelerazioni (per secondo)
    sec = per_secondo(md, fps)
    mds = np.median(sec, axis=1)                     # mediana per secondo
    mx = sec.max(axis=1)
    med = np.median(mds)
    tagli = np.where(mx > max(8 * med, 6.0))[0]
    out(f"\n[2] Delta medio per frame (mediana globale): {med:.3f} livelli di grigio")
    if len(tagli):
        elenco = ", ".join(f"{t//60}:{t%60:02d}" for t in tagli[:12])
        out(f"    Possibili TAGLI di scena a: {elenco}{' ...' if len(tagli) > 12 else ''}")
    else:
        out("    Nessun taglio di scena evidente. OK")

    k = 60 if len(mds) >= 600 else max(5, len(mds) // 10)
    if len(mds) >= 2 * k:
        liscia = np.convolve(mds, np.ones(k) / k, mode="valid")
        rapp = liscia / max(med, 1e-9)
        anom = np.where((rapp > 1.8) | (rapp < 0.5))[0]
        if len(anom):
            out(f"    Tratti con dinamica anomala (>1.8x o <0.5x la mediana, finestra {k} s):"
                f" {len(anom)} finestre, es. a {anom[0]//60}:{anom[0]%60:02d}"
                " -> controlla: accelerazione, intro/outro o cambio di scena")
        else:
            out("    Dinamica stabile nel tempo. OK")
    else:
        anom = np.array([], dtype=int)
        out("    (video troppo corto per l'analisi della dinamica nel tempo)")

    # --- 3. loop
    loop = trova_loop(thumbs, st, fps)
    out(f"\n[3] Tratti RIPETUTI (loop): {len(loop)} candidati")
    for (t1, t2) in loop[:6]:
        out(f"    ~{int(t1)//60}:{int(t1)%60:02d}  assomiglia a  ~{int(t2)//60}:{int(t2)%60:02d}")
    if not loop:
        out("    Nessun loop evidente. OK")
    else:
        out("    (guarda a occhio quei due punti: possono essere falsi positivi)")

    # --- 4. segmento pulito
    brutti = np.zeros(len(mds), dtype=bool)
    for t in tagli:
        brutti[max(0, t - 2): t + 3] = True
    if len(mds) >= 2 * k:
        for w in anom:
            brutti[w: w + k] = True
    brutti |= per_secondo(dup.astype(float), fps).mean(axis=1) > 0.4
    for (_, t2) in loop:
        brutti[int(t2): int(t2) + 30] = True
    best, cur, cur_start, best_start = 0, 0, 0, 0
    for i, b in enumerate(brutti):
        if not b:
            if cur == 0:
                cur_start = i
            cur += 1
            if cur > best:
                best, best_start = cur, cur_start
        else:
            cur = 0
    s0 = int(a.start) + best_start
    out(f"\n[4] Segmento pulito piu' lungo: da {s0//60}:{s0%60:02d}, durata {best/60:.1f} min")
    out(f'    ffmpeg -ss {s0} -t {best} -i "{p.name}" -c copy "{p.stem}_pulito.mp4"')
    out("    (poi controlla a occhio che nel pezzo non ci siano scritte o loghi)")

    # --- grafico
    fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True)
    t = np.arange(len(mds)) / 60 + a.start / 60
    ax[0].plot(t, mds, lw=0.8)
    ax[0].set_ylabel("delta medio (mediana/s)")
    ax[0].set_yscale("log")
    ax[0].set_title(f"{p.name}: dinamica nel tempo")
    for tg in tagli:
        ax[0].axvline(tg / 60 + a.start / 60, color="r", alpha=0.4)
    ax[0].axvspan(best_start / 60 + a.start / 60, (best_start + best) / 60 + a.start / 60,
                  color="g", alpha=0.12, label="segmento pulito")
    ax[0].legend(loc="upper right")
    ax[1].plot(t, 100 * per_secondo(dup.astype(float), fps).mean(axis=1), lw=0.8, color="orange")
    ax[1].set_ylabel("% frame duplicati")
    ax[1].set_xlabel("minuti")
    plt.tight_layout()
    png = p.with_name(p.stem + "_verifica.png")
    plt.savefig(png, dpi=130)
    p.with_name(p.stem + "_verifica.txt").write_text("\n".join(righe), encoding="utf-8")
    out(f"\nSalvati: {p.stem}_verifica.txt e {png.name}")


if __name__ == "__main__":
    main()
