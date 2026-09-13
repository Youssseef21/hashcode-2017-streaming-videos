"""
Genere des fichiers .in au format Hash Code 2017 (Streaming Videos)
pour tester main.py / score.py.

Usage :
    python generate_instances.py
    python generate_instances.py --run
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from main import read_input, solve, write_output
from score import calculate_score


OUT_DIR = Path(__file__).resolve().parent / "generated"


def write_instance(path: Path, V, E, R, C, X, sizes, endpoints, requests):
    lines = [f"{V} {E} {R} {C} {X}", " ".join(map(str, sizes))]
    for dc, caches in endpoints:
        lines.append(f"{dc} {len(caches)}")
        for cache_id, latency in caches:
            lines.append(f"{cache_id} {latency}")
    for video_id, endpoint_id, count in requests:
        lines.append(f"{video_id} {endpoint_id} {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def pick_caches(rng: random.Random, C: int, k: int):
    k = min(k, C)
    chosen = rng.sample(range(C), k)
    return chosen


def make_sizes(rng, V, lo, hi):
    return [rng.randint(lo, hi) for _ in range(V)]


def zipf_choice(rng, n, skew=1.3):
    weights = [1.0 / ((i + 1) ** skew) for i in range(n)]
    return rng.choices(range(n), weights=weights, k=1)[0]


def build_tiny(rng):
    """Minuscule : on peut verifier le score a la main."""
    V, E, R, C, X = 6, 3, 8, 2, 40
    sizes = [10, 25, 15, 8, 30, 12]
    endpoints = [
        (800, [(0, 100), (1, 250)]),
        (500, [(0, 80)]),
        (900, [(1, 120)]),
    ]
    requests = [
        (0, 0, 50),
        (1, 0, 20),
        (2, 1, 40),
        (0, 1, 10),
        (3, 2, 30),
        (4, 2, 5),
        (5, 0, 15),
        (1, 2, 8),
    ]
    return V, E, R, C, X, sizes, endpoints, requests


def build_no_cache(rng):
    """Aucun cache connecte : le score doit etre 0."""
    V, E, R, C, X = 10, 4, 20, 3, 100
    sizes = make_sizes(rng, V, 5, 40)
    endpoints = [(rng.randint(200, 900), []) for _ in range(E)]
    requests = [
        (rng.randrange(V), rng.randrange(E), rng.randint(1, 80))
        for _ in range(R)
    ]
    return V, E, R, C, X, sizes, endpoints, requests


def build_isolated(rng):
    """Chaque endpoint ne voit qu'un seul cache (pas de recouvrement)."""
    V, E, R, C, X = 40, 8, 120, 8, 80
    sizes = make_sizes(rng, V, 3, 25)
    endpoints = []
    for e in range(E):
        cache_id = e % C
        dc = rng.randint(400, 1200)
        lat = rng.randint(20, 80)
        endpoints.append((dc, [(cache_id, lat)]))
    requests = [
        (zipf_choice(rng, V), rng.randrange(E), rng.randint(1, 200))
        for _ in range(R)
    ]
    return V, E, R, C, X, sizes, endpoints, requests


def build_trending_mini(rng):
    """Comme trending_today : tous les caches, meme latence."""
    V, E, R, C, X = 80, 8, 400, 6, 200
    sizes = make_sizes(rng, V, 10, 80)
    endpoints = []
    for _ in range(E):
        dc = rng.randint(500, 800)
        caches = [(c, 100) for c in range(C)]
        endpoints.append((dc, caches))
    requests = [
        (zipf_choice(rng, V, 1.6), rng.randrange(E), rng.randint(1, 300))
        for _ in range(R)
    ]
    return V, E, R, C, X, sizes, endpoints, requests


def build_small_mixed(rng):
    """Petite instance mixte, style zoo."""
    V, E, R, C, X = 60, 12, 180, 8, 120
    sizes = make_sizes(rng, V, 1, 50)
    endpoints = []
    for _ in range(E):
        dc = rng.randint(200, 1500)
        k = rng.randint(1, min(5, C))
        caches = []
        for cache_id in pick_caches(rng, C, k):
            lat = rng.randint(10, max(11, dc - 50))
            caches.append((cache_id, lat))
        endpoints.append((dc, caches))
    requests = [
        (zipf_choice(rng, V), rng.randrange(E), rng.randint(1, 150))
        for _ in range(R)
    ]
    return V, E, R, C, X, sizes, endpoints, requests


