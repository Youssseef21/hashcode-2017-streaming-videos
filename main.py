"""
Hash Code 2017 -- Streaming Videos

Pipeline minimal :
    1. Lecture
    2. Greedy densite (alpha=1)
    3. Cache-seq (si utile) : remplir les caches un par un depuis vide
    4. Sac a dos exact par cache (1 seed) + PGCD si tailles commensurables
    5. Recherche locale (trous, promotion, echanges voisins)
    6. Ecriture
"""

from __future__ import annotations

import heapq
import math
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np


TOTAL_TIME_LIMIT = float(os.environ.get("HC_TIME", "570"))
MAX_DP_CELLS = 80_000_000


def choose_params(V, E, R, C, X):
    """Petit reglage : quand activer cache-seq et quelle taille de DP."""
    insane_x = X >= 10_000_000
    tiny_x = X <= 200 and C >= 80
    many_c = C >= 200 and R < 80_000

    if insane_x:
        return {"dp_max_cap": 8_000, "knapsack_max_items": 4_000, "cache_seq": True, "ls_share": 0.25}
    if tiny_x or many_c:
        return {"dp_max_cap": min(X, 20_000), "knapsack_max_items": 3_000, "cache_seq": True, "ls_share": 0.35}
    if X >= 20_000:
        return {"dp_max_cap": min(X, 40_000), "knapsack_max_items": 5_000, "cache_seq": False, "ls_share": 0.18}
    return {"dp_max_cap": min(X, 20_000), "knapsack_max_items": 3_000, "cache_seq": False, "ls_share": 0.20}


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
            datacenter_latency, number_of_caches = map(int, file.readline().split())
            connected_caches = {}
            for _ in range(number_of_caches):
                cache_id, cache_latency = map(int, file.readline().split())
                connected_caches[cache_id] = cache_latency
            endpoints.append({
                "datacenter_latency": datacenter_latency,
                "caches": connected_caches,
            })
        requests = []
        for _ in range(R):
            video_id, endpoint_id, number_of_requests = map(int, file.readline().split())
            requests.append((video_id, endpoint_id, number_of_requests))
    finally:
        if close:
            file.close()
    return V, E, R, C, X, video_sizes, endpoints, requests


def calculate_score(endpoints, requests, cache_videos):
    where = defaultdict(list)
    for cache_id, videos in enumerate(cache_videos):
        for video_id in videos:
            where[video_id].append(cache_id)
    saved = total = 0
    for video_id, endpoint_id, count in requests:
        endpoint = endpoints[endpoint_id]
        datacenter_latency = endpoint["datacenter_latency"]
        best = datacenter_latency
        for cache_id in where.get(video_id, ()):
            latency = endpoint["caches"].get(cache_id)
            if latency is not None and latency < best:
                best = latency
        saved += count * (datacenter_latency - best)
        total += count
    return saved * 1000 // total if total else 0


def _aggregate_requests(requests):
    counts = defaultdict(int)
    for video_id, endpoint_id, count in requests:
        counts[video_id, endpoint_id] += count
    video_reqs = defaultdict(list)
    for (video_id, endpoint_id), count in counts.items():
        video_reqs[video_id].append((endpoint_id, count))
    return counts, video_reqs


