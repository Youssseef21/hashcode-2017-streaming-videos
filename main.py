"""
Hash Code 2017 -- Streaming Videos

Version :
    1. Lecture
    2. Agrégation des requêtes
    3. Greedy lazy par densité (solution de départ)
    4. Optimisation par sac à dos exact, cache par cache
       (coordinate ascent avec caches "sales")
    5. Écriture

Idée de la phase 4 :
    On fige tous les autres caches et on re-résout UN cache en entier
    sur toute sa capacité. Les gains deviennent indépendants entre eux,
    c'est donc un vrai sac à dos 0/1 exact. Le score ne peut jamais baisser.
"""

import heapq
import random
import sys
import time
from collections import defaultdict

import numpy as np


# ============================================================
# PARAMÈTRES
# ============================================================

MAX_CANDIDATES = None

# Limite de temps (secondes) pour la phase 4
OPT_TIME_LIMIT = 20.0

# Nombre max de vidéos considérées dans un sac à dos (None = toutes)
KNAPSACK_MAX_ITEMS = None


# ============================================================
# AFFICHAGE
# ============================================================

def _explain(verbose, message=""):
    if verbose:
        print(message, file=sys.stderr, flush=True)


def _phase(verbose, number, title):
    if not verbose:
        return
    print("", file=sys.stderr)
    print("=" * 62, file=sys.stderr)
    print(f"  PHASE {number}  --  {title}", file=sys.stderr)
    print("=" * 62, file=sys.stderr, flush=True)


def _print_regle(verbose):
    _phase(verbose, 0, "LA REGLE")
    _explain(verbose, "  Seul le cache LE PLUS RAPIDE qui contient la video compte.")
    _explain(
        verbose,
        "  Gain marginal = (meilleure latence actuelle - nouvelle latence)"
        " x nombre de requetes"
    )
    _explain(verbose, "  Greedy : meilleur gain / taille.")
    _explain(verbose, "  Ensuite : sac a dos exact par cache, les autres figes.")


# ============================================================
# PHASE 1 -- LECTURE
# ============================================================

def read_input(source):
    close = False

    if hasattr(source, "readline"):
        file = source
    else:
        file = open(source, "r", encoding="utf-8")
        close = True

    try:
        V, E, R, C, X = map(int, file.readline().split())

        video_sizes = list(map(int, file.readline().split()))

        endpoints = []

        for _ in range(E):
            datacenter_latency, number_of_caches = map(
                int, file.readline().split()
            )

            connected_caches = {}

            for _ in range(number_of_caches):
                cache_id, cache_latency = map(
                    int, file.readline().split()
                )
                connected_caches[cache_id] = cache_latency

            endpoints.append({
                "datacenter_latency": datacenter_latency,
                "caches": connected_caches
            })

        requests = []

        for _ in range(R):
            video_id, endpoint_id, number_of_requests = map(
                int, file.readline().split()
            )
            requests.append((video_id, endpoint_id, number_of_requests))

    finally:
        if close:
            file.close()

    return V, E, R, C, X, video_sizes, endpoints, requests


# ============================================================
# PHASE 2 -- AGRÉGATION DES REQUÊTES
# ============================================================

def _aggregate_requests(requests):
    counts = defaultdict(int)

    for video_id, endpoint_id, count in requests:
        counts[video_id, endpoint_id] += count

    video_reqs = defaultdict(list)

    for (video_id, endpoint_id), count in counts.items():
        video_reqs[video_id].append((endpoint_id, count))

    return counts, video_reqs


# ============================================================
# PHASE 3 -- GREEDY (solution de départ)
# ============================================================

