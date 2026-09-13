import sys


def read_input(filename):
    with open(filename, "r", encoding="utf-8") as file:
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
            video_id, endpoint_id, request_count = map(
                int, file.readline().split()
            )
            requests.append((video_id, endpoint_id, request_count))

    return C, X, video_sizes, endpoints, requests


def read_output(filename, cache_count, capacity, video_sizes):
    caches = [set() for _ in range(cache_count)]

    with open(filename, "r", encoding="utf-8") as file:
        first_line = file.readline().strip()

        if not first_line:
            raise ValueError("Le fichier de sortie est vide.")

        number_of_cache_lines = int(first_line)

        for _ in range(number_of_cache_lines):
            values = list(map(int, file.readline().split()))

            if not values:
                raise ValueError("Une ligne de cache est vide.")

            cache_id = values[0]
            videos = values[1:]

            if not 0 <= cache_id < cache_count:
                raise ValueError(f"Cache invalide : {cache_id}")

            if caches[cache_id]:
                raise ValueError(
                    f"Le cache {cache_id} est décrit plusieurs fois."
                )

            if len(videos) != len(set(videos)):
                raise ValueError(
                    f"Une vidéo est répétée dans le cache {cache_id}."
                )

            for video_id in videos:
                if not 0 <= video_id < len(video_sizes):
                    raise ValueError(
                        f"Vidéo invalide : {video_id}"
                    )

            used_capacity = sum(video_sizes[v] for v in videos)

            if used_capacity > capacity:
                raise ValueError(
                    f"Cache {cache_id} dépasse sa capacité : "
                    f"{used_capacity}/{capacity} Mo"
                )

            caches[cache_id] = set(videos)

    return caches


def calculate_score(endpoints, requests, caches):
    total_saved_time = 0
    total_requests = 0

    for video_id, endpoint_id, request_count in requests:
        endpoint = endpoints[endpoint_id]
        datacenter_latency = endpoint["datacenter_latency"]

        best_latency = datacenter_latency

        for cache_id, cache_latency in endpoint["caches"].items():
            if video_id in caches[cache_id]:
                best_latency = min(best_latency, cache_latency)

        saved_time = datacenter_latency - best_latency

        total_saved_time += saved_time * request_count
        total_requests += request_count

    if total_requests == 0:
        return 0

    return (total_saved_time * 1000) // total_requests


def main():
    if len(sys.argv) != 3:
        print("Utilisation : python score.py entree.in sortie.out")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    try:
        C, capacity, video_sizes, endpoints, requests = read_input(
            input_file
        )

        caches = read_output(
            output_file,
            C,
            capacity,
            video_sizes
        )

        score = calculate_score(endpoints, requests, caches)

        print(f"Score : {score:,}".replace(",", " "))
        print("Le score représente les microsecondes économisées par requête.")

    except (OSError, ValueError) as error:
        print(f"Erreur : {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()