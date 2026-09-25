# Hash Code 2017
Solveur de placement de vidéos en cache (qualification Hash Code 2017).

## Fichiers

- `main.py` — solveur (greedy à gain marginal, fast-fill)
- `score.py` — score officiel
- `generate_instances.py` — 8 instances de test:
tiny_sanity → petit cas pour vérifier le fonctionnement et calculer le score à la main.
no_cache → aucun cache connecté → vérifier que le score est bien 0.
isolated_caches → chaque endpoint voit un seul cache → tester un cas simple et indépendant.
trending_mini → tous les caches sont accessibles + vidéos avec popularité différente → tester les vidéos populaires.
small_mixed → connexions et latences variées → tester un cas mixte plus réaliste.
skewed_popular → quelques vidéos sont extrêmement demandées → tester si l'algorithme gère bien une forte popularité.
medium → instance plus grande → tester l'algorithme sur une taille moyenne.
large_fastfill → très grande instance → tester la performance et la branche _solve_large.
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
