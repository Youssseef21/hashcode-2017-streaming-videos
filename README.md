# Hash Code 2017 — Streaming Videos

Solveur de placement de vidéos en cache (qualification Hash Code 2017).

## Fichiers

- `main.py` — solveur (greedy à gain marginal, knapsack, fast-fill)
- `score.py` — score officiel
- `generate_instances.py` — 8 instances de test
- `compte_rendu.pdf` — rapport : fonctionnement de l’algo et instances générées
- `me_at_the_zoo.in` — petite instance officielle
- `generated/*.in` — instances synthétiques (graine `20260913`)

## Utilisation

```bash
python main.py me_at_the_zoo.in me_at_the_zoo.out
python score.py me_at_the_zoo.in me_at_the_zoo.out
python main.py --all
python generate_instances.py --run
```

Sans argument, `main.py` lit stdin et écrit la solution sur stdout (mode juge).
