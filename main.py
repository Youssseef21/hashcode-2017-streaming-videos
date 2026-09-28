"""
Hash Code 2017 -- Streaming Videos

Deroulement (a montrer en presentation) :

  1. Lire l'instance            ->  read_input
  2. Fusionner les requetes     ->  _aggregate_requests
  3. Choisir les placements     ->  solve (greedy paresseux par densite, tas)
  4. Ecrire les caches          ->  write_output

Idee centrale : seul le cache LE PLUS RAPIDE qui a deja la video compte.
On note donc un placement par son gain MARGINAL par rapport au meilleur
actuel, plus par rapport au datacenter une fois qu'une meilleure copie existe.
Densite = gain_marginal / taille  (greedy style sac a dos).
"""

import heapq
import sys
import time
from collections import defaultdict

# Garde-fou optionnel pour les tres grosses instances (kittens).
# None = greedy pur, aucun filtre. Si memoire/temps trop eleves, essayer
# par exemple 3_000_000 : on ne garde que les meilleures idees au depart.
MAX_CANDIDATES = None


def _explain(verbose, message=""):
    """Affiche une ligne de presentation dans le terminal (stderr, jamais le .out)."""
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
    """Regle du greedy, affichee en premier pour l'oral."""
    _phase(verbose, 0, "LA REGLE (comment on calcule)")
    _explain(verbose, "  Score officiel : on economise du temps si la video est dans un cache proche.")
    _explain(verbose, "  Seul le cache LE PLUS RAPIDE compte (pas les copies plus lentes).")
    _explain(verbose, "")
    _explain(verbose, "  Gain d'un couple (video, cache) :")
    _explain(verbose, "    gain = (latence_actuelle - latence_cache) x nombre_de_requetes")
    _explain(verbose, "    uniquement si ce cache est plus rapide que le meilleur actuel")
    _explain(verbose, "")
    _explain(verbose, "  Au debut, latence_actuelle = datacenter (loin).")
    _explain(verbose, "  Apres un placement, latence_actuelle = ce cache (plus proche).")
    _explain(verbose, "")
    _explain(verbose, "  Densite = gain / taille_en_Mo")
    _explain(verbose, "  On prend toujours la densite la plus grande (le plus de temps gagne par Mo).")
    _explain(verbose, "")
    _explain(verbose, "  OUI = le gain n'a pas change, on place.")
    _explain(verbose, "  NON = le gain a baisse (deja une meilleure copie), on remet dans la liste.")


# =============================================================================
# PHASE 1 -- LECTURE DE L'INSTANCE
# Format : V E R C X, puis tailles, puis endpoints, puis requetes.
# =============================================================================

def read_input(source):
    close = False
    if hasattr(source, "readline"):
        file = source
    else:
        file = open(source, "r", encoding="utf-8")
        close = True

    try:
        # V videos, E endpoints, R lignes de requetes, C caches, X = capacite (Mo)
        V, E, R, C, X = map(int, file.readline().split())
        video_sizes = list(map(int, file.readline().split()))

        endpoints = []
        for _ in range(E):
            datacenter_latency, number_of_caches = map(
                int, file.readline().split()
            )
            # cache_id -> latence depuis cet endpoint (uniquement les caches relies)
            connected_caches = {}
            for _ in range(number_of_caches):
                cache_id, cache_latency = map(int, file.readline().split())
                connected_caches[cache_id] = cache_latency
            endpoints.append({
                "datacenter_latency": datacenter_latency,
                "caches": connected_caches
            })

        # Chaque requete : "l'endpoint e veut la video v, n fois"
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


# =============================================================================
# PHASE 2 -- AGREGATION DES REQUETES
# Deux lignes (v, e, 10) et (v, e, 4) deviennent un volume de 14.
# video_reqs[v] = liste des (endpoint, volume) qui demandent v.
# =============================================================================

