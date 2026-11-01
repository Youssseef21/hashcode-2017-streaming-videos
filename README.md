# Hash Code 2017 — Streaming Videos

Solveur de placement de vidéos en cache (qualification Google Hash Code 2017).

**Score :** on gagne du temps si la vidéo est dans un cache plus proche que le datacenter. **Seul le cache le plus rapide compte.**

```text
score = (ms économisées × 1000) // nombre de requêtes
```

## Algorithme (`main.py`)

Pipeline :

1. **Lecture** de l’instance `.in`
2. **Greedy** par densité `gain_marginal / taille` (tas lazy)
3. **Cache-seq** (si utile) : remplir les caches un par un depuis vide, deux ordres, on garde le meilleur départ
4. **Sac à dos exact** cache par cache (1 seed) ; **PGCD** si les tailles sont commensurables, sinon DP scalable
5. **Recherche locale** : trous, promotion vers un cache plus rapide, échanges entre voisins (coup gardé seulement si le score monte)
6. **Écriture** du `.out`

Budget total : 570 s par défaut (`HC_TIME` pour le changer).

## Fichiers

| Fichier | Rôle |
|---------|------|
| `main.py` | Solveur |
| `judge.py` | Score officiel `.in` + `.out` |
| `dashboard.py` + `web/` | Interface : datasets, greedy, métriques |
| `instance_stats.py` | Stats utilisées par le dashboard |
| `generated/` | Instances d’exemple |

## Utilisation

Dépendances : Python 3, `numpy`.

### Résoudre

```bash
python main.py generated/me_at_the_zoo.in zoo.out
```

Sans arguments : stdin → stdout (mode juge).

Batch local (`_local/instance*.txt`) :

```bash
python main.py --local 90
```

### Scorer

```bash
python judge.py generated/me_at_the_zoo.in zoo.out
```

### Dashboard

```bash
python dashboard.py
```

Ouvrir [http://127.0.0.1:8765](http://127.0.0.1:8765)

Place un `.in` dans `generated/` pour l’afficher dans la liste.
