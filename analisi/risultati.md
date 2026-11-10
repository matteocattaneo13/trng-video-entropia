## Statistiche per sorgente e ordinamento (bit per campione da 8 bit)

| Sorgente         | Ordinamento   |   n blocchi |    min |     Q1 |   mediana | IC95% mediana    |     Q3 |    max |   media |
|:-----------------|:--------------|------------:|-------:|-------:|----------:|:-----------------|-------:|-------:|--------:|
| Camino           | spazio        |          30 | 0.1625 | 0.3227 |    0.3707 | [0.3411, 0.3908] | 0.4122 | 0.4856 |  0.3585 |
| Camino           | tempo         |          30 | 0.0089 | 0.0211 |    0.0308 | [0.0223, 0.0484] | 0.0593 | 0.1719 |  0.0512 |
| Camino           | min2          |          30 | 0.0089 | 0.0211 |    0.0308 | [0.0223, 0.0484] | 0.0593 | 0.1719 |  0.0512 |
| Pioggia          | spazio        |          30 | 0.1208 | 0.2954 |    0.3493 | [0.3190, 0.4061] | 0.4780 | 0.7738 |  0.3894 |
| Pioggia          | tempo         |          30 | 0.0031 | 0.0075 |    0.0098 | [0.0078, 0.0107] | 0.0120 | 0.0320 |  0.0113 |
| Pioggia          | min2          |          30 | 0.0031 | 0.0075 |    0.0098 | [0.0078, 0.0107] | 0.0120 | 0.0320 |  0.0113 |
| Lava lamp        | spazio        |          30 | 0.0008 | 0.0161 |    0.0198 | [0.0175, 0.0208] | 0.0213 | 0.0294 |  0.0185 |
| Lava lamp        | tempo         |          30 | 0.0011 | 0.0102 |    0.0133 | [0.0110, 0.0167] | 0.0193 | 0.0302 |  0.0145 |
| Lava lamp        | min2          |          30 | 0.0008 | 0.0102 |    0.0126 | [0.0110, 0.0161] | 0.0168 | 0.0222 |  0.0130 |
| Traffico (notte) | spazio        |          30 | 0.0059 | 0.0105 |    0.0138 | [0.0120, 0.0152] | 0.0174 | 0.0210 |  0.0137 |
| Traffico (notte) | tempo         |          30 | 0.0057 | 0.0120 |    0.0146 | [0.0124, 0.0167] | 0.0173 | 0.0235 |  0.0145 |
| Traffico (notte) | min2          |          30 | 0.0057 | 0.0092 |    0.0120 | [0.0101, 0.0129] | 0.0143 | 0.0202 |  0.0120 |


## Confronto tra sorgenti (Kruskal-Wallis, 30 blocchi per sorgente)

| Ordinamento   |    H |        p |
|:--------------|-----:|---------:|
| spazio        | 92.7 | 5.84e-20 |
| tempo         | 49.4 | 1.06e-10 |
| min2          | 50.5 | 6.36e-11 |


Mann-Whitney a coppie (p con correzione di Holm; delta = probabilita' che un blocco della prima sorgente superi uno della seconda, 0.5 = nessuna differenza):

| Ordinamento   | A         | B                |   P(A>B) |   p (Holm) |
|:--------------|:----------|:-----------------|---------:|-----------:|
| spazio        | Camino    | Pioggia          |    0.501 |   0.994    |
| spazio        | Camino    | Lava lamp        |    1     |   1.81e-10 |
| spazio        | Camino    | Traffico (notte) |    1     |   1.81e-10 |
| spazio        | Pioggia   | Lava lamp        |    1     |   1.81e-10 |
| spazio        | Pioggia   | Traffico (notte) |    1     |   1.81e-10 |
| spazio        | Lava lamp | Traffico (notte) |    0.777 |   0.000478 |
| tempo         | Camino    | Pioggia          |    0.917 |   1.56e-07 |
| tempo         | Camino    | Lava lamp        |    0.872 |   3.04e-06 |
| tempo         | Camino    | Traffico (notte) |    0.919 |   1.56e-07 |
| tempo         | Pioggia   | Lava lamp        |    0.323 |   0.0382   |
| tempo         | Pioggia   | Traffico (notte) |    0.268 |   0.00616  |
| tempo         | Lava lamp | Traffico (notte) |    0.479 |   0.784    |
| min2          | Camino    | Pioggia          |    0.917 |   1.54e-07 |
| min2          | Camino    | Lava lamp        |    0.911 |   1.87e-07 |
| min2          | Camino    | Traffico (notte) |    0.939 |   3.28e-08 |
| min2          | Pioggia   | Lava lamp        |    0.359 |   0.184    |
| min2          | Pioggia   | Traffico (notte) |    0.376 |   0.199    |
| min2          | Lava lamp | Traffico (notte) |    0.58  |   0.29     |


## Andamento nel tempo (Spearman tra indice del blocco e entropia)

| Sorgente         | Ordinamento   |     rho |        p |
|:-----------------|:--------------|--------:|---------:|
| Camino           | spazio        | -0.221  | 0.241    |
| Camino           | tempo         | -0.196  | 0.299    |
| Pioggia          | spazio        | -0.675  | 4.25e-05 |
| Pioggia          | tempo         | -0.758  | 1.23e-06 |
| Lava lamp        | spazio        |  0.0154 | 0.936    |
| Lava lamp        | tempo         |  0.0808 | 0.671    |
| Traffico (notte) | spazio        | -0.248  | 0.186    |
| Traffico (notte) | tempo         | -0.437  | 0.0158   |


## Stimatore che determina il minimo (numero di blocchi su 30)

|                           |   LRS |   T-Tuple |
|:--------------------------|------:|----------:|
| Camino / spazio           |     0 |        30 |
| Camino / tempo            |     7 |        23 |
| Pioggia / spazio          |     0 |        30 |
| Pioggia / tempo           |     0 |        30 |
| Lava lamp / spazio        |     0 |        30 |
| Lava lamp / tempo         |     0 |        30 |
| Traffico (notte) / spazio |     0 |        30 |
| Traffico (notte) / tempo  |     0 |        30 |


## Solo frequenza (MCV) contro stima finale (mediana sui blocchi)

| sorgente         | ord    |   MCV |   finale |   rapporto MCV/finale |
|:-----------------|:-------|------:|---------:|----------------------:|
| Camino           | spazio | 1.501 |    0.371 |                 4.050 |
| Camino           | tempo  | 1.502 |    0.031 |                48.714 |
| Lava lamp        | spazio | 0.081 |    0.020 |                 4.096 |
| Lava lamp        | tempo  | 0.081 |    0.013 |                 6.096 |
| Pioggia          | spazio | 0.538 |    0.349 |                 1.541 |
| Pioggia          | tempo  | 0.539 |    0.010 |                54.773 |
| Traffico (notte) | spazio | 0.084 |    0.014 |                 6.063 |
| Traffico (notte) | tempo  | 0.084 |    0.015 |                 5.757 |


## Camino: blocchi che contengono l'aggiunta di legna vs gli altri

| Ordinamento   |   n con mano |   mediana con |   n senza |   mediana senza |      p |
|:--------------|-------------:|--------------:|----------:|----------------:|-------:|
| spazio        |            4 |       0.3588  |        26 |         0.3707  | 0.7022 |
| tempo         |            4 |       0.03565 |        26 |         0.03084 | 0.7912 |
| min2          |            4 |       0.03565 |        26 |         0.03084 | 0.7912 |