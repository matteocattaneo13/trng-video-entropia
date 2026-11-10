# TRNG da sorgenti video caotiche ambientali

Codice e risultati della tesi triennale *Progettazione e analisi statistica di un True Random Number Generator (TRNG) basato su sorgenti video caotiche ambientali* — Matteo Cattaneo, Università degli Studi di Milano, corso di laurea in Sicurezza dei Sistemi e delle Reti Informatiche (relatore: Prof. Stelvio Cimato), A.A. 2025/2026.

La tesi stima con la NIST SP 800-90B quanta min-entropia contengono quattro video di fenomeni caotici (camino, pioggia, lampada a lava, traffico notturno) e condiziona l'uscita con SHA-256, dimensionando la compressione sull'entropia misurata.

> **Avvertenza.** I video sono pubblici: chiunque li scarichi riproduce gli stessi bit. Il codice misura la variabilità delle scene e **non** va usato per generare chiavi o semi crittografici.

Repository: <https://github.com/matteocattaneo13/trng-video-entropia>

## Pipeline

| Passo | Script | Cosa fa |
|---|---|---|
| 1 | `step1_verifica_video.py`, `step1b_cerca_loop.py` | qualificazione dei video: tagli, accelerazioni, loop |
| 2 | `step2_estrai_grezzo.py` | campioni grezzi a 8 bit, `(G_t − G_{t−1}) mod 256` su una griglia di 880 punti, 30 blocchi da 1.000.000 di campioni, ordinamenti *spazio* e *tempo* |
| 3 | `ea_non_iid` (NIST) | stima della min-entropia, percorso non-IID: `ea_non_iid -v <blocco>.bin 8` |
| 4 | `step4_condiziona.py` | condizionamento SHA-256 con margine 2:1 |
| 5 | `step5_analisi.py` | statistiche (Kruskal-Wallis, Mann-Whitney con Holm, Spearman, bootstrap) e figure |
| 6 | `step6_diagnosi_serie_ferme.py` | diagnosi del calo in ordine *tempo*: fotogrammi ripetuti, serie ferme, controprova senza i punti fermi |

`figura_metodo.py` produce la figura della griglia del capitolo Metodo.

Lo strumento NIST si scarica e compila da <https://github.com/usnistgov/SP800-90B_EntropyAssessment> (`cd cpp && make non_iid`).

## Video

I video non sono inclusi nel repository. Si scaricano da YouTube e si ritagliano come descritto nell'Appendice A della tesi; le impronte SHA-256 dei file analizzati sono nei file `metadati/*_full_meta.json` (campo `sha256_video`).

| Sorgente | Video |
|---|---|
| Camino | https://www.youtube.com/watch?v=RjKX0DCbqfk |
| Pioggia | https://www.youtube.com/watch?v=Yj1wuyT1VS0 |
| Lava lamp | https://www.youtube.com/watch?v=h_lQ2tMgLVM |
| Traffico (notte) | https://www.youtube.com/watch?v=pZ5V0V_G2Po |

## Contenuto

- `analisi/`: tabelle CSV dei risultati (stime per blocco, statistiche, stimatore limitante, effetto della mano, diagnosi delle serie ferme) e figure;
- `risultati_90B.zip`: uscita completa di `ea_non_iid` per i 240 file (4 sorgenti × 30 blocchi × 2 ordinamenti), compressa in un unico archivio;
- `metadati/`: parametri di estrazione, istanti dei blocchi, SHA-256 dei video e log del condizionamento;
- `controlli/`: esiti della qualificazione dei due video scartati (traffico accelerato, pioggia in loop).

## Requisiti

Python 3 con `numpy`, `pandas`, `scipy`, `matplotlib`, `opencv-python`; `ffmpeg` per i ritagli.
