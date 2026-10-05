"""
Statistiques sur une instance Hash Code 2017 (Streaming Videos).

Couvre :
  - videos : tailles, popularite, Zipf, Gini
  - connectivite : graphe biparti endpoint--cache, degres, densite, latences

Usage :
    python instance_stats.py
    python instance_stats.py generated/tiny_sanity.in
    python instance_stats.py --csv stats_instances.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import deque
from pathlib import Path

import numpy as np

from main import read_input

try:
    import instanceCreator as ic
except ImportError:
    ic = None


ROOT = Path(__file__).resolve().parent


def gini(values) -> float:
    """Coefficient de Gini dans [0, 1]. 0 = egalitaire, 1 = une video prend tout."""
    x = np.sort(np.asarray(values, dtype=float))
    total = x.sum()
    n = x.size
    if n == 0 or total <= 0:
        return 0.0
    return float((2.0 * np.dot(np.arange(1, n + 1), x)) / (n * total) - (n + 1) / n)


def _share(sorted_desc: np.ndarray, frac: float) -> float:
    total = float(sorted_desc.sum())
    if total <= 0:
        return 0.0
    k = max(1, int(np.ceil(frac * len(sorted_desc))))
    return float(sorted_desc[:k].sum() / total)


def _bipartite_components(E: int, C: int, endpoints) -> dict:
    """Composantes connexes du graphe non oriente endpoints -- caches."""
    adj = [[] for _ in range(E + C)]
    for e, ep in enumerate(endpoints):
        for cache_id in ep["caches"]:
            c = E + cache_id
            adj[e].append(c)
            adj[c].append(e)

    seen = [False] * (E + C)
    n_comp = 0
    n_nontrivial = 0
    largest = 0
    for start in range(E + C):
        if seen[start] or not adj[start]:
            continue
        n_comp += 1
        q = deque([start])
        seen[start] = True
        size = 0
        while q:
            node = q.popleft()
            size += 1
            for nxt in adj[node]:
                if not seen[nxt]:
                    seen[nxt] = True
                    q.append(nxt)
        largest = max(largest, size)
        if size > 1:
            n_nontrivial += 1
    isolated_nodes = sum(1 for i in range(E + C) if not adj[i])
    return {
        "composantes_non_vides": n_comp,
        "composantes_taille_gt1": n_nontrivial,
        "plus_grande_composante": largest,
        "sommets_isoles": isolated_nodes,
    }


def validate_limits(V, E, R, C, X, video_sizes, endpoints, requests) -> dict:
    """Reprend les bornes de instanceCreator / instanceValidator."""
    errors = []
    if ic is None:
        return {"ok": True, "errors": ["instanceCreator introuvable, validation sautee"]}

    checks = [
        (1 <= V <= ic.MAX_AUTHORISED_VIDEO_NUMBER, "V hors bornes"),
        (1 <= E <= ic.MAX_AUTHORISED_ENDPOINT_NUMBER, "E hors bornes"),
        (1 <= R <= ic.MAX_AUTHORISED_REQUEST_NUMBER, "R hors bornes"),
        (1 <= C <= ic.MAX_AUTHORISED_CACHE_NUMBER, "C hors bornes"),
        (1 <= X <= ic.MAX_AUTHORISED_CACHE_CAPACITY, "X hors bornes"),
    ]
    for ok, msg in checks:
        if not ok:
            errors.append(msg)

    for size in video_sizes:
        if not 1 <= size <= ic.MAX_AUTHORISED_VIDEO_SIZE:
            errors.append("taille video hors bornes")
            break

    lines_per_ep = [0] * E
    for video_id, endpoint_id, count in requests:
        if not 0 <= video_id < V:
            errors.append(f"video invalide {video_id}")
            break
        if not 0 <= endpoint_id < E:
            errors.append(f"endpoint invalide {endpoint_id}")
            break
        if count < 1:
            errors.append("count de requete < 1")
            break
        lines_per_ep[endpoint_id] += 1

    for n in lines_per_ep:
        if n > ic.MAX_AUTHORISED_REQUEST_PER_ENDPOINT:
            errors.append("trop de lignes de requetes pour un endpoint")
            break

    for ep in endpoints:
        dc = ep["datacenter_latency"]
        if not ic.MIN_AUTHORISED_SERVER_LATENCY <= dc <= ic.MAX_AUTHORISED_SERVER_LATENCY:
            errors.append("latence datacenter hors bornes")
            break
        for cache_id, lat in ep["caches"].items():
            if not 0 <= cache_id < C:
                errors.append(f"cache invalide {cache_id}")
                break
            if not 1 <= lat <= ic.MAX_AUTHORISED_CACHE_LATENCY:
                errors.append("latence cache hors bornes")
                break
            if lat >= dc:
                errors.append("latence cache >= datacenter")
                break
        else:
            continue
        break

    # Une seule fois chaque message (plusieurs endpoints peuvent echouer pareil)
    uniq = []
    for msg in errors:
        if msg not in uniq:
            uniq.append(msg)
    return {"ok": len(uniq) == 0, "errors": uniq}


def _heatmap(endpoints, E: int, C: int):
    if E * C > 5000 or E == 0 or C == 0:
        return None
    matrix = [[0] * C for _ in range(E)]
    for e, ep in enumerate(endpoints):
        for cache_id, lat in ep["caches"].items():
            if 0 <= cache_id < C:
                matrix[e][cache_id] = int(lat)
    return matrix


def analyze_instance(path: str | Path) -> dict:
    path = Path(path)
    V, E, R, C, X, video_sizes, endpoints, requests = read_input(str(path))
    sizes = np.asarray(video_sizes, dtype=np.int64)

    video_volume = np.zeros(V, dtype=np.int64)
    video_lines = np.zeros(V, dtype=np.int64)
    ep_volume = np.zeros(E, dtype=np.int64)
    ep_lines = np.zeros(E, dtype=np.int64)
    total_plays = 0
    for video_id, endpoint_id, count in requests:
        video_volume[video_id] += count
        video_lines[video_id] += 1
        ep_volume[endpoint_id] += count
        ep_lines[endpoint_id] += 1
        total_plays += count

    requested_mask = video_volume > 0
    n_requested = int(requested_mask.sum())
    ranked = np.sort(video_volume)[::-1]

    ep_degree = np.array([len(ep["caches"]) for ep in endpoints], dtype=np.int64)
    cache_degree = np.zeros(C, dtype=np.int64)
    cache_lats = []
    gains = []
    dc_lats = np.array([ep["datacenter_latency"] for ep in endpoints], dtype=np.int64)
    seen_pairs = set()
    for e, ep in enumerate(endpoints):
        dc = ep["datacenter_latency"]
        for cache_id, lat in ep["caches"].items():
            cache_degree[cache_id] += 1
            cache_lats.append(lat)
            gains.append(dc - lat)
            seen_pairs.add((e, cache_id))

    n_edges = len(seen_pairs)
    density = n_edges / (E * C) if E * C else 0.0
    cache_lats = np.asarray(cache_lats, dtype=np.int64) if cache_lats else np.array([], dtype=np.int64)
    gains = np.asarray(gains, dtype=np.int64) if gains else np.array([], dtype=np.int64)

    expansion = 0
    for _v, endpoint_id, _n in requests:
        expansion += ep_degree[endpoint_id]

    validation = validate_limits(V, E, R, C, X, video_sizes, endpoints, requests)
    components = _bipartite_components(E, C, endpoints)

    def _desc(arr):
        if arr.size == 0:
            return {"min": 0, "max": 0, "moyenne": 0.0, "mediane": 0.0, "std": 0.0}
        return {
            "min": int(arr.min()),
            "max": int(arr.max()),
            "moyenne": float(arr.mean()),
            "mediane": float(np.median(arr)),
            "std": float(arr.std()),
        }

    return {
        "fichier": path.name,
        "chemin": str(path),
        "source": _guess_source(path),
        "V": V,
        "E": E,
        "R": R,
        "C": C,
        "X": X,
        "valide": validation["ok"],
        "erreurs_validation": validation["errors"],
        "videos": {
            "tailles": _desc(sizes),
            "taille_totale_Mo": int(sizes.sum()),
            "demandees": n_requested,
            "jamais_demandees": V - n_requested,
            "part_demandees": n_requested / V if V else 0.0,
            "volume_total": int(total_plays),
            "volume_par_video": _desc(video_volume),
            "gini_popularite": gini(video_volume),
            "part_top_1pct": _share(ranked, 0.01),
            "part_top_5pct": _share(ranked, 0.05),
            "part_top_10pct": _share(ranked, 0.10),
            "part_top_10_videos": float(ranked[: min(10, V)].sum() / total_plays) if total_plays else 0.0,
            "lignes_par_video": _desc(video_lines),
        },
        "requetes": {
            "lignes": R,
            "volume_par_endpoint": _desc(ep_volume),
            "lignes_par_endpoint": _desc(ep_lines),
            "endpoints_sans_demande": int((ep_volume == 0).sum()),
        },
        "connectivite": {
            "aretes": n_edges,
            "densite": density,
            "degre_endpoint": _desc(ep_degree),
            "degre_cache": _desc(cache_degree),
            "endpoints_isoles": int((ep_degree == 0).sum()),
            "caches_inutilises": int((cache_degree == 0).sum()),
            "expansion_requete_x_cache": int(expansion),
            "latence_datacenter": _desc(dc_lats),
            "latence_cache": _desc(cache_lats),
            "gain_ms_possible": _desc(gains),
            **components,
        },
        "_arrays": {
            "sizes": sizes,
            "video_volume": video_volume,
            "ep_volume": ep_volume,
            "ep_degree": ep_degree,
            "cache_degree": cache_degree,
            "dc_lats": dc_lats,
            "cache_lats": cache_lats,
            "gains": gains,
        },
        "top_videos": [
            {
                "id": int(vid),
                "taille": int(sizes[vid]),
                "volume": int(video_volume[vid]),
            }
            for vid in np.argsort(video_volume)[::-1][:15]
            if video_volume[vid] > 0
        ],
        "heatmap": _heatmap(endpoints, E, C),
    }


def _guess_source(path: Path) -> str:
    name = path.name.lower()
    if path.parent.name == "generated":
        return "generate_instances.py"
    if "dejavu" in name:
        return "instanceCreator.dejaVu"
    if "universal" in name or "lambda" in name:
        return "instanceCreator.universalLambda"
    if name == "me_at_the_zoo.in":
        return "officiel Hash Code"
    return "autre"


CREATOR_INSTANCES = ("custom_dejavu42.in", "custom_universallambda42.in")


def discover_instances(root: Path | None = None) -> list[Path]:
    """Uniquement les deux instances d'instanceCreator.py."""
    root = root or ROOT
    paths = []
    for name in CREATOR_INSTANCES:
        path = root / name
        if path.is_file():
            paths.append(path)
    return paths