def solve(C, capacity, video_sizes, endpoints, requests, verbose=False, trace=None):
    """Greedy incrémental avec lazy priority queue."""

    counts, video_reqs = _aggregate_requests(requests)

    _phase(verbose, 2, "ON FUSIONNE LES DEMANDES IDENTIQUES")
    _explain(
        verbose,
        f"  {len(requests)} lignes -> {len(counts)} demandes distinctes"
    )

    _phase(verbose, 3, "GREEDY : meilleur gain marginal / taille")

    current_best = {
        (video_id, endpoint_id): endpoints[endpoint_id]["datacenter_latency"]
        for video_id, endpoint_id in counts
    }

    remaining = [capacity] * C
    cache_videos = [set() for _ in range(C)]

    def apply_best_updates(cache_id, video_id):
        for endpoint_id, count in video_reqs.get(video_id, ()):
            latency = endpoints[endpoint_id]["caches"].get(cache_id)
            if latency is None:
                continue
            key = (video_id, endpoint_id)
            if latency < current_best[key]:
                current_best[key] = latency

    def place(cache_id, video_id):
        if video_id in cache_videos[cache_id]:
            return
        size = video_sizes[video_id]
        if size > remaining[cache_id]:
            return
        cache_videos[cache_id].add(video_id)
        remaining[cache_id] -= size
        apply_best_updates(cache_id, video_id)

    # Gains initiaux
    initial_benefit = defaultdict(int)

    for (video_id, endpoint_id), count in counts.items():
        endpoint = endpoints[endpoint_id]
        datacenter_latency = endpoint["datacenter_latency"]

        for cache_id, cache_latency in endpoint["caches"].items():
            saved = datacenter_latency - cache_latency
            if saved > 0:
                initial_benefit[cache_id, video_id] += saved * count

    # Heap
    heap = []

    for (cache_id, video_id), benefit in initial_benefit.items():
        size = video_sizes[video_id]
        if size <= 0 or size > capacity or benefit <= 0:
            continue
        heap.append((-benefit / size, cache_id, video_id, benefit))

    del initial_benefit

    if MAX_CANDIDATES is not None and len(heap) > MAX_CANDIDATES:
        _explain(
            verbose,
            f"  Filtre : {MAX_CANDIDATES} candidats sur {len(heap)}"
        )
        heap = heapq.nsmallest(MAX_CANDIDATES, heap)
    else:
        heapq.heapify(heap)

    _explain(verbose, f"  {len(heap)} candidats initiaux")

    def marginal_benefit(cache_id, video_id):
        if video_id in cache_videos[cache_id]:
            return 0
        if video_sizes[video_id] > remaining[cache_id]:
            return 0

        total = 0

        for endpoint_id, count in video_reqs.get(video_id, ()):
            latency = endpoints[endpoint_id]["caches"].get(cache_id)
            if latency is None:
                continue
            best = current_best[video_id, endpoint_id]
            if latency < best:
                total += (best - latency) * count

        return total

    placements = 0
    stale = 0

    while heap:
        _neg_density, cache_id, video_id, old_benefit = heapq.heappop(heap)

        if video_id in cache_videos[cache_id]:
            continue

        size = video_sizes[video_id]

        if size > remaining[cache_id]:
            continue

        benefit = marginal_benefit(cache_id, video_id)

        if benefit <= 0:
            continue

        if benefit != old_benefit:
            heapq.heappush(
                heap, (-benefit / size, cache_id, video_id, benefit)
            )
            stale += 1
            continue

        place(cache_id, video_id)
        placements += 1

        if trace is not None:
            trace.append((
                cache_id,
                video_id,
                size,
                remaining[cache_id],
                benefit,
                capacity - remaining[cache_id],
            ))

    _explain(verbose, f"  Greedy terminé : {placements} placements")
    _explain(verbose, f"  {stale} candidats recalculés")

    return cache_videos


# ============================================================
# PHASE 4 -- SAC À DOS EXACT, CACHE PAR CACHE
# ============================================================

def build_structures(C, endpoints, counts):
    """
    ep_reqs[e]         = [(video, nb_requetes)]
    cache_endpoints[c] = [(endpoint, latence)]
    neighbors[c]       = caches qui partagent au moins un endpoint avec c
    """
    ep_reqs = defaultdict(list)

    for (video_id, endpoint_id), count in counts.items():
        ep_reqs[endpoint_id].append((video_id, count))

    cache_endpoints = [[] for _ in range(C)]
    neighbors = [set() for _ in range(C)]

    for e, endpoint in enumerate(endpoints):
        if e not in ep_reqs:
            continue

        ids = list(endpoint["caches"])

        for c, lat in endpoint["caches"].items():
            cache_endpoints[c].append((e, lat))

        for a in ids:
            neighbors[a].update(ids)

    for c in range(C):
        neighbors[c].discard(c)

    return ep_reqs, cache_endpoints, neighbors


