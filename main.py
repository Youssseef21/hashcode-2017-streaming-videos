import heapq
import sys
import time
from collections import defaultdict


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
                cache_id, cache_latency = map(int, file.readline().split())
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


def _aggregate_requests(requests):
    counts = defaultdict(int)
    for video_id, endpoint_id, count in requests:
        counts[video_id, endpoint_id] += count

    video_reqs = defaultdict(list)
    for (video_id, endpoint_id), count in counts.items():
        video_reqs[video_id].append((endpoint_id, count))

    return counts, video_reqs


def _solve_large(C, capacity, video_sizes, endpoints, requests, verbose=False, time_limit=8.5):
    """
    Fast cache-by-cache fill for huge instances (kittens).
    Uses flat arrays and a time budget so the judge always gets a solution.
    """
    started = time.perf_counter()
    V = len(video_sizes)
    E = len(endpoints)
    ep_cache = [endpoint["caches"] for endpoint in endpoints]
    ep_dc = [endpoint["datacenter_latency"] for endpoint in endpoints]

    acc = defaultdict(int)
    for video_id, endpoint_id, count in requests:
        acc[video_id, endpoint_id] += count

    nreq = len(acc)
    req_v = [0] * nreq
    req_e = [0] * nreq
    req_n = [0] * nreq
    req_best = [0] * nreq
    ep_rids = [[] for _ in range(E)]
    video_rids = [[] for _ in range(V)]

    for i, ((video_id, endpoint_id), count) in enumerate(acc.items()):
        req_v[i] = video_id
        req_e[i] = endpoint_id
        req_n[i] = count
        req_best[i] = ep_dc[endpoint_id]
        ep_rids[endpoint_id].append(i)
        video_rids[video_id].append(i)

    cache_endpoints = [[] for _ in range(C)]
    demand = [0] * C
    for endpoint_id in range(E):
        request_sum = 0
        rids = ep_rids[endpoint_id]
        for rid in rids:
            request_sum += req_n[rid]
        for cache_id, latency in ep_cache[endpoint_id].items():
            cache_endpoints[cache_id].append((endpoint_id, latency))
            demand[cache_id] += request_sum

    ep_volume = [0] * E
    for endpoint_id in range(E):
        total = 0
        for rid in ep_rids[endpoint_id]:
            total += req_n[rid]
        ep_volume[endpoint_id] = total
        ep_rids[endpoint_id] = tuple(ep_rids[endpoint_id])

    # A cache may connect to hundreds of endpoints. Scanning all of them
    # is too slow for the judge; the busiest endpoints carry most of the score.
    max_endpoints = 70
    for cache_id in range(C):
        conns = cache_endpoints[cache_id]
        if len(conns) > max_endpoints:
            conns.sort(key=lambda item: ep_volume[item[0]], reverse=True)
            cache_endpoints[cache_id] = conns[:max_endpoints]

    remaining = [capacity] * C
    cache_videos = [set() for _ in range(C)]
    benefit = [0] * V
    order = sorted(range(C), key=lambda cid: demand[cid], reverse=True)

    if verbose:
        print(f"  fast-fill: {C} caches, {nreq} requests", file=sys.stderr, flush=True)

    for i, cache_id in enumerate(order):
        if time.perf_counter() - started > time_limit:
            if verbose:
                print(f"  fast-fill: time budget at cache {i}/{C}", file=sys.stderr, flush=True)
            break

        room = remaining[cache_id]
        if room <= 0 or not cache_endpoints[cache_id]:
            continue

        touched = []
        rb = req_best
        rv = req_v
        rn = req_n
        bf = benefit
        add_touched = touched.append
        for endpoint_id, latency in cache_endpoints[cache_id]:
            for rid in ep_rids[endpoint_id]:
                best = rb[rid]
                if latency >= best:
                    continue
                video_id = rv[rid]
                if bf[video_id] == 0:
                    add_touched(video_id)
                bf[video_id] += (best - latency) * rn[rid]

        items = []
        for video_id in touched:
            value = benefit[video_id]
            benefit[video_id] = 0
            size = video_sizes[video_id]
            if value > 0 and 0 < size <= room:
                items.append((value / size, size, video_id))
        items.sort(reverse=True)

        placed_here = cache_videos[cache_id]
        lat_by_ep = {endpoint_id: latency for endpoint_id, latency in cache_endpoints[cache_id]}
        for _density, size, video_id in items:
            if size > remaining[cache_id]:
                continue
            placed_here.add(video_id)
            remaining[cache_id] -= size
            for rid in video_rids[video_id]:
                latency = lat_by_ep.get(req_e[rid])
                if latency is not None and latency < req_best[rid]:
                    req_best[rid] = latency

        if verbose and (i + 1) % 50 == 0:
            print(f"  fast-fill: {i + 1}/{C}", file=sys.stderr, flush=True)

    if verbose:
        placed = sum(len(videos) for videos in cache_videos)
        elapsed = time.perf_counter() - started
        print(f"  fast-fill: {placed} placements in {elapsed:.2f}s", file=sys.stderr, flush=True)

    return cache_videos


