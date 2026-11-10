#!/usr/bin/env python3
"""
STEP 5 - Analisi statistica delle stime di min-entropia (SP 800-90B)
====================================================================
Legge i file risultati_90B/<sorgente>_full_b<N>_{spazio,tempo}.txt (output di `ea_non_iid -v`)
e produce:
  - tabelle (CSV + Markdown): statistiche per sorgente e ordinamento, intervalli di confidenza
    bootstrap sulla mediana, stimatore limitante, confronto tra sorgenti
  - test non parametrici: Kruskal-Wallis tra sorgenti, Mann-Whitney a coppie (correzione di Holm),
    correlazione di Spearman con il tempo (non stazionarieta')
  - figure PNG
Uso:
  python step5_analisi.py --risultati risultati_90B --out analisi
  python step5_analisi.py --risultati risultati_90B --out analisi --meta-camino fireplace_full_meta.json
"""
import argparse
import itertools
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

SORGENTI = ["fireplace", "rain", "lava", "traffic"]
NOMI = {"fireplace": "Camino", "rain": "Pioggia", "lava": "Lava lamp", "traffic": "Traffico (notte)"}
COL = {"spazio": "#2a78d6", "tempo": "#eb6834"}      # blu / arancione (validati insieme)
RE_FILE = re.compile(r"^(fireplace|rain|lava|traffic)_full_b(\d+)_(spazio|tempo)\.txt$")
RE_EST = re.compile(r"^\t(.+?) = ([0-9.]+) / (\d) bit\(s\)", re.M)
RE_MIN = re.compile(r"^min\(H_original, 8 X H_bitstring\):\s*([0-9.]+)", re.M)


def famiglia(nome):
    n = nome.replace(" Test Estimate", "").replace(" (bit string)", "").strip()
    n = n.replace("Most Common Value Estimate", "MCV")
    n = re.sub(r"Multi Most Common in Window \(MultiMCW\) Prediction", "MultiMCW", n)
    n = re.sub(r"Multi Markov Model with Counting \(MultiMMC\) Prediction", "MultiMMC", n)
    n = n.replace(" Prediction", "").replace("Estimate", "").strip()
    return n


def leggi(path):
    t = path.read_text(errors="replace")
    m = RE_MIN.search(t)
    if not m:
        return None
    ests = []
    for nome, v, bits in RE_EST.findall(t):
        v = float(v)
        scal = v if bits == "8" else v * 8          # tutto in bit per campione da 8 bit
        ests.append((famiglia(nome), "bit" if bits == "1" else "8bit", scal))
    lim = min(ests, key=lambda x: x[2])
    mcv = [e[2] for e in ests if e[0] == "MCV" and e[1] == "8bit"]
    return {"H": float(m.group(1)), "limitante": lim[0], "limitante_tipo": lim[1],
            "H_mcv": mcv[0] if mcv else np.nan}


def holm(p):
    p = np.asarray(p)
    o = np.argsort(p)
    out = np.empty_like(p)
    run = 0.0
    for r, i in enumerate(o):
        run = max(run, (len(p) - r) * p[i])
        out[i] = min(1.0, run)
    return out


