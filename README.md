# Hash Code 2017 — Streaming Videos

Solveur de placement de vidéos en cache (qualification Google Hash Code 2017), plus un dashboard pour voir une instance, le greedy, et le score.

Idée du score : on gagne du temps si la vidéo est dans un cache **plus proche** que le datacenter. **Seul le cache le plus rapide compte.**

## Algorithme

Greedy paresseux par **densité** `gain_marginal / taille` (tas / heap) :

1. Lire l’instance
2. Fusionner les demandes identiques `(vidéo, endpoint)`
3. Classer les couples `(vidéo, cache)` par densité
4. Prendre le meilleur, **retester** le gain : OUI on pose, NON on remet dans le tas

`MAX_CANDIDATES` dans `main.py` peut limiter le tas au départ (`None` = tout garder).

## Fichiers

| Fichier | Rôle |
|---------|------|
| `main.py` | Solveur (greedy + traces terminal) |
| `judge.py` | Score officiel à partir d’un `.in` et d’un `.out` |
| `dashboard.py` + `web/` | Page web : dataset, remplissage, score |
| `instance_stats.py` | Stats (Zipf, Gini, connectivité) |
| `generated/` | Instances de test |
| `web_cache/` | Cache du dashboard (ignoré par git) |

## Utilisation

### Résoudre

```bash
python main.py generated/me_at_the_zoo.in zoo.out
```

Sans arguments : stdin → stdout (mode juge).

```bash
python main.py --all
```

### Scorer une solution

```bash
python judge.py generated/me_at_the_zoo.in zoo.out
```

### Dashboard

```bash
python dashboard.py
```

Ouvrir [http://127.0.0.1:8765](http://127.0.0.1:8765)

Cliquer un dataset, puis **Lancer le greedy**. Les gros fichiers sont lents la première fois.

Dépendances : Python 3, `numpy`.

### Stats en terminal

```bash
python instance_stats.py generated/tiny_sanity.in
```

## Instances `generated/`

| Fichier | Intérêt |
|---------|---------|
| `tiny_sanity.in` | Score vérifiable à la main |
| `no_cache.in` | Aucun lien cache, score 0 |
| `isolated_caches.in` | Un cache par endpoint |
| `trending_mini.in` | Tous les caches, même latence |
| `small_mixed.in` | Style zoo |
| `skewed_popular.in` | Peu de vidéos portent presque tout le trafic |
| `medium.in` | Taille moyenne |
| `me_at_the_zoo.in` | Petite instance officielle |

Ajouter un `.in` dans `generated/` le fait apparaître dans le dashboard (sauf les très gros fichiers exclus dans `dashboard.py`).
