#!/usr/bin/env python3
"""
STEP 2 - Estrazione dei DATI GREZZI dal video (nessun hash, nessun condizionamento)
===================================================================================
Obiettivo: ottenere i campioni "crudi" della sorgente, cosi' che lo Step 3
(NIST SP 800-90B) possa stimare quanta entropia contengono davvero.

Definizione del campione (da scrivere in tesi):
  1. si prende ogni frame, lo si converte in grigio e lo si riduce a una risoluzione
     comune (default 640x360, media di area) -> sorgenti confrontabili;
  2. si fissa una griglia regolare di punti (default 1 punto ogni 16 pixel);
  3. per ogni punto, campione = (valore al frame t) - (valore al frame t-1)  mod 256,
     tenendo gli ultimi --bit bit (default 8, cioe' il valore intero).

Si producono blocchi di 1.000.000 di campioni presi da punti DIVERSI del video
(default 5 blocchi), cosi' si vede se la stima e' stabile nel tempo.
Ogni blocco viene scritto in due ordinamenti (la stima 90B e' sensibile all'ordine):
  *_spazio.bin : i punti di uno stesso frame uno dopo l'altro (cattura la dipendenza spaziale)
  *_tempo.bin  : la serie temporale di ogni punto (cattura la dipendenza nel tempo)
La stima prudente sara' il MINIMO tra i due.

Uso base:
  python step2_estrai_grezzo.py fireplace_40min.mp4
Prove di sensibilita' (Step 6), esempi:
  python step2_estrai_grezzo.py video.mp4 --bit 1
  python step2_estrai_grezzo.py video.mp4 --salto 4        (simula 1/4 degli fps)
  python step2_estrai_grezzo.py video.mp4 --escludi 520,10,110,30   (maschera un orologio)
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tempo_s(txt):
    """'7:24' -> 444 ; '1:02:03' -> 3723 ; '95' -> 95"""
    v = 0.0
    for p in txt.strip().split(":"):
        v = v * 60 + float(p)
    return v


def parse_evita(txt, prima, dopo):
    """'7:24,16:35,18:58-19:20' -> [(a,b), ...] in secondi. Gli istanti singoli
    vengono allargati di 'prima' secondi prima e 'dopo' secondi dopo."""
    out = []
    for tok in [t for t in txt.split(",") if t.strip()]:
        if "-" in tok:
            a, b = tok.split("-")
            out.append((tempo_s(a), tempo_s(b)))
        else:
            t = tempo_s(tok)
            out.append((t - prima, t + dopo))
    out.sort()
    merged = []
    for a, b in out:                                   # unisce gli intervalli sovrapposti
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def scegli_inizi(f_start, f_end, evita_f, span, n_blocchi):
    """Divide la regione in tratti permessi (tolti gli intervalli da evitare) e
    distribuisce i blocchi in modo uniforme sul tempo permesso."""
    permessi, cur = [], f_start
    for a, b in evita_f:
        if a > cur:
            permessi.append((cur, min(a, f_end)))
        cur = max(cur, b)
    if cur < f_end:
        permessi.append((cur, f_end))
    fattibili = [(a, b - span) for a, b in permessi if b - a >= span]
    tot = sum(b - a for a, b in fattibili)
    if not fattibili:
        sys.exit("Nessun tratto abbastanza lungo senza eventi da evitare. "
                 "Riduci --campioni, allarga la regione o i margini.")
    targets = [tot * 0.5] if n_blocchi == 1 else [tot * j / (n_blocchi - 1) for j in range(n_blocchi)]
    inizi = []
    for p in targets:
        for a, b in fattibili:
            if p <= b - a or (a, b) == fattibili[-1]:
                inizi.append(int(a + min(p, b - a)))
                break
            p -= b - a
    return inizi, permessi


def diagnostica(x):
    """Statistiche veloci sul flusso di simboli (NON sostituiscono la stima 90B)."""
    cnt = np.bincount(x, minlength=256)
    p = cnt / cnt.sum()
    pmax = p.max()
    nz = p[p > 0]
    return {
        "frazione_zeri": float(p[0]),
        "H_min_solo_valore_piu_frequente": float(-math.log2(pmax)),
        "H_shannon": float(-(nz * np.log2(nz)).sum()),
        "simboli_distinti": int((cnt > 0).sum()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--prefisso", default=None, help="prefisso dei file di output")
    ap.add_argument("--risoluzione", default="640x360")
    ap.add_argument("--passo", type=int, default=16, help="pixel tra due punti della griglia")
    ap.add_argument("--bit", type=int, default=8, help="bit meno significativi da tenere (1-8)")
    ap.add_argument("--salto", type=int, default=1, help="usa 1 frame ogni N (simula fps piu' bassi)")
    ap.add_argument("--campioni", type=int, default=1_000_000, help="campioni per blocco")
    ap.add_argument("--blocchi", type=int, default=5)
    ap.add_argument("--start", type=float, default=0, help="secondo di inizio")
    ap.add_argument("--durata", type=float, default=0, help="secondi su cui distribuire i blocchi (0 = fino alla fine)")
    ap.add_argument("--escludi", default=None, help="x,y,w,h: rettangolo da escludere (coordinate alla risoluzione scelta)")
    ap.add_argument("--evita", default="",
                    help='istanti/intervalli del video da non campionare (tagli di montaggio, mani, ...), '
                         'es. "7:24,16:35,18:58-19:20". Tempi nel video cosi\' com\'e\' (se usi un file ritagliato, '
                         'sottrai l\'inizio del ritaglio).')
    ap.add_argument("--margine", default="8,25",
                    help="secondi evitati PRIMA,DOPO ogni istante singolo di --evita (default 8,25)")
    a = ap.parse_args()

    if not 1 <= a.bit <= 8:
        sys.exit("--bit deve essere tra 1 e 8")
    W, H = (int(v) for v in a.risoluzione.lower().split("x"))
    p = Path(a.video)
    prefisso = a.prefisso or p.with_suffix("").as_posix()

    cap = cv2.VideoCapture(str(p))
    if not cap.isOpened():
        sys.exit(f"Impossibile aprire {p}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # --- griglia di punti
    xs = np.arange(a.passo // 2, W, a.passo)
    ys = np.arange(a.passo // 2, H, a.passo)
    gx, gy = np.meshgrid(xs, ys)
    gx, gy = gx.ravel(), gy.ravel()
    if a.escludi:
        ex, ey, ew, eh = (int(v) for v in a.escludi.split(","))
        keep = ~((gx >= ex) & (gx < ex + ew) & (gy >= ey) & (gy < ey + eh))
        gx, gy = gx[keep], gy[keep]
    S = len(gx)
    frames_blocco = math.ceil(a.campioni / S)
    span = (frames_blocco + 1) * a.salto                  # frame originali occupati da un blocco

    f_start = int(a.start * fps)
    f_end = n_tot if not a.durata else min(n_tot, f_start + int(a.durata * fps))
    if f_end >= n_tot - 1:
        # Il numero di frame scritto nel contenitore puo' essere impreciso (soprattutto dopo un
        # ritaglio con -c copy): lascio 5 secondi di sicurezza in fondo al video.
        f_end -= int(5 * fps)
    if f_end - f_start < span * a.blocchi:
        sys.exit(f"Video troppo corto: servono {span*a.blocchi} frame, ne ho {f_end-f_start}. "
                 "Riduci --blocchi, --campioni o --salto.")
    m_prima, m_dopo = (float(v) for v in a.margine.split(","))
    evita_s = parse_evita(a.evita, m_prima, m_dopo) if a.evita else []
    evita_f = [(int(x * fps), int(y * fps)) for x, y in evita_s]
    inizi, permessi = scegli_inizi(f_start, f_end, evita_f, span, a.blocchi)
    if a.evita:
        print(f"Regione {f_start/fps:.0f}s-{f_end/fps:.0f}s, eventi da evitare: {len(evita_s)} intervalli "
              f"(margine -{m_prima:.0f}s/+{m_dopo:.0f}s)")
        print("Tratti permessi (s): " + ", ".join(f"{x/fps:.0f}-{y/fps:.0f}" for x, y in permessi))

    print(f"{p.name}: {fps:.2f} fps, {n_tot} frame, risoluzione di analisi {W}x{H}")
    print(f"Griglia: {S} punti per frame (passo {a.passo}px) -> {frames_blocco} frame per blocco da {a.campioni} campioni")
    print(f"Frame rate effettivo: {fps/a.salto:.2f} fps (salto {a.salto}), bit per campione: {a.bit}")

    mask_bit = (1 << a.bit) - 1
    meta = {
        "video": p.name, "sha256_video": sha256_file(p), "fps": fps, "frame_totali": n_tot,
        "risoluzione_analisi": [W, H], "passo_griglia": a.passo, "punti_per_frame": S,
        "bit_per_campione": a.bit, "salto_frame": a.salto, "fps_effettivi": fps / a.salto,
        "campioni_per_blocco": a.campioni, "frame_per_blocco": frames_blocco,
        "escludi": a.escludi, "evita": a.evita, "margine": a.margine,
        "regione_s": [f_start / fps, f_end / fps], "blocchi": [], "blocchi_scartati": [],
    }

    for j, f0 in enumerate(inizi):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f0))
        reale = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        ok, fr = cap.read()
        if not ok:
            print(f"  blocco {j}: lettura fallita al frame {f0}, blocco scartato")
            meta["blocchi_scartati"].append(j)
            continue

        def punti(frame):
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            g = cv2.resize(g, (W, H), interpolation=cv2.INTER_AREA)
            return g[gy, gx]

        prev = punti(fr)
        M = np.empty((frames_blocco, S), dtype=np.uint8)
        completo = True
        for k in range(frames_blocco):
            for _ in range(a.salto - 1):
                cap.grab()
            ok, fr = cap.read()
            if not ok:
                completo = False
                break
            cur = punti(fr)
            M[k] = (cur - prev) & mask_bit               # uint8: la sottrazione va in modulo 256
            prev = cur
        if not completo:
            print(f"  blocco {j}: fine video inattesa dopo {k} frame su {frames_blocco}, blocco scartato")
            meta["blocchi_scartati"].append(j)
            continue

        info = {"blocco": j, "frame_iniziale_richiesto": int(f0), "frame_iniziale_reale": reale,
                "secondo_iniziale": round(reale / fps, 1), "file": {}, "diagnostica": {}}
        for nome, arr in (("spazio", M.ravel()), ("tempo", M.T.ravel())):
            x = np.ascontiguousarray(arr[: a.campioni])
            fn = f"{prefisso}_b{j}_{nome}.bin"
            x.tofile(fn)
            info["file"][nome] = fn
            info["diagnostica"][nome] = diagnostica(x)
        d = info["diagnostica"]["spazio"]
        print(f"  blocco {j} (da {info['secondo_iniziale']:.0f}s): zeri {100*d['frazione_zeri']:.1f}%  "
              f"H_min(rapida) {d['H_min_solo_valore_piu_frequente']:.3f}  H_shannon {d['H_shannon']:.3f} bit/campione",
              flush=True)
        meta["blocchi"].append(info)
    cap.release()

    Path(f"{prefisso}_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nScritti {len(meta['blocchi'])*2} file .bin e {Path(prefisso).name}_meta.json")
    if meta["blocchi_scartati"]:
        print(f"ATTENZIONE: blocchi scartati per fine video: {meta['blocchi_scartati']}")
    print("Passo successivo (Step 3), per ogni file .bin:")
    print(f"   ./ea_non_iid -v <file>.bin {a.bit}")


if __name__ == "__main__":
    main()