def solve(C, capacity, video_sizes, endpoints, requests, verbose=False, trace=None):
    """Greedy lazy par densite (gain / taille)."""
    counts, video_reqs = _aggregate_requests(requests)
    _phase(verbose, 2, "GREEDY densite")

    current_best = {
        (video_id, endpoint_id): endpoints[endpoint_id]["datacenter_latency"]
        for video_id, endpoint_id in counts
    }
    remaining = [capacity] * C
    cache_videos = [set() for _ in range(C)]

    def apply_best_updates(cache_id, video_id):
        for endpoint_id, _count in video_reqs.get(video_id, ()):
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

    initial_benefit = defaultdict(int)
    for (video_id, endpoint_id), count in counts.items():
        endpoint = endpoints[endpoint_id]
        dc = endpoint["datacenter_latency"]
        for cache_id, cache_latency in endpoint["caches"].items():
            saved = dc - cache_latency
            if saved > 0:
                initial_benefit[cache_id, video_id] += saved * count

    heap = []
    for (cache_id, video_id), benefit in initial_benefit.items():
        size = video_sizes[video_id]
        if size <= 0 or size > capacity or benefit <= 0:
            continue
        heap.append((-benefit / size, cache_id, video_id, benefit))
    heapq.heapify(heap)

    def marginal_benefit(cache_id, video_id):
        if video_id in cache_videos[cache_id] or video_sizes[video_id] > remaining[cache_id]:
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
    while heap:
        _neg, cache_id, video_id, old_benefit = heapq.heappop(heap)
        if video_id in cache_videos[cache_id]:
            continue
        size = video_sizes[video_id]
        if size > remaining[cache_id]:
            continue
        benefit = marginal_benefit(cache_id, video_id)
        if benefit <= 0:
            continue
        if benefit != old_benefit:
            heapq.heappush(heap, (-benefit / size, cache_id, video_id, benefit))
            continue
        place(cache_id, video_id)
        placements += 1
        if trace is not None:
            trace.append((
                cache_id, video_id, size, remaining[cache_id],
                benefit, capacity - remaining[cache_id],
            ))

    _explain(verbose, f"  {placements} placements")
    return cache_videos


def build_structures(C, endpoints, counts):
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


def _recompute_best(v, e, endpoints, cache_videos):
    endpoint = endpoints[e]
    dc = endpoint["datacenter_latency"]
    b1, b1c, b2 = dc, -1, dc
    for c2, lat in endpoint["caches"].items():
        if lat < b2 and v in cache_videos[c2]:
            if lat < b1:
                b2, b1, b1c = b1, lat, c2
            else:
                b2 = lat
    return (b1, b1c, b2)


def build_best_state(endpoints, counts, cache_videos):
    return {(v, e): _recompute_best(v, e, endpoints, cache_videos) for v, e in counts}


def update_best_state(c, changed, endpoints, cache_endpoints, counts, cache_videos, state):
    for e, _lat in cache_endpoints[c]:
        for v in changed:
            if (v, e) in counts:
                state[v, e] = _recompute_best(v, e, endpoints, cache_videos)


def compute_gain(c, cache_endpoints, ep_reqs, state):
    gain = defaultdict(int)
    for e, lat in cache_endpoints[c]:
        for v, count in ep_reqs[e]:
            b1, b1c, b2 = state[v, e]
            without_c = b2 if b1c == c else b1
            if lat < without_c:
                gain[v] += (without_c - lat) * count
    return gain


def prepare_optimization(C, endpoints, requests):
    counts, _ = _aggregate_requests(requests)
    ep_reqs, cache_endpoints, neighbors = build_structures(C, endpoints, counts)
    return counts, ep_reqs, cache_endpoints, neighbors


def fractional_bound(items, capacity):
    ordered = sorted(items, key=lambda t: t[1] / t[2], reverse=True)
    total, cap = 0.0, capacity
    for _v, g, s in ordered:
        if s <= cap:
            total += g
            cap -= s
        else:
            total += g * cap / s
            break
    return total


def knapsack_dp(items, capacity):
    n = len(items)
    dp = np.zeros(capacity + 1, dtype=np.int64)
    keep = np.zeros((n, capacity + 1), dtype=bool)
    for i, (_v, g, s) in enumerate(items):
        if s > capacity:
            continue
        new = dp[: capacity + 1 - s] + g
        better = new > dp[s:]
        keep[i, s:] = better
        dp[s:] = np.where(better, new, dp[s:])
    chosen = set()
    cap = capacity
    for i in range(n - 1, -1, -1):
        if cap >= 0 and keep[i, cap]:
            v, _g, s = items[i]
            chosen.add(v)
            cap -= s
    return chosen, int(dp[capacity])


