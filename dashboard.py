"""
Dashboard web : datasets, remplissage greedy, analyse de score.

    python dashboard.py
    -> http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import re
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import numpy as np

import instanceCreator as ic
from instance_stats import analyze_instance, drop_arrays, summary_row
from main import read_input, solve, write_output

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
CACHE = ROOT / "web_cache"
PORT = 8765
CACHE_VERSION = 5

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
            if path.stem in ("large_fastfill", "kittens"):
                continue
            rows.append(_peek(path, "generated"))
    instances = ROOT / "instances"
    if instances.is_dir():
        for path in sorted(instances.glob("*.in")):
            rows.append(_peek(path, "instances"))
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


def calculate_score(endpoints, requests, caches):
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


def _solution_details(C, X, V, E, sizes, endpoints, requests, caches):
    fill = [sum(sizes[v] for v in videos) for videos in caches]
    occupation = [round(100.0 * f / X, 1) if X else 0.0 for f in fill]
    n_videos = [len(videos) for videos in caches]
    presence = [0] * V
    for videos in caches:
        for v in videos:
            presence[v] += 1
    copies = sum(presence)
    unique = sum(1 for n in presence if n > 0)
    extra = copies - unique
    duplicated_videos = sum(1 for n in presence if n >= 2)
    max_copies = max(presence) if presence else 0
    hist = [0] * (max_copies + 1)
    for n in presence:
        if n:
            hist[n] += 1
    mo_stored = sum(fill)
    mo_unique = sum(sizes[v] for v, n in enumerate(presence) if n > 0)
    mo_extra = mo_stored - mo_unique

    time_saved = [0] * C
    data_dc = [0] * E
    data_from_cache = [0] * C
    stack_ok = E * (C + 1) <= 4000
    data_cache_ep = [[0] * E for _ in range(C)] if stack_ok else None
    useful = set()
    for video_id, endpoint_id, count in requests:
        ep = endpoints[endpoint_id]
        dc = ep["datacenter_latency"]
        best = dc
        best_c = -1
        for cache_id, lat in ep["caches"].items():
            if video_id in caches[cache_id] and lat < best:
                best = lat
                best_c = cache_id
        vol = sizes[video_id] * count
        if best_c != -1:
            time_saved[best_c] += count * (dc - best)
            data_from_cache[best_c] += vol
            useful.add((best_c, video_id))
            if data_cache_ep is not None:
                data_cache_ep[best_c][endpoint_id] += vol
        else:
            data_dc[endpoint_id] += vol

    wasted = 0
    for cache_id, videos in enumerate(caches):
        for video_id in videos:
            if (cache_id, video_id) not in useful:
                wasted += 1

    matrix = None
    if V * C <= 2500:
        matrix = [[1 if v in caches[c] else 0 for v in range(V)] for c in range(C)]

    dup_videos = [
        {"v": i, "copies": n, "taille": int(sizes[i])}
        for i, n in enumerate(presence)
        if n >= 2
    ]
    dup_videos.sort(key=lambda row: (-row["copies"], -row["taille"]))

    return {
        "remplissage_Mo": fill,
        "occupation_pct": occupation,
        "videos_par_cache": n_videos,
        "moyenne_occupation_pct": round(sum(occupation) / C, 2) if C else 0,
        "copies": copies,
        "videos_uniques_en_cache": unique,
        "copies_en_trop": extra,
        "taux_duplication": round(extra / copies, 4) if copies else 0,
        "taux_videos_dupliquees": round(duplicated_videos / unique, 4) if unique else 0,
        "copies_moyennes": round(copies / unique, 3) if unique else 0,
        "videos_dupliquees": duplicated_videos,
        "histogramme_copies": hist,
        "mo_stockes": mo_stored,
        "mo_uniques": mo_unique,
        "mo_dupliques": mo_extra,
        "taux_mo_dupliques": round(mo_extra / mo_stored, 4) if mo_stored else 0,
        "copies_inutiles": wasted,
        "taux_copies_inutiles": round(wasted / copies, 4) if copies else 0,
        "gain_par_cache": time_saved,
        "volume_dc": data_dc if E <= 400 else [],
        "volume_par_cache": data_from_cache,
        "volume_cache_ep": data_cache_ep,
        "presence": presence if V <= 400 else [],
        "dupliquees": dup_videos[:40],
        "matrice": matrix,
    }


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
    write_output(str(path.with_suffix(".out")), caches)
    score = calculate_score(endpoints, requests, caches)
    elapsed = time.perf_counter() - started

    hit_volume = 0
    for video_id, endpoint_id, count in requests:
        ep = endpoints[endpoint_id]
        for cache_id, lat in ep["caches"].items():
            if video_id in caches[cache_id] and lat < ep["datacenter_latency"]:
                hit_volume += count
                break

    n_videos = [len(videos) for videos in caches]
    details = _solution_details(C, X, V, E, sizes, endpoints, requests, caches)

    steps = []
    saved = 0
    used = [0] * C
    curve = []
    densities = []
    keep_every = max(1, len(trace) // 450) if trace else 1
    for i, (cache_id, video_id, size, left, benefit, _used_total) in enumerate(trace, start=1):
        used[cache_id] += size
        saved += benefit
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
        "steps": steps,
        "courbe": curve,
        "densites": densities[:500],
    }
    data.update(details)
    CACHE.mkdir(exist_ok=True)
    cache_file.write_text(json.dumps(data), encoding="utf-8")
    with _lock:
        _solve_mem[key] = data
    return data


def _safe_stem(name: str) -> str:
    stem = Path(str(name)).stem.strip()
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")
    return stem or "custom"


def generate_from_creator(raw: dict) -> Path:
    kind = str(raw.get("generateur") or "dejaVu")
    if kind not in ic.generator:
        kind = "dejaVu"

    def _int(key, default, lo, hi):
        try:
            value = int(raw.get(key, default))
        except (TypeError, ValueError):
            value = default
        return max(lo, min(hi, value))

    V = _int("V", 200, 2, ic.MAX_AUTHORISED_VIDEO_NUMBER)
    E = _int("E", 20, 1, ic.MAX_AUTHORISED_ENDPOINT_NUMBER)
    R = _int("R", 800, 1, ic.MAX_AUTHORISED_REQUEST_NUMBER)
    C = _int("C", 10, 1, ic.MAX_AUTHORISED_CACHE_NUMBER)
    X = _int("X", 400, 1, ic.MAX_AUTHORISED_CACHE_CAPACITY)
    seed = _int("seed", 42, 0, 1_000_000)
    vmin = _int("V_min", 4, 1, ic.MAX_AUTHORISED_VIDEO_SIZE)
    vmax = _int("V_max", 110, 1, ic.MAX_AUTHORISED_VIDEO_SIZE)
    if vmax <= vmin:
        vmax = min(ic.MAX_AUTHORISED_VIDEO_SIZE, vmin + 1)
    if kind == "dejaVu":
        C = max(C, 4)
        R = max(R, 20 * E)
        text = ic.generator["dejaVu"](
            E=E, V=V, R=R, V_min_size=vmin, V_max_size=vmax, C=C, X=X, seed=seed
        )
    else:
        text = ic.generator["universalLambda"](
            E=E,
            V=V,
            C=C,
            X=X,
            seed=seed,
            videoSizeLambda=lambda idV, rng: max(
                1, ic.MAX_AUTHORISED_VIDEO_SIZE - idV + rng.randint(0, idV + 1)
            ),
            requestLambda=lambda idE, idV, rng: (
                rng.randint(8000, 12001)
                if (idE % 2, idV % 2) == (0, 1)
                else rng.randint(-100, 101)
            ),
            dcLambda=lambda idE, rng: max(
                2,
                min(
                    (idE + ic.MAX_AUTHORISED_SERVER_LATENCY) // 2 + rng.randint(-100, 100),
                    ic.MAX_AUTHORISED_SERVER_LATENCY,
                ),
            ),
            connectionLambda=lambda idE, idC, dcL, rng: rng.randint(
                -300, min(ic.MAX_AUTHORISED_CACHE_LATENCY, max(2, dcL) - 1)
            ),
        )
    if not text.endswith("\n"):
        text += "\n"
    folder = ROOT / "instances"
    folder.mkdir(exist_ok=True)
    path = folder / f"{_safe_stem(raw.get('nom') or 'custom_' + kind)}.in"
    path.write_text(text, encoding="utf-8")
    return path


def run_pipeline(raw: dict) -> dict:
    path = generate_from_creator(raw)
    with _lock:
        _stats_mem.pop(str(path), None)
        _solve_mem.pop(str(path), None)
    for suffix in (
        f"{path.stem}.stats.v{CACHE_VERSION}.json",
        f"{path.stem}.solve.v{CACHE_VERSION}.json",
    ):
        cache_file = CACHE / suffix
        if cache_file.is_file():
            cache_file.unlink()
    stats = get_stats(path)
    solve_data = get_solve(path)
    return {
        "dataset": _peek(path, "instanceCreator"),
        "stats": stats,
        "solve": solve_data,
    }


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

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/pipeline":
            try:
                self._send_json(run_pipeline(self._read_json()))
            except Exception as exc:
                self._send_json({"erreur": str(exc)}, 400)
            return
        self._send_json({"erreur": "inconnu"}, 404)

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
            try:
                self._send_json(get_solve(target))
            except Exception as exc:
                self._send_json({"erreur": str(exc)}, 500)
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