def _aggregate_requests(requests):
    counts = defaultdict(int)
    for video_id, endpoint_id, count in requests:
        counts[video_id, endpoint_id] += count

    video_reqs = defaultdict(list)
    for (video_id, endpoint_id), count in counts.items():
        video_reqs[video_id].append((endpoint_id, count))

    return counts, video_reqs


# =============================================================================
# PHASE 3 -- GREEDY PARESSEUX PAR DENSITE
# Type : greedy incremental + file de priorite paresseuse (Minoux).
#   densite = gain_marginal / taille
#   Apres chaque placement, on re-verifie les candidats (on ne reconstruit pas le tas).
# =============================================================================

def solve(C, capacity, video_sizes, endpoints, requests, verbose=False):
    """
    Greedy incremental a gain de latence marginal.

    Seul le cache le plus rapide qui contient deja la video compte.
    Chaque placement est donc note contre la meilleure latence actuelle,
    pas contre le datacenter.
    """
    counts, video_reqs = _aggregate_requests(requests)
    _phase(verbose, 2, "ON FUSIONNE LES DEMANDES IDENTIQUES")
    _explain(
        verbose,
        f"  {len(requests)} lignes dans le fichier -> {len(counts)} vraies demandes",
    )

    _phase(verbose, 3, "GREEDY : on prend le meilleur coup, un par un")
    _explain(verbose, "  A chaque etape : quelle video mettre dans quel cache ?")
    _explain(verbose, "  On choisit celle qui rapporte le plus par Mo (densite).")
    _explain(verbose, "  Si une video est deja dans un cache plus rapide, recopier ne sert a rien.")

    # --- 3.1 state: best latency per (video, endpoint), space left per cache ---
    # Start from the datacenter: nothing is cached yet.
    current_best = {
        (video_id, endpoint_id): endpoints[endpoint_id]["datacenter_latency"]
        for video_id, endpoint_id in counts
    }
    _explain(verbose, "  Au debut, tout le monde telecharge depuis le datacenter (loin).")

    remaining = [capacity] * C
    cache_videos = [set() for _ in range(C)]

    def apply_best_updates(cache_id, video_id):
        """Apres placement : certains endpoints ont peut-etre une copie plus rapide."""
        for endpoint_id, count in video_reqs.get(video_id, ()):
            latency = endpoints[endpoint_id]["caches"].get(cache_id)
            if latency is None:
                continue
            key = (video_id, endpoint_id)
            if latency < current_best[key]:
                current_best[key] = latency

    def place(cache_id, video_id):
        """Pose un couple (cache, video) s'il tient encore."""
        if video_id in cache_videos[cache_id]:
            return
        size = video_sizes[video_id]
        if size > remaining[cache_id]:
            return
        cache_videos[cache_id].add(video_id)
        remaining[cache_id] -= size
        apply_best_updates(cache_id, video_id)

    # --- 3.2 seed scores vs the datacenter (first ranking only) ---
    initial_benefit = defaultdict(int)
    for (video_id, endpoint_id), count in counts.items():
        endpoint = endpoints[endpoint_id]
        datacenter_latency = endpoint["datacenter_latency"]
        for cache_id, cache_latency in endpoint["caches"].items():
            saved = datacenter_latency - cache_latency
            if saved > 0:
                initial_benefit[cache_id, video_id] += saved * count

    # Max-heap of (-density, cache, video, benefit_used_to_rank)
    # Python heapq is a min-heap, so we store negative density.
    heap = []
    for (cache_id, video_id), benefit in initial_benefit.items():
        size = video_sizes[video_id]
        if size <= 0 or size > capacity or benefit <= 0:
            continue
        heap.append((-benefit / size, cache_id, video_id, benefit))
    del initial_benefit  # libere la memoire avant la boucle principale

    if MAX_CANDIDATES is not None and len(heap) > MAX_CANDIDATES:
        _explain(
            verbose,
            f"  Filtre : on garde les {MAX_CANDIDATES} meilleures idees sur {len(heap)}",
        )
        # nsmallest sur -densite = les plus fortes densites ; la liste triee est un tas valide
        heap = heapq.nsmallest(MAX_CANDIDATES, heap)
    else:
        heapq.heapify(heap)

    _explain(verbose, f"  On a {len(heap)} idees (video + cache), classees de la meilleure a la moins bonne")
    if verbose and heap:
        _top_density, top_c, top_v, top_b = heap[0]
        _explain(
            verbose,
            f"  Premiere idee : video {top_v} dans cache {top_c}  (meilleur rapport gain/taille)",
        )

    def marginal_benefit(cache_id, video_id):
        """
        Millisecondes encore gagnees SI on met cette video dans CE cache.
        Si un cache plus rapide l'a deja, le resultat est 0.
        """
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

    # --- 3.3 lazy greedy loop: pop, re-check, place or re-push ---
    placements = 0
    stale = 0
    _explain(verbose, "")
    _explain(verbose, "  OUI = on met la video    NON = le chiffre a change, on remet dans la liste")

    while heap:
        _neg_density, cache_id, video_id, old_benefit = heapq.heappop(heap)

        if video_id in cache_videos[cache_id]:
            continue

        size = video_sizes[video_id]
        if size > remaining[cache_id]:
            continue

        # Stale entry? Another placement already stole part of this gain.
        benefit = marginal_benefit(cache_id, video_id)
        if benefit <= 0:
            continue

        if benefit != old_benefit:
            # Re-insert with the fresh density; it may no longer be the best.
            if size <= 0:
                continue
            heapq.heappush(
                heap,
                (-benefit / size, cache_id, video_id, benefit),
            )
            stale += 1
            _explain(
                verbose,
                f"    NON  video {video_id} dans cache {cache_id} : "
                f"deja une meilleure copie ailleurs",
            )
            continue

        # Benefit matches the heap key -> this is still the best move. Take it.
        place(cache_id, video_id)
        placements += 1
        _explain(
            verbose,
            f"    OUI  #{placements}  video {video_id} dans cache {cache_id}  "
            f"({size} Mo, reste {remaining[cache_id]} Mo)",
        )

    _explain(verbose, "")
    _explain(verbose, f"  Bilan : {placements} videos placees, {stale} idees trop vieilles (on ne les a pas prises)")
    used = sum(1 for videos in cache_videos if videos)
    _explain(verbose, f"  {used} caches sur {C} sont utilises")

    return cache_videos


