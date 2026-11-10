#!/usr/bin/env python3
"""
STEP 4 - Condizionamento SHA-256 dimensionato sull'entropia misurata (SP 800-90B)
=================================================================================
Per ogni blocco estratto dallo Step 2 e valutato con ea_non_iid (Step 3):
  1. legge la stima di min-entropia H (bit per campione) dal file risultati_90B/<blocco>.txt
     - modo "min"    : H = minimo tra ordinamento spazio e ordinamento tempo (prudente, default)
     - modo "spazio" : H dell'ordinamento spazio (ordine in cui i dati vengono davvero consumati)
     - modo "tempo"  : H dell'ordinamento tempo
  2. calcola quanti campioni servono per ogni uscita da 256 bit:
         k = ceil( margine * 256 / H )      (margine = 2 -> 512 bit di entropia in ingresso)
  3. divide i campioni del blocco (file *_spazio.bin, nell'ordine di estrazione) in pezzi
     consecutivi da k campioni e fa lo SHA-256 di ciascuno. Un blocco con H piccola produce
     poche uscite, uno con H quasi zero non ne produce.
  4. scrive i bit in un unico file binario + un log JSON con i numeri per blocco.

L'SHA-256 non CREA entropia: ne distilla solo quanta ne e' stata misurata a monte.
Quanti bit escono e' quindi il vero "rendimento" della sorgente.

Uso (dalla cartella dei video):
  python step4_condiziona.py fireplace_full
  python step4_condiziona.py rain_full --modo spazio
  python step4_condiziona.py lava_full --margine 2 --risultati risultati_90B
Produce: <prefisso>_cond_<modo>.bin  e  <prefisso>_cond_<modo>_log.json
"""
import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

RE_MIN = re.compile(r"^min\(H_original, 8 X H_bitstring\):\s*([0-9.]+)", re.M)


def leggi_h(path):
    if not path.exists():
        return None
    m = RE_MIN.search(path.read_text(errors="replace"))
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prefisso", help="es. fireplace_full (legge <prefisso>_meta.json)")
    ap.add_argument("--modo", choices=["min", "spazio", "tempo"], default="min")
    ap.add_argument("--margine", type=float, default=2.0,
                    help="entropia in ingresso / 256 per ogni uscita (default 2 -> 512 bit)")
    ap.add_argument("--risultati", default="risultati_90B", help="cartella con i .txt del 90B")
    ap.add_argument("--cartella", default=".", help="cartella dei .bin e del meta.json")
    a = ap.parse_args()

    cart = Path(a.cartella)
    ris = Path(a.risultati)
    meta_p = cart / f"{a.prefisso}_meta.json"
    if not meta_p.exists():
        sys.exit(f"Non trovo {meta_p}")
    meta = json.loads(meta_p.read_text(encoding="utf-8"))

    out_bits = bytearray()
    righe, tot_in_entropia, tot_campioni = [], 0.0, 0
    print(f"{'blocco':>6} {'H spazio':>9} {'H tempo':>9} {'H usata':>9} {'k':>9} {'uscite':>7} {'bit out':>9}")
    for b in meta["blocchi"]:
        j = b["blocco"]
        f_sp = cart / b["file"]["spazio"]
        nome_sp, nome_te = Path(b["file"]["spazio"]).stem, Path(b["file"]["tempo"]).stem
        h_sp = leggi_h(ris / f"{nome_sp}.txt")
        h_te = leggi_h(ris / f"{nome_te}.txt")
        if a.modo == "spazio":
            H = h_sp
        elif a.modo == "tempo":
            H = h_te
        else:
            H = min(h for h in (h_sp, h_te) if h is not None) if (h_sp is not None and h_te is not None) else None
        if H is None:
            sys.exit(f"Manca la stima 90B per il blocco {j} ({nome_sp}.txt / {nome_te}.txt in {ris}). "
                     "Esegui prima lo Step 3 su tutti i blocchi.")
        dati = f_sp.read_bytes()
        n = len(dati)
        tot_campioni += n
        tot_in_entropia += H * n
        k = math.ceil(a.margine * 256 / H) if H > 0 else None
        n_out = (n // k) if k else 0
        for i in range(n_out):
            out_bits += hashlib.sha256(dati[i * k:(i + 1) * k]).digest()
        righe.append({"blocco": j, "H_spazio": h_sp, "H_tempo": h_te, "H_usata": H,
                      "campioni_per_uscita": k, "uscite_256bit": n_out, "bit_out": n_out * 256,
                      "file_sorgente": b["file"]["spazio"]})
        print(f"{j:>6} {h_sp:>9.4f} {h_te:>9.4f} {H:>9.4f} {k if k else 0:>9} {n_out:>7} {n_out*256:>9}")

    bit_tot = len(out_bits) * 8
    print(f"\nEntropia totale stimata in ingresso: {tot_in_entropia/1e3:.0f} kbit "
          f"({tot_campioni/1e6:.0f} M campioni, modo '{a.modo}')")
    print(f"Bit in uscita: {bit_tot} ({bit_tot/8/1024:.1f} KiB)  "
          f"-> rendimento {bit_tot/tot_campioni/8*100:.3f}% dei bit grezzi")
    print(f"Bit usati: {bit_tot/ max(tot_in_entropia,1e-9)*100:.0f}% dell'entropia stimata "
          f"(con margine {a.margine}: atteso circa {100/a.margine:.0f}%)")

    out_f = cart / f"{a.prefisso}_cond_{a.modo}.bin"
    out_f.write_bytes(bytes(out_bits))
    log = {"prefisso": a.prefisso, "modo": a.modo, "margine": a.margine,
           "video": meta.get("video"), "sha256_video": meta.get("sha256_video"),
           "blocchi": righe, "bit_totali": bit_tot,
           "entropia_totale_stimata_bit": tot_in_entropia,
           "sha256_output": hashlib.sha256(bytes(out_bits)).hexdigest()}
    (cart / f"{a.prefisso}_cond_{a.modo}_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"Scritti: {out_f.name} e {a.prefisso}_cond_{a.modo}_log.json")


if __name__ == "__main__":
    main()
