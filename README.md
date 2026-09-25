# Hash Code 2017 — Streaming Videos

Solveur du problème **Streaming Videos** de la Google Hash Code 2017, avec génération d'instances synthétiques pour tester l'algorithme sur différents scénarios.

## Fichiers

* `main.py` — solveur principal basé sur une stratégie **greedy à gain marginal**, avec une stratégie **fast-fill** pour les grandes instances.
* `score.py` — calcul du score selon les règles officielles de Hash Code 2017.
* `generate_instances.py` — générateur de **8 instances synthétiques**, chacune ciblant un scénario de test différent :

  * `tiny_sanity` — petite instance permettant de vérifier facilement le fonctionnement et le score à la main.
  * `no_cache` — aucun cache connecté, le score attendu est donc `0`.
  * `isolated_caches` — chaque endpoint est connecté à un seul cache, pour tester un cas simple et indépendant.
  * `trending_mini` — tous les caches sont accessibles, avec des vidéos de popularités différentes.
  * `small_mixed` — connexions, latences et requêtes variées pour simuler un cas plus réaliste.
  * `skewed_popular` — quelques vidéos sont fortement demandées afin de tester la gestion des vidéos populaires.
  * `medium` — instance de taille moyenne pour tester le comportement du solveur à plus grande échelle.
  * `large_fastfill` — grande instance conçue pour tester les performances et déclencher la stratégie `_solve_large`.
* `me_at_the_zoo.in` — petite instance officielle de qualification.
* `generated/*.in` — instances synthétiques générées avec une seed fixe (`20260913`).

## Utilisation

### Résoudre une instance

```bash
python main.py me_at_the_zoo.in me_at_the_zoo.out
```

### Calculer le score

```bash
python score.py me_at_the_zoo.in me_at_the_zoo.out
```

### Résoudre toutes les instances

```bash
python main.py --all
```

### Générer et tester les instances synthétiques

```bash
python generate_instances.py --run
```

### Mode juge

Sans arguments, `main.py` lit l'entrée depuis `stdin` et écrit la solution sur `stdout`.


