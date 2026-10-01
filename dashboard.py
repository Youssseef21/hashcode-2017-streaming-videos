"""
Dashboard web : datasets, remplissage greedy, analyse de score.

    python dashboard.py
    -> http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from instance_stats import analyze_instance, drop_arrays, summary_row
from main import read_input, solve
from score import calculate_score

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
CACHE = ROOT / "web_cache"
PORT = 8765
CACHE_VERSION = 3

_stats_mem = {}
_solve_mem = {}
_lock = threading.Lock()


def _datasets() -> list[dict]:
    rows = []
    for name in ("custom_dejavu42.in", "custom_universallambda42.in"):
        path = ROOT / name
        if path.is_file():
            rows.append(_peek(path, "instanceCreator"))
    zoo = ROOT / "me_at_the_zoo.in"
    if zoo.is_file():
        rows.append(_peek(zoo, "officiel"))
    generated = ROOT / "generated"
    if generated.is_dir():
        for path in sorted(generated.glob("*.in")):
            if path.stem == "large_fastfill":
                continue
            rows.append(_peek(path, "generate_instances"))
    return rows


def _peek(path: Path, family: str) -> dict:
    with path.open("r", encoding="utf-8") as file:
        V, E, R, C, X = map(int, file.readline().split())
    return {
        "id": _did(path),
        "fichier": path.name,
        "chemin": str(path.relative_to(ROOT)).replace("\\", "/"),
        "famille": family,
        "V": V,
        "E": E,
        "R": R,
        "C": C,
        "X": X,
        "lourd": R >= 50_000 or V >= 5_000,
    }


def _did(path: Path) -> str:
    rel = path.resolve().relative_to(ROOT.resolve()).as_posix()
    return rel.replace("/", "__")


def _path_from_id(dataset_id: str) -> Path | None:
    dataset_id = unquote(dataset_id)
    root = ROOT.resolve()
    for row in _datasets():
        if row["id"] != dataset_id:
            continue
        path = (ROOT / row["chemin"]).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            return None
        return path if path.is_file() else None
    return None


def _jsonable_stats(stats: dict) -> dict:
    arrays = stats.get("_arrays", {})
    sizes = arrays.get("sizes")
    volume = arrays.get("video_volume")
    payload = drop_arrays(stats)
    payload["resume"] = summary_row(stats)
    payload["graphiques"] = {
        "tailles": _sample_list(sizes, 8000),
        "zipf": _zipf(volume),
        "lorenz": _lorenz(volume),
        "degre_endpoint": _tolist(arrays.get("ep_degree")),
        "degre_cache": _tolist(arrays.get("cache_degree")),
        "volume_endpoint": _tolist(arrays.get("ep_volume")),
        "latence_dc": _tolist(arrays.get("dc_lats")),
        "latence_cache": _sample_list(arrays.get("cache_lats"), 8000),
        "gains": _sample_list(arrays.get("gains"), 8000),
        "scatter": _scatter(sizes, volume),
    }
    return payload


def _tolist(arr):
    if arr is None:
        return []
    return arr.tolist()


def _sample_list(arr, cap: int):
    if arr is None:
        return []
    if arr.size <= cap:
        return arr.tolist()
    step = max(1, arr.size // cap)
    return arr[::step].tolist()


def _lorenz(volume) -> list:
    if volume is None or volume.size == 0:
        return []
    ranked = np.sort(volume)[::-1]
    total = float(ranked.sum())
    if total <= 0:
        return []
    cum = np.cumsum(ranked) / total
    n = min(100, cum.size)
    idx = np.linspace(0, cum.size - 1, n).astype(int)
    return [{"x": float(i / max(cum.size - 1, 1)), "y": float(cum[i])} for i in idx]


def _scatter(sizes, volume) -> list:
    if sizes is None or volume is None:
        return []
    points = []
    for i, (sz, vol) in enumerate(zip(sizes.tolist(), volume.tolist())):
        if vol > 0:
            points.append((int(i), int(sz), int(vol)))
    points.sort(key=lambda p: p[2], reverse=True)
    points = points[: min(250, len(points))]
    return [{"v": a, "size": b, "vol": c} for a, b, c in points]


def _zipf(volume) -> list:
    if volume is None or volume.size == 0:
        return []
    ranked = sorted((int(x) for x in volume if x > 0), reverse=True)
    return ranked[: min(120, len(ranked))]


def get_stats(path: Path) -> dict:
    key = str(path)
    with _lock:
        if key in _stats_mem:
            return _stats_mem[key]
    cache_file = CACHE / f"{path.stem}.stats.v{CACHE_VERSION}.json"
    if cache_file.is_file() and cache_file.stat().st_mtime >= path.stat().st_mtime:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        with _lock:
            _stats_mem[key] = data
        return data
    stats = analyze_instance(path)
    data = _jsonable_stats(stats)
    CACHE.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    with _lock:
        _stats_mem[key] = data
    return data


def get_solve(path: Path) -> dict:
    key = str(path)
    with _lock:
        if key in _solve_mem:
            return _solve_mem[key]
    cache_file = CACHE / f"{path.stem}.solve.v{CACHE_VERSION}.json"
    if cache_file.is_file() and cache_file.stat().st_mtime >= path.stat().st_mtime:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        with _lock:
            _solve_mem[key] = data
        return data

    started = time.perf_counter()
    V, E, R, C, X, sizes, endpoints, requests = read_input(str(path))
    total_plays = sum(n for _v, _e, n in requests)
    ceiling_saved = 0
    for video_id, endpoint_id, count in requests:
        ep = endpoints[endpoint_id]
        dc = ep["datacenter_latency"]
        best = dc
        for lat in ep["caches"].values():
            if lat < best:
                best = lat
        ceiling_saved += (dc - best) * count
    ceiling_score = (ceiling_saved * 1000) // total_plays if total_plays else 0

    trace = []
    caches = solve(C, X, sizes, endpoints, requests, verbose=False, trace=trace)
    score = calculate_score(endpoints, requests, caches)
    elapsed = time.perf_counter() - started

    hit_volume = 0
    for video_id, endpoint_id, count in requests:
        ep = endpoints[endpoint_id]
        for cache_id, lat in ep["caches"].items():
            if video_id in caches[cache_id] and lat < ep["datacenter_latency"]:
                hit_volume += count
                break

    fill = [sum(sizes[v] for v in videos) for videos in caches]
    n_videos = [len(videos) for videos in caches]
    benefit_by_cache = [0] * C

    steps = []
    saved = 0
    used = [0] * C
    curve = []
    densities = []
    keep_every = max(1, len(trace) // 450) if trace else 1
    for i, (cache_id, video_id, size, left, benefit, _used_total) in enumerate(trace, start=1):
        used[cache_id] += size
        saved += benefit
        benefit_by_cache[cache_id] += benefit
        dens = benefit / size if size else 0
        live_score = (saved * 1000) // total_plays if total_plays else 0
        if i == 1 or i == len(trace) or i % keep_every == 0:
            steps.append({
                "n": i,
                "c": cache_id,
                "v": video_id,
                "size": size,
                "left": left,
                "score": live_score,
                "gain": benefit,
                "densite": round(dens, 2),
                "used": list(used),
            })
            curve.append({
                "n": i,
                "score": live_score,
                "fill_pct": 100.0 * sum(used) / (X * C) if X * C else 0,
                "gain": benefit,
                "densite": round(dens, 2),
            })
            densities.append(round(dens, 4))

    data = {
        "fichier": path.name,
        "V": V,
        "E": E,
        "R": R,
        "C": C,
        "X": X,
        "score": score,
        "score_plafond": ceiling_score,
        "part_plafond": round(score / ceiling_score, 4) if ceiling_score else 0,
        "ms_par_requete": round(saved / total_plays, 3) if total_plays else 0,
        "volume_requetes": total_plays,
        "volume_avec_cache": hit_volume,
        "part_requetes_cachees": round(hit_volume / total_plays, 4) if total_plays else 0,
        "ms_economisees": saved,
        "temps_s": round(elapsed, 3),
        "placements": len(trace),
        "caches_utilises": sum(1 for n in n_videos if n),
        "remplissage_Mo": fill,
        "videos_par_cache": n_videos,
        "gain_par_cache": benefit_by_cache,
        "occupation_pct": [round(100.0 * f / X, 1) if X else 0 for f in fill],
        "steps": steps,
        "courbe": curve,
        "densites": densities[:500],
        "moyenne_occupation_pct": round(100.0 * sum(fill) / (X * C), 2) if X * C else 0,
    }
    CACHE.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    with _lock:
        _solve_mem[key] = data
    return data


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[dashboard] {self.address_string()} {fmt % args}")

    def _send_json(self, payload, code=200):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/datasets":
            self._send_json({"datasets": _datasets()})
            return
        if path.startswith("/api/stats/"):
            dataset_id = path[len("/api/stats/") :]
            target = _path_from_id(dataset_id)
            if target is None:
                self._send_json({"erreur": "dataset inconnu"}, 404)
                return
            self._send_json(get_stats(target))
            return
        if path.startswith("/api/solve/"):
            dataset_id = path[len("/api/solve/") :]
            target = _path_from_id(dataset_id)
            if target is None:
                self._send_json({"erreur": "dataset inconnu"}, 404)
                return
            self._send_json(get_solve(target))
            return
        if path in ("/", ""):
            self.path = "/index.html"
        return SimpleHTTPRequestHandler.do_GET(self)


def main():
    WEB.mkdir(exist_ok=True)
    CACHE.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Dashboard : http://127.0.0.1:{PORT}", flush=True)
    print("Ctrl+C pour arreter.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArret.")
        server.server_close()


if __name__ == "__main__":
    main()