def compute_gain(c, endpoints, cache_endpoints, ep_reqs, cache_videos):
    """
    Gain de chaque video v si on la met dans le cache c,
    en ignorant totalement le contenu actuel de c.
    """
    gain = defaultdict(int)

    for e, lat in cache_endpoints[c]:
        endpoint = endpoints[e]
        dc = endpoint["datacenter_latency"]
        other_caches = endpoint["caches"]

        for v, count in ep_reqs[e]:
            best = dc

            for c2, lat2 in other_caches.items():
                if c2 != c and lat2 < best and v in cache_videos[c2]:
                    best = lat2

            if lat < best:
                gain[v] += (best - lat) * count

    return gain


def fractional_bound(items, capacity):
    """Borne sup. du sac à dos (relaxation fractionnaire)."""
    ordered = sorted(items, key=lambda t: t[1] / t[2], reverse=True)

    total = 0.0
    cap = capacity

    for _v, g, s in ordered:
        if s <= cap:
            total += g
            cap -= s
        else:
            total += g * cap / s
            break

    return total


def knapsack(items, capacity):
    """Sac à dos 0/1 exact (numpy). items = [(video, gain, size)]."""
    n = len(items)

    dp = np.zeros(capacity + 1, dtype=np.int64)
    keep = np.zeros((n, capacity + 1), dtype=bool)

    for i, (_v, g, s) in enumerate(items):
        new = dp[:capacity + 1 - s] + g
        better = new > dp[s:]
        keep[i, s:] = better
        dp[s:] = np.where(better, new, dp[s:])

    chosen = set()
    cap = capacity

    for i in range(n - 1, -1, -1):
        if keep[i, cap]:
            v, _g, s = items[i]
            chosen.add(v)
            cap -= s

    return chosen, int(dp[capacity])


def optimize_caches(
    cache_videos,
    C,
    capacity,
    video_sizes,
    endpoints,
    requests,
    time_limit=OPT_TIME_LIMIT,
    verbose=False
):
    _phase(verbose, 4, "SAC A DOS EXACT PAR CACHE (caches sales)")

    counts, _ = _aggregate_requests(requests)

    ep_reqs, cache_endpoints, neighbors = build_structures(
        C, endpoints, counts
    )

    deadline = time.time() + time_limit

    dirty = set(c for c in range(C) if cache_endpoints[c])

    solved = 0
    skipped_fit = 0
    skipped_bound = 0
    improved = 0
    rounds = 0

    while dirty and time.time() < deadline:
        rounds += 1
        batch = list(dirty)
        random.shuffle(batch)

        for c in batch:
            if time.time() >= deadline:
                break

            if c not in dirty:
                continue

            dirty.discard(c)

            gain = compute_gain(
                c, endpoints, cache_endpoints, ep_reqs, cache_videos
            )

            items = [
                (v, g, video_sizes[v])
                for v, g in gain.items()
                if g > 0 and 0 < video_sizes[v] <= capacity
            ]

            if not items:
                continue

            current = sum(gain.get(v, 0) for v in cache_videos[c])

            # Condition : tout rentre -> pas besoin de DP
            if sum(s for _, _, s in items) <= capacity:
                new_set = {v for v, _, _ in items}
                value = sum(g for _, g, _ in items)
                skipped_fit += 1

            else:
                # Condition : déjà optimal (borne fractionnaire)
                if fractional_bound(items, capacity) <= current:
                    skipped_bound += 1
                    continue

                if (
                    KNAPSACK_MAX_ITEMS is not None
                    and len(items) > KNAPSACK_MAX_ITEMS
                ):
                    items.sort(key=lambda t: t[1] / t[2], reverse=True)
                    items = items[:KNAPSACK_MAX_ITEMS]

                new_set, value = knapsack(items, capacity)
                solved += 1

            # Remplacement seulement si strictement meilleur
            if value > current:
                cache_videos[c] = new_set
                improved += 1
                dirty.update(neighbors[c])

    _explain(verbose, f"  {rounds} tours, {improved} caches ameliores")
    _explain(
        verbose,
        f"  {solved} sacs a dos resolus, "
        f"{skipped_fit} 'tout rentre', "
        f"{skipped_bound} sautes (deja optimaux)"
    )

    if dirty:
        _explain(verbose, f"  Temps ecoule : {len(dirty)} caches non revus")

    return cache_videos