def build_skewed(rng):
    """Quelques videos tres demandees, beaucoup ignorees."""
    V, E, R, C, X = 120, 20, 600, 12, 250
    sizes = make_sizes(rng, V, 5, 90)
    endpoints = []
    for _ in range(E):
        dc = rng.randint(300, 1000)
        k = rng.randint(2, min(7, C))
        caches = [
            (cid, rng.randint(15, 180))
            for cid in pick_caches(rng, C, k)
        ]
        endpoints.append((dc, caches))
    requests = [
        (zipf_choice(rng, V, 2.1), rng.randrange(E), rng.randint(10, 500))
        for _ in range(R)
    ]
    return V, E, R, C, X, sizes, endpoints, requests


def build_medium(rng):
    """Moyenne : greedy global, encore rapide."""
    V, E, R, C, X = 400, 35, 4000, 20, 800
    sizes = make_sizes(rng, V, 8, 120)
    endpoints = []
    for _ in range(E):
        dc = rng.randint(250, 1100)
        k = rng.randint(2, 8)
        caches = [
            (cid, rng.randint(20, 220))
            for cid in pick_caches(rng, C, k)
        ]
        endpoints.append((dc, caches))
    requests = [
        (zipf_choice(rng, V, 1.2), rng.randrange(E), rng.randint(1, 250))
        for _ in range(R)
    ]
    return V, E, R, C, X, sizes, endpoints, requests


def build_large_fastfill(rng):
    """Assez grand pour declencher _solve_large (expansion > 8e6)."""
    V, E, R, C, X = 800, 60, 90000, 45, 1500
    sizes = make_sizes(rng, V, 10, 180)
    endpoints = []
    for _ in range(E):
        dc = rng.randint(400, 900)
        k = C
        caches = [(cid, rng.randint(40, 200)) for cid in range(k)]
        endpoints.append((dc, caches))
    requests = [
        (zipf_choice(rng, V, 1.4), rng.randrange(E), rng.randint(1, 200))
        for _ in range(R)
    ]
    return V, E, R, C, X, sizes, endpoints, requests


PRESETS = [
    ("tiny_sanity", build_tiny, 1),
    ("no_cache", build_no_cache, 2),
    ("isolated_caches", build_isolated, 3),
    ("trending_mini", build_trending_mini, 4),
    ("small_mixed", build_small_mixed, 5),
    ("skewed_popular", build_skewed, 6),
    ("medium", build_medium, 7),
    ("large_fastfill", build_large_fastfill, 8),
]


def generate_all(seed: int = 20260913):
    OUT_DIR.mkdir(exist_ok=True)
    created = []
    for name, builder, local_seed in PRESETS:
        rng = random.Random(seed + local_seed)
        data = builder(rng)
        path = OUT_DIR / f"{name}.in"
        write_instance(path, *data)
        created.append(path)
        V, E, R, C, X = data[:5]
        print(f"  {path.name:22}  V={V:<5} E={E:<4} R={R:<6} C={C:<4} X={X}")
    return created


def run_all(paths):
    print("\n=== scores ===")
    for path in paths:
        out = path.with_suffix(".out")
        V, E, R, C, X, sizes, endpoints, requests = read_input(str(path))
        caches = solve(C, X, sizes, endpoints, requests, verbose=False)
        write_output(str(out), caches)
        score = calculate_score(endpoints, requests, caches)
        print(f"  {path.stem:22}  score = {score:,}".replace(",", " "))


def main():
    parser = argparse.ArgumentParser(description="Generateur d'instances de test")
    parser.add_argument("--run", action="store_true", help="resoudre et scorer chaque instance")
    parser.add_argument("--seed", type=int, default=20260913)
    args = parser.parse_args()

    print(f"Dossier : {OUT_DIR}")
    paths = generate_all(args.seed)
    print(f"{len(paths)} instances creees.")
    if args.run:
        run_all(paths)


if __name__ == "__main__":
    main()