def boot_ci(x, f=np.median, n=10000, seed=1):
    rng = np.random.default_rng(seed)
    x = np.asarray(x)
    b = f(rng.choice(x, (n, len(x))), axis=1)
    return np.percentile(b, [2.5, 97.5])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--risultati", default="risultati_90B")
    ap.add_argument("--out", default="analisi")
    ap.add_argument("--meta-camino", default=None, help="fireplace_full_meta.json (per mani si/no)")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)

    righe = []
    for p in sorted(Path(a.risultati).glob("*_full_b*_*.txt")):
        m = RE_FILE.match(p.name)
        if not m:
            continue
        r = leggi(p)
        if r:
            righe.append({"sorgente": m.group(1), "blocco": int(m.group(2)), "ord": m.group(3), **r})
    df = pd.DataFrame(righe)
    if df.empty:
        raise SystemExit("Nessun file *_full_* trovato")
    w = df.pivot_table(index=["sorgente", "blocco"], columns="ord", values="H").reset_index()
    w["min2"] = w[["spazio", "tempo"]].min(axis=1)
    w.to_csv(out / "entropia_per_blocco.csv", index=False)
    md = []

    # --- 1. statistiche descrittive + IC bootstrap sulla mediana
    tab = []
    for s in SORGENTI:
        for o in ["spazio", "tempo", "min2"]:
            x = w.loc[w.sorgente == s, o].to_numpy()
            lo, hi = boot_ci(x)
            tab.append({"Sorgente": NOMI[s], "Ordinamento": o, "n blocchi": len(x),
                        "min": x.min(), "Q1": np.percentile(x, 25), "mediana": np.median(x),
                        "IC95% mediana": f"[{lo:.4f}, {hi:.4f}]", "Q3": np.percentile(x, 75),
                        "max": x.max(), "media": x.mean()})
    T1 = pd.DataFrame(tab)
    T1.to_csv(out / "tabella_statistiche.csv", index=False)
    md.append("## Statistiche per sorgente e ordinamento (bit per campione da 8 bit)\n")
    md.append(T1.to_markdown(index=False, floatfmt=".4f"))

    # --- 2. confronto tra sorgenti
    md.append("\n\n## Confronto tra sorgenti (Kruskal-Wallis, 30 blocchi per sorgente)\n")
    kw = []
    for o in ["spazio", "tempo", "min2"]:
        g = [w.loc[w.sorgente == s, o].to_numpy() for s in SORGENTI]
        H, p = stats.kruskal(*g)
        kw.append({"Ordinamento": o, "H": H, "p": p})
    md.append(pd.DataFrame(kw).to_markdown(index=False, floatfmt=".3g"))
    md.append("\n\nMann-Whitney a coppie (p con correzione di Holm; delta = probabilita' che un blocco "
              "della prima sorgente superi uno della seconda, 0.5 = nessuna differenza):\n")
    mw = []
    for o in ["spazio", "tempo", "min2"]:
        coppie = list(itertools.combinations(SORGENTI, 2))
        ps, rows = [], []
        for s1, s2 in coppie:
            x1 = w.loc[w.sorgente == s1, o].to_numpy()
            x2 = w.loc[w.sorgente == s2, o].to_numpy()
            U, p = stats.mannwhitneyu(x1, x2, alternative="two-sided")
            ps.append(p)
            rows.append({"Ordinamento": o, "A": NOMI[s1], "B": NOMI[s2], "P(A>B)": U / (len(x1) * len(x2))})
        for r, ph in zip(rows, holm(ps)):
            r["p (Holm)"] = ph
            mw.append(r)
    md.append(pd.DataFrame(mw).to_markdown(index=False, floatfmt=".3g"))

    # --- 3. non stazionarieta': correlazione con l'indice del blocco (= tempo)
    md.append("\n\n## Andamento nel tempo (Spearman tra indice del blocco e entropia)\n")
    sp = []
    for s in SORGENTI:
        for o in ["spazio", "tempo"]:
            d = w[w.sorgente == s].sort_values("blocco")
            rho, p = stats.spearmanr(d.blocco, d[o])
            sp.append({"Sorgente": NOMI[s], "Ordinamento": o, "rho": rho, "p": p})
    md.append(pd.DataFrame(sp).to_markdown(index=False, floatfmt=".3g"))

    # --- 4. stimatore limitante
    md.append("\n\n## Stimatore che determina il minimo (numero di blocchi su 30)\n")
    lim = df.groupby(["sorgente", "ord", "limitante"]).size().reset_index(name="n")
    pv = lim.pivot_table(index=["sorgente", "ord"], columns="limitante", values="n", fill_value=0).astype(int)
    pv = pv.reindex([(s, o) for s in SORGENTI for o in ["spazio", "tempo"]])
    pv.index = [f"{NOMI[s]} / {o}" for s, o in pv.index]
    md.append(pv.to_markdown())
    pv.to_csv(out / "stimatore_limitante.csv")

    # --- 5. istogramma vs dipendenza: MCV (solo frequenza) contro min finale
    md.append("\n\n## Solo frequenza (MCV) contro stima finale (mediana sui blocchi)\n")
    g = df.groupby(["sorgente", "ord"]).agg(MCV=("H_mcv", "median"), finale=("H", "median")).reset_index()
    g["rapporto MCV/finale"] = g.MCV / g.finale
    g["sorgente"] = g.sorgente.map(NOMI)
    md.append(g.to_markdown(index=False, floatfmt=".3f"))

    # --- 6. camino: blocchi con mani / senza mani
    mani = None
    if a.meta_camino and Path(a.meta_camino).exists():
        meta = json.loads(Path(a.meta_camino).read_text(encoding="utf-8"))
        fps = meta["fps"]
        dur = meta["frame_per_blocco"] / fps
        ev = [t for t in [16 * 60 + 35, 18 * 60 + 58, 19 * 60 + 3, 19 * 60 + 9, 22 * 60 + 2, 23 * 60 + 32,
                          31 * 60 + 23, 31 * 60 + 28, 34 * 60 + 28, 35 * 60 + 56]]
        starts = {b["blocco"]: b["secondo_iniziale"] for b in meta["blocchi"]}
        wf = w[w.sorgente == "fireplace"].copy()
        wf["inizio_s"] = wf.blocco.map(starts)
        wf["mano"] = [any(s <= t <= s + dur for t in ev) for s in wf.inizio_s]
        wf.to_csv(out / "camino_mani.csv", index=False)
        md.append("\n\n## Camino: blocchi che contengono l'aggiunta di legna vs gli altri\n")
        rr = []
        for o in ["spazio", "tempo", "min2"]:
            x1 = wf.loc[wf.mano, o]
            x0 = wf.loc[~wf.mano, o]
            p = stats.mannwhitneyu(x1, x0)[1] if len(x1) > 1 and len(x0) > 1 else np.nan
            rr.append({"Ordinamento": o, "n con mano": len(x1), "mediana con": x1.median(),
                       "n senza": len(x0), "mediana senza": x0.median(), "p": p})
        md.append(pd.DataFrame(rr).to_markdown(index=False, floatfmt=".4g"))
        mani = wf

    (out / "risultati.md").write_text("\n".join(md), encoding="utf-8")

    # ------------------ figure
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.6})
    # fig 1: entropia per blocco nel tempo, un pannello per sorgente
    fig, ax = plt.subplots(2, 2, figsize=(11, 6.5), sharey=True)
    for a_, s in zip(ax.ravel(), SORGENTI):
        d = w[w.sorgente == s].sort_values("blocco")
        for o, mk in (("spazio", "o"), ("tempo", "s")):
            a_.plot(d.blocco, d[o], marker=mk, ms=4, lw=1.4, color=COL[o], label=f"ordine {o}")
        a_.set_yscale("log")
        a_.set_title(NOMI[s], loc="left", fontsize=11)
        a_.set_xlabel("indice del blocco (ordine temporale)")
    for a_ in ax[:, 0]:
        a_.set_ylabel("min-entropia (bit/campione)")
    ax[0, 0].legend(frameon=False, loc="lower left")
    fig.suptitle("Min-entropia stimata (SP 800-90B) per blocco da 1.000.000 di campioni", x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(out / "fig1_entropia_per_blocco.png", dpi=160)
    plt.close(fig)

    # fig 2: distribuzione per sorgente e ordinamento
    fig, ax = plt.subplots(figsize=(9, 4.8))
    rng = np.random.default_rng(0)
    for i, s in enumerate(SORGENTI):
        for k, o in enumerate(["spazio", "tempo"]):
            x = w.loc[w.sorgente == s, o].to_numpy()
            pos = i + (-0.19 if k == 0 else 0.19)
            bp = ax.boxplot(x, positions=[pos], widths=0.3, showfliers=False, patch_artist=True,
                            medianprops=dict(color="black", lw=1.4))
            bp["boxes"][0].set(facecolor=COL[o], alpha=0.35, edgecolor=COL[o])
            for el in ("whiskers", "caps"):
                for l in bp[el]:
                    l.set(color=COL[o])
            ax.scatter(pos + rng.uniform(-0.07, 0.07, len(x)), x, s=10, color=COL[o],
                       edgecolor="white", linewidth=0.4, zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(range(4))
    ax.set_xticklabels([NOMI[s] for s in SORGENTI])
    ax.set_ylabel("min-entropia (bit/campione)")
    ax.set_title("Distribuzione sui 30 blocchi", loc="left")
    ax.plot([], [], "s", color=COL["spazio"], label="ordine spazio")
    ax.plot([], [], "s", color=COL["tempo"], label="ordine tempo")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(out / "fig2_confronto_sorgenti.png", dpi=160)
    plt.close(fig)

    # fig 3: solo frequenza (MCV) contro stima finale
    gg = df[df.ord == "spazio"].groupby("sorgente").agg(mcv=("H_mcv", "median"), fin=("H", "median"))
    gt = df[df.ord == "tempo"].groupby("sorgente").agg(fin=("H", "median"))
    fig, ax = plt.subplots(figsize=(8, 4.4))
    xs = np.arange(4)
    ax.bar(xs - 0.27, [gg.mcv[s] for s in SORGENTI], 0.26, color="#8d8c86", label="solo frequenza (MCV)")
    ax.bar(xs, [gg.fin[s] for s in SORGENTI], 0.26, color=COL["spazio"], label="stima finale, ordine spazio")
    ax.bar(xs + 0.27, [gt.fin[s] for s in SORGENTI], 0.26, color=COL["tempo"], label="stima finale, ordine tempo")
    ax.set_yscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([NOMI[s] for s in SORGENTI])
    ax.set_ylabel("bit/campione (mediana sui blocchi)")
    ax.set_title("Cosa perde chi guarda solo l'istogramma", loc="left")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "fig3_istogramma_vs_90B.png", dpi=160)
    plt.close(fig)
    print(f"Fatto. File in {out}/ : risultati.md, tabelle CSV, 3 figure PNG")


if __name__ == "__main__":
    main()