# =============================================================================
# PHASE 4 -- ECRITURE DE LA SOLUTION
# Premiere ligne : nombre de caches utilises.
# Ensuite : cache_id  video_id video_id ...
# =============================================================================

def write_output(dest, cache_videos, verbose=False):
    _phase(verbose, 4, "ON ECRIT LE RESULTAT")
    used_caches = [
        (cache_id, videos)
        for cache_id, videos in enumerate(cache_videos)
        if videos
    ]
    _explain(verbose, f"  {len(used_caches)} caches ont recu des videos")
    for cache_id, videos in used_caches:
        liste = " ".join(map(str, sorted(videos)))
        _explain(verbose, f"  cache {cache_id} : {liste}")

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

        cache_videos = solve(
            C, capacity, video_sizes, endpoints, requests, verbose=True
        )
        write_output(output_filename, cache_videos, verbose=True)
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
        print("              python main.py   (stdin -> stdout)", file=sys.stderr)
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

    _print_regle(verbose)

    _phase(verbose, 1, "ON LIT LE FICHIER")
    _explain(verbose, f"  {V} videos, {E} quartiers (endpoints), {R} demandes")
    _explain(verbose, f"  {C} caches, {capacity} Mo chacun")

    cache_videos = solve(
        C,
        capacity,
        video_sizes,
        endpoints,
        requests,
        verbose=verbose,
    )

    write_output(dest, cache_videos, verbose=verbose)

    if verbose:
        print(f"Solution créée : {dest}", file=sys.stderr)


if __name__ == "__main__":
    main()