def knapsack_greedy(items, capacity):
    ordered = sorted(items, key=lambda t: t[1] / t[2], reverse=True)
    chosen, cap, value = set(), capacity, 0
    for v, g, s in ordered:
        if 0 < s <= cap:
            chosen.add(v)
            cap -= s
            value += g
    return chosen, value


def _real_value(chosen, items, capacity):
    by_id = {v: (g, s) for v, g, s in items}
    ordered = sorted(
        chosen,
        key=lambda v: by_id[v][0] / by_id[v][1] if by_id[v][1] else 0,
        reverse=True,
    )
    selected, cap, value = set(), capacity, 0
    for v in ordered:
        g, s = by_id[v]
        if 0 < s <= cap:
            selected.add(v)
            cap -= s
            value += g
    for v, g, s in sorted(items, key=lambda t: t[1] / t[2], reverse=True):
        if v not in selected and 0 < s <= cap:
            selected.add(v)
            cap -= s
            value += g
    return selected, value


def _size_gcd(items, capacity):
    g = int(capacity)
    for _v, _gain, s in items:
        if 0 < s <= capacity:
            g = math.gcd(g, int(s))
            if g == 1:
                return 1
    return max(1, g)


def knapsack(items, capacity, dp_max_cap=20_000):
    if not items or capacity <= 0:
        return set(), 0
    if sum(s for _v, _g, s in items) <= capacity:
        return {v for v, g, s in items}, sum(g for v, g, s in items)

    gcd = _size_gcd(items, capacity)
    if gcd > 1:
        capacity = capacity // gcd
        items = [(v, g, s // gcd) for v, g, s in items]

    n = len(items)
    if capacity <= dp_max_cap and n * (capacity + 1) <= MAX_DP_CELLS:
        return knapsack_dp(items, capacity)

    scale = max(1, (capacity + dp_max_cap - 1) // dp_max_cap)
    scaled_cap = max(1, capacity // scale)
    scaled = [(v, g, max(1, s // scale)) for v, g, s in items]
    if len(scaled) * (scaled_cap + 1) > MAX_DP_CELLS:
        return knapsack_greedy(items, capacity)
    chosen, _ = knapsack_dp(scaled, scaled_cap)
    return _real_value(chosen, items, capacity)


def solve_cache_seq(
    C, capacity, video_sizes, endpoints, requests, cfg=None, deadline=None, reverse=False
):
    """Remplit chaque cache une fois, depuis vide."""
    cfg = cfg or {}
    prep = prepare_optimization(C, endpoints, requests)
    counts, ep_reqs, cache_endpoints, _ = prep
    cache_videos = [set() for _ in range(C)]
    state = build_best_state(endpoints, counts, cache_videos)
    # reverse=False : plus connectes d'abord ; reverse=True : moins d'abord (utile sur 01)
    order = sorted(range(C), key=lambda c: len(cache_endpoints[c]), reverse=not reverse)

    for c in order:
        if deadline is not None and time.time() >= deadline:
            break
        gain = compute_gain(c, cache_endpoints, ep_reqs, state)
        items = [
            (v, g, video_sizes[v])
            for v, g in gain.items()
            if g > 0 and 0 < video_sizes[v] <= capacity
        ]
        if not items:
            continue
        chosen, _ = knapsack(items, capacity, dp_max_cap=cfg.get("dp_max_cap", 20_000))
        if not chosen:
            continue
        cache_videos[c] = chosen
        update_best_state(c, chosen, endpoints, cache_endpoints, counts, cache_videos, state)
    return cache_videos


def optimize_caches(
    cache_videos,
    C,
    capacity,
    video_sizes,
    endpoints,
    requests=None,
    verbose=False,
    prep=None,
    deadline=None,
    cfg=None,
    time_limit=None,
):
    """Coordinate ascent sac a dos. Compatible generate_contest (requests en 6e arg)."""
    if prep is None:
        if requests is None:
            raise ValueError("optimize_caches needs requests or prep")
        prep = prepare_optimization(C, endpoints, requests)
    if deadline is None:
        deadline = time.time() + (time_limit if time_limit is not None else 20.0)
    cfg = cfg or {}

    counts, ep_reqs, cache_endpoints, neighbors = prep
    state = build_best_state(endpoints, counts, cache_videos)
    dirty = set(c for c in range(C) if cache_endpoints[c])
    improved = 0

    while dirty and time.time() < deadline:
        batch = list(dirty)
        random.shuffle(batch)
        for c in batch:
            if time.time() >= deadline:
                break
            if c not in dirty:
                continue
            dirty.discard(c)

            gain = compute_gain(c, cache_endpoints, ep_reqs, state)
            items = [
                (v, g, video_sizes[v])
                for v, g in gain.items()
                if g > 0 and 0 < video_sizes[v] <= capacity
            ]
            if not items:
                continue
            current = sum(gain.get(v, 0) for v in cache_videos[c])

            if sum(s for _v, _g, s in items) <= capacity:
                new_set = {v for v, _g, _s in items}
                value = sum(g for _v, g, _s in items)
            else:
                if fractional_bound(items, capacity) <= current:
                    continue
                max_items = cfg.get("knapsack_max_items")
                if max_items is not None and len(items) > max_items:
                    items.sort(key=lambda t: t[1] / t[2], reverse=True)
                    items = items[:max_items]
                new_set, value = knapsack(items, capacity, dp_max_cap=cfg.get("dp_max_cap", 20_000))

            if value > current:
                changed = cache_videos[c] ^ new_set
                cache_videos[c] = new_set
                update_best_state(
                    c, changed, endpoints, cache_endpoints, counts, cache_videos, state
                )
                improved += 1
                dirty.update(neighbors[c])

    _explain(verbose, f"  sac a dos : {improved} caches ameliores")
    return cache_videos


def _delta_add(c, v, cache_endpoints, counts, state):
    total = 0
    for e, lat in cache_endpoints[c]:
        key = (v, e)
        if key not in counts:
            continue
        b1, _b1c, _b2 = state[key]
        if lat < b1:
            total += (b1 - lat) * counts[key]
    return total


def _apply_add(c, v, cache_videos, remaining, video_sizes, endpoints, cache_endpoints, counts, state):
    cache_videos[c].add(v)
    remaining[c] -= video_sizes[v]
    update_best_state(c, {v}, endpoints, cache_endpoints, counts, cache_videos, state)


def _apply_remove(c, v, cache_videos, remaining, video_sizes, endpoints, cache_endpoints, counts, state):
    cache_videos[c].discard(v)
    remaining[c] += video_sizes[v]
    update_best_state(c, {v}, endpoints, cache_endpoints, counts, cache_videos, state)


def local_search(
    cache_videos, C, capacity, video_sizes, endpoints, requests, prep, deadline, verbose=False
):
    """Trous + promotion + echanges voisins ; coup garde seulement si score monte."""
    _phase(verbose, 5, "RECHERCHE LOCALE")
    if time.time() >= deadline:
        return cache_videos

    counts, ep_reqs, cache_endpoints, neighbors = prep

    def clone(sol):
        return [set(vs) for vs in sol]

    def rebuild(sol):
        st = build_best_state(endpoints, counts, sol)
        rem = [capacity - sum(video_sizes[v] for v in sol[c]) for c in range(C)]
        return st, rem

    best = clone(cache_videos)
    best_score = calculate_score(endpoints, requests, best)
    cache_videos = clone(best)
    state, remaining = rebuild(cache_videos)
    accepted = 0

    def restore():
        nonlocal cache_videos, state, remaining
        cache_videos = clone(best)
        state, remaining = rebuild(cache_videos)

    def accept():
        nonlocal best_score, best, accepted
        sc = calculate_score(endpoints, requests, cache_videos)
        if sc > best_score:
            best_score = sc
            best = clone(cache_videos)
            accepted += 1
            return True
        restore()
        return False

    # Trous
    for c in range(C):
        if time.time() >= deadline or remaining[c] <= 0:
            continue
        items = []
        for v, g in compute_gain(c, cache_endpoints, ep_reqs, state).items():
            size = video_sizes[v]
            if v not in cache_videos[c] and g > 0 and 0 < size <= remaining[c]:
                items.append((g / size, v, size))
        items.sort(reverse=True)
        for _d, v, size in items[:12]:
            if time.time() >= deadline or size > remaining[c] or v in cache_videos[c]:
                continue
            _apply_add(c, v, cache_videos, remaining, video_sizes, endpoints, cache_endpoints, counts, state)
            if not accept():
                break

    # Promotion
    for c in range(C):
        if time.time() >= deadline:
            break
        for v in list(cache_videos[c]):
            if time.time() >= deadline:
                break
            size = video_sizes[v]
            best_c2, best_g, seen = None, 0, set()
            for e, lat in cache_endpoints[c]:
                if (v, e) not in counts:
                    continue
                for c2, lat2 in endpoints[e]["caches"].items():
                    if c2 == c or c2 in seen or v in cache_videos[c2]:
                        continue
                    seen.add(c2)
                    if remaining[c2] < size or lat2 >= lat:
                        continue
                    g = _delta_add(c2, v, cache_endpoints, counts, state)
                    if g > best_g:
                        best_g, best_c2 = g, c2
            if best_c2 is None:
                continue
            _apply_add(best_c2, v, cache_videos, remaining, video_sizes, endpoints, cache_endpoints, counts, state)
            accept()

    # Echanges voisins
    pairs = [(c1, c2) for c1 in range(C) for c2 in neighbors[c1] if c2 > c1]
    random.shuffle(pairs)
    for c1, c2 in pairs:
        if time.time() >= deadline:
            break
        vids1, vids2 = list(cache_videos[c1]), list(cache_videos[c2])
        if not vids1 or not vids2:
            continue
        random.shuffle(vids1)
        random.shuffle(vids2)
        got = False
        for v in vids1[:14]:
            if got or time.time() >= deadline:
                break
            sv = video_sizes[v]
            for w in vids2[:14]:
                if v == w or w in cache_videos[c1] or v in cache_videos[c2]:
                    continue
                sw = video_sizes[w]
                if sv > remaining[c2] + sw or sw > remaining[c1] + sv:
                    continue
                _apply_remove(c1, v, cache_videos, remaining, video_sizes, endpoints, cache_endpoints, counts, state)
                _apply_remove(c2, w, cache_videos, remaining, video_sizes, endpoints, cache_endpoints, counts, state)
                if sv <= remaining[c2]:
                    _apply_add(c2, v, cache_videos, remaining, video_sizes, endpoints, cache_endpoints, counts, state)
                if sw <= remaining[c1]:
                    _apply_add(c1, w, cache_videos, remaining, video_sizes, endpoints, cache_endpoints, counts, state)
                if accept():
                    got = True
                    break
                break

    _explain(verbose, f"  +{accepted} coups, score={best_score}")
    return best


def write_output(dest, cache_videos, verbose=False):
    _phase(verbose, 6, "ECRITURE")
    used = [(c, vs) for c, vs in enumerate(cache_videos) if vs]
    close = False
    if dest is sys.stdout or dest == "-":
        file = sys.stdout
    elif hasattr(dest, "write"):
        file = dest
    else:
        file = open(dest, "w", encoding="utf-8", newline="\n")
        close = True
    try:
        file.write(f"{len(used)}\n")
        for cache_id, videos in used:
            file.write(f"{cache_id} {' '.join(map(str, sorted(videos)))}\n")
        file.flush()
    finally:
        if close:
            file.close()


def solve_instance(source, dest=None, verbose=False, time_limit=None):
    started = time.time()
    budget = TOTAL_TIME_LIMIT if time_limit is None else time_limit
    V, E, R, C, capacity, video_sizes, endpoints, requests = read_input(source)
    cfg = choose_params(V, E, R, C, capacity)
    deadline = started + budget

    _phase(verbose, 1, "LECTURE")
    _explain(verbose, f"  V={V} E={E} R={R} C={C} X={capacity}")
    _explain(verbose, f"  cache_seq={cfg['cache_seq']} dpX={cfg['dp_max_cap']}")

    # 1) greedy
    start = solve(C, capacity, video_sizes, endpoints, requests, verbose=verbose)
    score_g = calculate_score(endpoints, requests, start)

    # 2) cache-seq si utile (les 2 ordres), on garde le meilleur depart
    if cfg["cache_seq"]:
        for reverse in (False, True):
            if time.time() >= deadline:
                break
            seq = solve_cache_seq(
                C, capacity, video_sizes, endpoints, requests,
                cfg=cfg, deadline=deadline, reverse=reverse,
            )
            score_seq = calculate_score(endpoints, requests, seq)
            _explain(verbose, f"  cache-seq reverse={reverse} -> {score_seq}")
            if score_seq > score_g:
                start = seq
                score_g = score_seq

    # 3) sac a dos (1 seed)
    prep = prepare_optimization(C, endpoints, requests)
    ls_deadline = deadline
    knap_deadline = deadline - budget * cfg["ls_share"]
    work = [set(v) for v in start]
    if time.time() < knap_deadline:
        random.seed(0)
        work = optimize_caches(
            work, C, capacity, video_sizes, endpoints,
            prep=prep, deadline=knap_deadline, verbose=verbose, cfg=cfg,
        )

    # 4) recherche locale
    work = local_search(
        work, C, capacity, video_sizes, endpoints, requests, prep,
        deadline=ls_deadline, verbose=verbose,
    )
    score = calculate_score(endpoints, requests, work)

    if dest is not None:
        write_output(dest, work, verbose=verbose)

    return {
        "V": V, "E": E, "R": R, "C": C, "X": capacity,
        "greedy": score_g, "score": score, "elapsed": time.time() - started,
    }


def run_local(folder="_local", time_limit=90.0):
    folder = Path(folder)
    paths = sorted(folder.glob("instance*.txt"))
    print(f"{'fichier':18} {'greedy':>10} {'final':>10} {'sec':>7}")
    print("-" * 50)
    for path in paths:
        info = solve_instance(str(path), str(path.with_suffix(".out")), False, time_limit)
        print(
            f"{path.name:18} {info['greedy']:10d} {info['score']:10d} "
            f"{info['elapsed']:6.1f}s"
        )


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--local":
        limit = float(sys.argv[2]) if len(sys.argv) >= 3 else 90.0
        run_local("_local", time_limit=limit)
        return

    started = time.time()
    if len(sys.argv) == 1:
        source, dest, verbose = sys.stdin, sys.stdout, False
    elif len(sys.argv) >= 3 and not sys.argv[1].startswith("-"):
        source, dest, verbose = sys.argv[1], sys.argv[2], True
    else:
        print("Utilisation : python main.py fichier.in fichier.out", file=sys.stderr)
        print("              python main.py --local [secondes]", file=sys.stderr)
        return

    info = solve_instance(source, dest, verbose=verbose)
    if verbose:
        print(f"Score greedy : {info['greedy']}", file=sys.stderr)
        print(f"Score final  : {info['score']}", file=sys.stderr)
        print(f"Temps        : {time.time() - started:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