def summary_row(stats: dict) -> dict:
    v = stats["videos"]
    c = stats["connectivite"]
    return {
        "fichier": stats["fichier"],
        "source": stats["source"],
        "valide": stats["valide"],
        "V": stats["V"],
        "E": stats["E"],
        "R": stats["R"],
        "C": stats["C"],
        "X": stats["X"],
        "videos_demandees": v["demandees"],
        "gini": round(v["gini_popularite"], 3),
        "top10pct": round(v["part_top_10pct"], 3),
        "densite": round(c["densite"], 3),
        "deg_ep_moy": round(c["degre_endpoint"]["moyenne"], 2),
        "ep_isoles": c["endpoints_isoles"],
        "caches_vides": c["caches_inutilises"],
        "composantes": c["composantes_non_vides"],
        "expansion": c["expansion_requete_x_cache"],
    }


def drop_arrays(stats: dict) -> dict:
    clean = dict(stats)
    clean.pop("_arrays", None)
    return clean


def print_report(stats: dict) -> None:
    v = stats["videos"]
    c = stats["connectivite"]
    q = stats["requetes"]
    print(f"=== {stats['fichier']}  ({stats['source']}) ===")
    print(f"  V={stats['V']}  E={stats['E']}  R={stats['R']}  C={stats['C']}  X={stats['X']}")
    print(f"  validation : {'OK' if stats['valide'] else 'ECHEC'} {stats['erreurs_validation']}")
    print("  -- videos --")
    print(
        f"  tailles Mo : min={v['tailles']['min']}  max={v['tailles']['max']}  "
        f"moy={v['tailles']['moyenne']:.1f}"
    )
    print(
        f"  demandees {v['demandees']}/{stats['V']}  "
        f"jamais {v['jamais_demandees']}  Gini={v['gini_popularite']:.3f}"
    )
    print(
        f"  part trafic top 10% videos = {100 * v['part_top_10pct']:.1f}%  "
        f"top 10 videos = {100 * v['part_top_10_videos']:.1f}%"
    )
    print("  -- requetes --")
    print(
        f"  volume total {v['volume_total']}  "
        f"lignes/endpoint moy={q['lignes_par_endpoint']['moyenne']:.1f}"
    )
    print("  -- connectivite --")
    print(
        f"  aretes {c['aretes']}  densite {100 * c['densite']:.1f}%  "
        f"deg endpoint moy={c['degre_endpoint']['moyenne']:.2f}  "
        f"deg cache moy={c['degre_cache']['moyenne']:.2f}"
    )
    print(
        f"  endpoints isoles {c['endpoints_isoles']}  "
        f"caches inutilises {c['caches_inutilises']}  "
        f"composantes {c['composantes_non_vides']}"
    )
    print(
        f"  latence DC moy={c['latence_datacenter']['moyenne']:.0f} ms  "
        f"cache moy={c['latence_cache']['moyenne']:.0f} ms  "
        f"gain possible moy={c['gain_ms_possible']['moyenne']:.0f} ms"
    )
    print()


