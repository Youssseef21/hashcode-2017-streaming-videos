import sys

def get_placements(solution_file):
    placements = set()
    try:
        with open(solution_file, "r", encoding="utf-8") as f:
            lines = f.read().strip().split("\n")
    except FileNotFoundError:
        print("Error: solution missing")
        return placements

    if lines and lines[0]:
        n_lines = int(lines[0].strip())
        for i in range(1, n_lines + 1):
            parts = list(map(int, lines[i].split()))
            c_id = parts[0]
            for v_id in parts[1:]:
                placements.add((c_id, v_id))
    return placements


def calc_similarity(sol1, sol2):
    s1 = get_placements(sol1)
    s2 = get_placements(sol2)
    union_size = len(s1 | s2)
    if union_size == 0:
        return 100.0
    return (len(s1 & s2) / union_size) * 100.0


def evaluate_and_plot(input_file, solution_file):
    with open(input_file, "r", encoding="utf-8") as f:
        in_data = f.read().split()

    if not in_data:
        print("Error: empty input")
        return

    it = iter(in_data)
    V = int(next(it))
    E = int(next(it))
    R = int(next(it))
    C = int(next(it))
    X = int(next(it))

    video_sizes = [int(next(it)) for _ in range(V)]

    endpoints = {}
    for e_id in range(E):
        l_d = int(next(it))
        k = int(next(it))
        connections = {}
        for _ in range(k):
            c_id = int(next(it))
            l_c = int(next(it))
            connections[c_id] = l_c
        endpoints[e_id] = {"L_D": l_d, "connections": connections}

    requests = []
    for _ in range(R):
        v = int(next(it))
        e = int(next(it))
        n = int(next(it))
        requests.append((v, e, n))

    try:
        with open(solution_file, "r", encoding="utf-8") as f:
            sol_lines = f.read().strip().split("\n")
    except FileNotFoundError:
        print("Error: solution missing")
        return

    cache_contents = {i: set() for i in range(C)}
    if sol_lines and sol_lines[0]:
        n_lines = int(sol_lines[0].strip())
        for i in range(1, n_lines + 1):
            parts = list(map(int, sol_lines[i].split()))
            c_id = parts[0]
            cache_contents[c_id] = set(parts[1:])

    space_pct = [0.0] * C
    time_saved = [0] * C
    video_presence = [0] * V
    data_dc = [0] * E
    data_cache = {c: [0] * E for c in range(C)}

    for c in range(C):
        used = sum(video_sizes[v] for v in cache_contents[c])
        space_pct[c] = (used / X) * 100 if X else 0.0

    for c in range(C):
        for v in cache_contents[c]:
            video_presence[v] += 1

    total_saved = 0
    total_req = 0
    for v, e, n in requests:
        ep = endpoints[e]
        l_d = ep["L_D"]
        min_l = l_d
        best_c = -1
        for c, l_c in ep["connections"].items():
            if v in cache_contents[c] and l_c < min_l:
                min_l = l_c
                best_c = c
        data_vol = video_sizes[v] * n
        total_req += n
        if best_c != -1:
            gain = n * (l_d - min_l)
            time_saved[best_c] += gain
            total_saved += gain
            data_cache[best_c][e] += data_vol
        else:
            data_dc[e] += data_vol

    score = (total_saved * 1000) // total_req if total_req else 0
    used_caches = sum(1 for s in space_pct if s > 0)
    videos_cached = sum(1 for p in video_presence if p > 0)

    print(f"Instance : {input_file}")
    print(f"Solution : {solution_file}")
    print(f"  V={V}  E={E}  R={R}  C={C}  X={X}")
    print(f"  Caches utilises : {used_caches}/{C}")
    print(f"  Videos en cache : {videos_cached}/{V}")
    print(f"  Occupation moyenne : {sum(space_pct)/C:.1f} %")
    print(f"  Score : {score}")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        print("Pour les graphes : pip install plotly")
        return

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Space Used per Cache (%)",
            "Time Saved per Cache",
            "Cache Presence per Video",
            "Data Volume per Endpoint (MB)",
        ),
    )

    fig.add_trace(
        go.Bar(
            x=list(range(C)),
            y=space_pct,
            marker_color="steelblue",
            hovertemplate="Cache %{x}<br>Space: %{y:.2f}%<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=list(range(C)),
            y=time_saved,
            marker_color="seagreen",
            hovertemplate="Cache %{x}<br>Time: %{y}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(
            x=list(range(V)),
            y=video_presence,
            marker_color="firebrick",
            hovertemplate="Video %{x}<br>Caches: %{y}<extra></extra>",
        ),
        row=2,
        col=1,
    )
    if sum(data_dc) > 0:
        fig.add_trace(
            go.Bar(
                x=list(range(E)),
                y=data_dc,
                marker_color="black",
                hovertemplate="Endpoint %{x}<br>Source: DC<br>Volume: %{y} MB<extra></extra>",
            ),
            row=2,
            col=2,
        )
    for c in range(C):
        if sum(data_cache[c]) > 0:
            fig.add_trace(
                go.Bar(
                    x=list(range(E)),
                    y=data_cache[c],
                    hovertemplate=(
                        "Endpoint %{x}<br>Source: Cache "
                        + str(c)
                        + "<br>Volume: %{y} MB<extra></extra>"
                    ),
                ),
                row=2,
                col=2,
            )

    fig.update_layout(barmode="stack", height=800, showlegend=False, hovermode="closest")
    fig.update_xaxes(title_text="Cache ID", row=1, col=1)
    fig.update_xaxes(title_text="Cache ID", row=1, col=2)
    fig.update_xaxes(title_text="Video ID", row=2, col=1)
    fig.update_xaxes(title_text="Endpoint ID", row=2, col=2)

    out_file = "dashboard.html"
    fig.write_html(out_file)
    print(f"Graphes : {out_file}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "compare":
        similarity = calc_similarity(sys.argv[2], sys.argv[3])
        print(f"Similarity: {similarity:.2f}%")
    elif len(sys.argv) == 3:
        evaluate_and_plot(sys.argv[1], sys.argv[2])
    else:
        print("Usage plot: python stat.py input.in solution.out")
        print("Usage compare: python stat.py compare sol1.out sol2.out")
        sys.exit(1)