def solve(C, capacity, video_sizes, endpoints, requests, verbose=False):
    """
    Incremental greedy with marginal latency gain.

    Only the fastest cache that already holds a video counts, so each
    placement is scored against the current best latency — not against
    the datacenter.
    """
    counts, video_reqs = _aggregate_requests(requests)

    expansion = 0
    if C > 20:
        for _video_id, endpoint_id, _count in requests:
            expansion += len(endpoints[endpoint_id]["caches"])
            if expansion > 8_000_000:
                return _solve_large(
                    C, capacity, video_sizes, endpoints, requests, verbose=verbose
                )

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

    initial_benefit = defaultdict(int)
    for (video_id, endpoint_id), count in counts.items():
        endpoint = endpoints[endpoint_id]
        datacenter_latency = endpoint["datacenter_latency"]
        for cache_id, cache_latency in endpoint["caches"].items():
            saved = datacenter_latency - cache_latency
            if saved > 0:
                initial_benefit[cache_id, video_id] += saved * count

    heap = []
    for (cache_id, video_id), benefit in initial_benefit.items():
        size = video_sizes[video_id]
        if size <= 0 or size > capacity or benefit <= 0:
            continue
        heap.append((-benefit / size, cache_id, video_id, benefit))
    heapq.heapify(heap)

    if verbose:
        print(f"  greedy: {len(heap):,} candidats", file=sys.stderr, flush=True)

    def marginal_benefit(cache_id, video_id):
        if video_id in cache_videos[cache_id]:
            return 0
        size = video_sizes[video_id]
        if size > remaining[cache_id]:
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
            if size <= 0:
                continue
            heapq.heappush(
                heap,
                (-benefit / size, cache_id, video_id, benefit),
            )
            continue

        place(cache_id, video_id)
        placements += 1

    if verbose:
        print(f"  greedy: {placements} placements", file=sys.stderr, flush=True)

    return cache_videos


def write_output(dest, cache_videos):
    used_caches = [
        (cache_id, videos)
        for cache_id, videos in enumerate(cache_videos)
        if videos
    ]

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


def run_all():
    from score import calculate_score

    instances = [
        "me_at_the_zoo",
        "videos_worth_spreading",
        "trending_today",
        "kittens",
    ]

    total = 0
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

        cache_videos = solve(
            C, capacity, video_sizes, endpoints, requests, verbose=True
        )
        write_output(output_filename, cache_videos)
        score = calculate_score(endpoints, requests, cache_videos)
        elapsed = time.time() - started
        total += score
        print(f"  score = {score:,}  ({elapsed:.1f}s)".replace(",", " "))
        print()

    print(f"Total : {total:,}".replace(",", " "))


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "--all":
        run_all()
        return

    # Sphere Engine: no arguments, input on stdin, solution on stdout only.
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
        print("              python main.py   (stdin → stdout)", file=sys.stderr)
        return

    (
        V,
        E,
        R,
        C,
        capacity,
        video_sizes,
        endpoints,
        requests
    ) = read_input(source)

    cache_videos = solve(
        C,
        capacity,
        video_sizes,
        endpoints,
        requests,
        verbose=verbose,
    )

    write_output(dest, cache_videos)

    if verbose:
        print(f"Solution créée : {dest}", file=sys.stderr)


if __name__ == "__main__":
    main()