# ============================================================
# PHASE 5 -- ÉCRITURE
# ============================================================

def write_output(dest, cache_videos, verbose=False):

    _phase(verbose, 5, "ON ECRIT LE RESULTAT")

    used_caches = [
        (cache_id, videos)
        for cache_id, videos in enumerate(cache_videos)
        if videos
    ]

    _explain(verbose, f"  {len(used_caches)} caches utilisés")

    close = False

    if dest is sys.stdout or dest == "-":
        file = sys.stdout
    elif hasattr(dest, "write"):
        file = dest
    else:
        file = open(dest, "w", encoding="utf-8", newline="\n")
        close = True

    try:
        file.write(f"{len(used_caches)}\n")

        for cache_id, videos in used_caches:
            video_list = " ".join(map(str, sorted(videos)))
            file.write(f"{cache_id} {video_list}\n")

        file.flush()

    finally:
        if close:
            file.close()


# ============================================================
# RUN ALL
# ============================================================

def run_all():

    from score import calculate_score

    instances = [
        "me_at_the_zoo",
        "videos_worth_spreading",
        "trending_today",
        "kittens",
    ]

    total = 0

    _print_regle(True)

    for name in instances:

        input_filename = f"{name}.in"
        output_filename = f"{name}.out"

        print(f"=== {name} ===")

        started = time.time()

        (
            V, E, R, C, capacity, video_sizes, endpoints, requests
        ) = read_input(input_filename)

        print(
            f"  V={V} E={E} R={R} C={C} X={capacity} "
            f"({time.time() - started:.1f}s lecture)"
        )

        # 1. GREEDY
        cache_videos = solve(
            C, capacity, video_sizes, endpoints, requests, verbose=True
        )

        score_greedy = calculate_score(endpoints, requests, cache_videos)
        print(f"  score greedy = {score_greedy:,}".replace(",", " "))

        # 2. SAC A DOS PAR CACHE
        cache_videos = optimize_caches(
            cache_videos, C, capacity, video_sizes, endpoints, requests,
            verbose=True
        )

        # 3. WRITE
        write_output(output_filename, cache_videos, verbose=True)

        # 4. SCORE
        score = calculate_score(endpoints, requests, cache_videos)
        elapsed = time.time() - started
        total += score

        print(f"  score final  = {score:,} ({elapsed:.1f}s)".replace(",", " "))
        print()

    print(f"Total : {total:,}".replace(",", " "))


# ============================================================
# MAIN
# ============================================================

def main():

    if len(sys.argv) == 2 and sys.argv[1] == "--all":
        run_all()
        return

    started = time.time()

    judge_mode = len(sys.argv) == 1

    if judge_mode:
        source = sys.stdin
        dest = sys.stdout
        verbose = False

    elif len(sys.argv) >= 3 and not sys.argv[1].startswith("-"):
        source = sys.argv[1]
        dest = sys.argv[2]
        verbose = True

    else:
        print("Utilisation : python main.py fichier.in fichier.out", file=sys.stderr)
        print("              python main.py --all", file=sys.stderr)
        print("              python main.py", file=sys.stderr)
        return

    (
        V, E, R, C, capacity, video_sizes, endpoints, requests
    ) = read_input(source)

    _print_regle(verbose)

    _phase(verbose, 1, "ON LIT LE FICHIER")
    _explain(verbose, f"  {V} videos, {E} endpoints, {R} demandes")
    _explain(verbose, f"  {C} caches, {capacity} MB chacun")

    cache_videos = solve(
        C, capacity, video_sizes, endpoints, requests, verbose=verbose
    )

    cache_videos = optimize_caches(
        cache_videos, C, capacity, video_sizes, endpoints, requests,
        verbose=verbose
    )

    write_output(dest, cache_videos, verbose=verbose)

    if verbose:
        print(f"Solution créée : {dest}", file=sys.stderr)
        print(f"Temps d'exécution : {time.time() - started:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
