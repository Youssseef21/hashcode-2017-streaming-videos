import sys

NB_CACHES = 1000


def mauvaise_entree():
    print("Score = 0")
    return 0


def main():
    if len(sys.argv) < 3:
        print("USAGE: python judge.py input output")
        print("With:")
        print("  - input: the filename in which there is the instance,")
        print("  - output: the filename in which there is the solution.")
        print("example: python judge.py testcases/a_example.txt testcases/a_example.out")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    # =========================
    # Parse data file
    # =========================

    try:
        with open(input_file, "r") as f:
            data = list(map(int, f.read().split()))
    except FileNotFoundError:
        print(f"Cannot open file {input_file}")
        return

    pos = 0

    # Première ligne :
    # nbVideos nbEndpoints nbRequest nbCaches capacity
    nb_videos = data[pos]
    nb_endpoints = data[pos + 1]
    nb_requests = data[pos + 2]
    nb_caches = data[pos + 3]
    capacity = data[pos + 4]
    pos += 5

    # Tailles des vidéos
    sizes = data[pos:pos + nb_videos]
    pos += nb_videos

    # Endpoints
    endpoints = []

    for _ in range(nb_endpoints):
        datacenter_latency = data[pos]
        nb_caches_endpoint = data[pos + 1]
        pos += 2

        caches_latency = [0] * NB_CACHES

        for _ in range(nb_caches_endpoint):
            cache = data[pos]
            latency = data[pos + 1]
            pos += 2

            caches_latency[cache] = latency

        endpoints.append({
            "datacenter": datacenter_latency,
            "nb_caches": nb_caches_endpoint,
            "caches_latency": caches_latency
        })

    # Requêtes
    requests = []

    for _ in range(nb_requests):
        video = data[pos]
        endpoint = data[pos + 1]
        nb = data[pos + 2]
        pos += 3

        requests.append({
            "video": video,
            "endpoint": endpoint,
            "nb": nb
        })

    # =========================
    # Parse and check solution
    # =========================

    try:
        with open(output_file, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Cannot open file {output_file}")
        return

    if not lines:
        return mauvaise_entree()

    # Nombre de caches utilisés
    try:
        nb_used_cache = int(lines[0].strip())
    except ValueError:
        return mauvaise_entree()

    if nb_used_cache > nb_caches:
        return mauvaise_entree()

    # solution[v] = liste des caches contenant la vidéo v
    solution = [[] for _ in range(nb_videos)]

    used_cache = [False] * nb_caches

    # Chaque ligne :
    # cache_id video1 video2 video3 ...
    for i in range(1, nb_used_cache + 1):

        if i >= len(lines):
            return mauvaise_entree()

        parts = lines[i].split()

        if not parts:
            return mauvaise_entree()

        try:
            cache = int(parts[0])
        except ValueError:
            return mauvaise_entree()

        # Vérification du cache
        if cache >= nb_caches or cache < 0:
            return mauvaise_entree()

        if used_cache[cache]:
            return mauvaise_entree()

        used_cache[cache] = True

        total_size = 0

        # Vidéos placées dans ce cache
        for value in parts[1:]:

            try:
                video = int(value)
            except ValueError:
                return mauvaise_entree()

            if video >= nb_videos or video < 0:
                return mauvaise_entree()

            solution[video].append(cache)
            total_size += sizes[video]

        # Vérification de la capacité
        if total_size > capacity:
            return mauvaise_entree()

    # =========================
    # Compute score
    # =========================

    score = 0
    total_request = 0

    for request in requests:

        endpoint_id = request["endpoint"]
        video = request["video"]
        nb = request["nb"]

        endpoint = endpoints[endpoint_id]

        data_latency = endpoint["datacenter"]
        min_latency = data_latency

        total_request += nb

        # Parcourt les caches contenant cette vidéo
        for cache in solution[video]:

            latency = endpoint["caches_latency"][cache]

            # Dans le code C++, une latence de 0 signifie
            # que le cache n'est pas connecté à cet endpoint.
            if latency > 0:
                min_latency = min(min_latency, latency)

        score += nb * (data_latency - min_latency)

    # Même calcul que :
    # score*1000/totalRequest
    final_score = score * 1000 // total_request

    print(f"Score = {final_score}")


def calculate_score(endpoints, requests, caches):
    """Score officiel Hash Code : microsecondes gagnees par requete (division entiere)."""
    total_saved = 0
    total_requests = 0
    for video_id, endpoint_id, count in requests:
        endpoint = endpoints[endpoint_id]
        datacenter = endpoint["datacenter_latency"]
        best = datacenter
        for cache_id, latency in endpoint["caches"].items():
            if video_id in caches[cache_id] and latency < best:
                best = latency
        total_saved += (datacenter - best) * count
        total_requests += count
    if total_requests == 0:
        return 0
    return (total_saved * 1000) // total_requests


if __name__ == "__main__":
    main()