def plot_instance(stats: dict, out_dir: Path | None = None):
    import matplotlib.pyplot as plt

    arrays = stats["_arrays"]
    name = stats["fichier"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    fig.suptitle(f"Statistiques — {name}", fontsize=13)

    axes[0, 0].hist(arrays["sizes"], bins=min(30, max(5, stats["V"] // 3)), color="#4C72B0", edgecolor="white")
    axes[0, 0].set_title("Tailles des videos (Mo)")
    axes[0, 0].set_xlabel("Mo")
    axes[0, 0].set_ylabel("nombre de videos")

    vols = np.sort(arrays["video_volume"])[::-1]
    ranks = np.arange(1, len(vols) + 1)
    positive = vols > 0
    if positive.any():
        axes[0, 1].loglog(ranks[positive], vols[positive], marker="o", linestyle="none", markersize=3)
    axes[0, 1].set_title("Popularite (Zipf) rang vs volume")
    axes[0, 1].set_xlabel("rang")
    axes[0, 1].set_ylabel("requetes")

    cum = np.cumsum(vols) / vols.sum() if vols.sum() else vols
    axes[0, 2].plot(np.linspace(0, 1, len(cum), endpoint=True), cum, color="#C44E52")
    axes[0, 2].plot([0, 1], [0, 1], "--", color="gray")
    axes[0, 2].set_title(f"Lorenz popularite (Gini={stats['videos']['gini_popularite']:.2f})")
    axes[0, 2].set_xlabel("part des videos")
    axes[0, 2].set_ylabel("part du trafic")

    axes[1, 0].bar(np.arange(len(arrays["ep_degree"])), arrays["ep_degree"], color="#55A868")
    axes[1, 0].set_title("Degre des endpoints (# caches)")
    axes[1, 0].set_xlabel("endpoint")
    axes[1, 0].set_ylabel("caches relies")

    axes[1, 1].bar(np.arange(len(arrays["cache_degree"])), arrays["cache_degree"], color="#DD8452")
    axes[1, 1].set_title("Degre des caches (# endpoints)")
    axes[1, 1].set_xlabel("cache")
    axes[1, 1].set_ylabel("endpoints relies")

    if arrays["dc_lats"].size and arrays["cache_lats"].size:
        axes[1, 2].hist(arrays["dc_lats"], bins=12, alpha=0.6, label="datacenter")
        axes[1, 2].hist(arrays["cache_lats"], bins=12, alpha=0.6, label="cache")
        axes[1, 2].legend()
    axes[1, 2].set_title("Distribution des latences (ms)")
    axes[1, 2].set_xlabel("ms")

    fig.tight_layout()
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"{Path(name).stem}_stats.png"
        fig.savefig(dest, dpi=120)
        plt.close(fig)
        return dest
    return fig


def main():
    parser = argparse.ArgumentParser(description="Statistiques d'instances Hash Code 2017")
    parser.add_argument(
        "files",
        nargs="*",
        help=".in a analyser (defaut : custom_dejavu42.in et custom_universallambda42.in)",
    )
    parser.add_argument("--csv", type=Path, help="exporter le tableau resume")
    parser.add_argument("--json", type=Path, help="exporter le detail JSON")
    parser.add_argument("--plots", type=Path, help="dossier PNG (un graphe par instance)")
    args = parser.parse_args()

    paths = [Path(p) for p in args.files] if args.files else discover_instances()
    if not paths:
        print("Aucune instance .in trouvee.")
        return

    rows = []
    details = []
    for path in paths:
        stats = analyze_instance(path)
        print_report(stats)
        rows.append(summary_row(stats))
        details.append(drop_arrays(stats))
        if args.plots:
            dest = plot_instance(stats, args.plots)
            print(f"  figure : {dest}")

    print("--- resume ---")
    headers = list(rows[0].keys())
    widths = {h: max(len(h), max(len(str(r[h])) for r in rows)) for h in headers}
    print("  ".join(h.ljust(widths[h]) for h in headers))
    for row in rows:
        print("  ".join(str(row[h]).ljust(widths[h]) for h in headers))

    if args.csv:
        with args.csv.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        print(f"CSV : {args.csv}")

    if args.json:
        args.json.write_text(json.dumps(details, indent=2), encoding="utf-8")
        print(f"JSON : {args.json}")


if __name__ == "__main__":
    main()
