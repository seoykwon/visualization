#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export all station-to-station (역→역) travel times (Dijkstra) to CSV
USING ONLY: merged_clean.csv (for ride edges) + inferred transfers.

- Nodes = (station, line)
- Ride edges: read from merged_clean.csv
  * Supports two schemas:
    (A) Edge list:  line, from_station, to_station, seconds|mmss|소요시간
    (B) Sequential: 호선|line, 역명|station, 소요시간|seconds|mmss  (연속 역 연결)
- Transfer edges: for each station, connect all its (station,line) nodes with
  weight=--transfer-sec (default 180s)

Inputs (same folder):
  - merged_clean.csv
  - (optional) station_dictionary_updated.json  # only for name checks if you want

Outputs:
  - station_pairs_all_from_merged.csv  (src_station,dst_station,seconds,minutes)
  - station_pairs_from_<역명>.csv      (if --source-station provided)

Usage:
  python3 export_station_pairs_from_merged.py
  python3 export_station_pairs_from_merged.py --transfer-sec 180 --source-station 사당
"""
import argparse, csv, json, re, heapq
from pathlib import Path
from collections import defaultdict

BASE = Path(".")
MERGED = BASE / "merged_clean.csv"
ST_DICT = BASE / "station_dictionary_updated.json"  # optional


def open_csv_kr(path: Path):
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            f = open(path, "r", encoding=enc, newline="")
            f.readline(); f.seek(0)
            return f
        except Exception:
            pass
    raise RuntimeError(f"Failed to open: {path} with common encodings")


def mmss_to_sec(s):
    if s is None:
        return None
    s = str(s).strip()
    m = re.match(r"^(\d+):(\d{2})$", s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    try:
        return int(round(float(s) * 60))
    except Exception:
        return None


def norm_colnames(names):
    # lower + strip
    return [str(c).strip().lower() for c in names]


def pick_col(names, candidates):
    """Return first matching column name (case-insensitive) if present."""
    low = norm_colnames(names)
    for cand in candidates:
        if cand in low:
            return names[low.index(cand)]
    return None


def load_ride_edges_from_merged(merged_path: Path):
    """
    Returns:
      edges: list of (line, from_station, to_station, seconds)
      station_to_lines: dict[station] -> set[line]
    """
    edges = []
    station_to_lines = defaultdict(set)

    with open_csv_kr(merged_path) as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames or []
        # Try edge-list schema first
        col_line = pick_col(cols, ["line", "호선", "line_id", "노선", "노선명"])
        col_from = pick_col(cols, ["from_station", "출발역", "from", "시작역", "전역_clean"])
        col_to   = pick_col(cols, ["to_station", "도착역", "to", "끝역", "역명_clean"])
        col_sec  = pick_col(cols, ["seconds", "sec", "time_sec", "duration_s", "소요초", "소요시간"])
        col_mmss = pick_col(cols, ["mmss", "소요시간", "time", "duration"])

        if col_line and col_from and col_to and (col_sec or col_mmss):
            # Edge list mode
            for row in rdr:
                ln = str(row[col_line]).strip()
                a  = str(row[col_from]).strip()
                b  = str(row[col_to]).strip()
                if not a or not b or not ln:
                    continue
                if col_sec and row[col_sec] not in (None, ""):
                    try:
                        sec = int(row[col_sec])
                    except Exception:
                        sec = mmss_to_sec(row[col_sec])
                else:
                    sec = mmss_to_sec(row[col_mmss])
                if not sec or sec <= 0:
                    continue
                edges.append((ln, a, b, int(sec)))
                station_to_lines[a].add(ln); station_to_lines[b].add(ln)

        else:
            # Sequential mode: need line + station + (seconds or mmss)
            col_line = pick_col(cols, ["line", "호선", "line_id", "노선", "노선명"])
            col_st   = pick_col(cols, ["역명", "station", "station_name", "name"])
            col_sec  = pick_col(cols, ["seconds", "sec", "time_sec", "duration_s"])
            col_mmss = pick_col(cols, ["mmss", "소요시간", "time", "duration"])
            col_cum  = pick_col(cols, ["호선별누계(km)", "누계", "누계km", "cumulative_km"])

            if not (col_line and col_st and (col_sec or col_mmss)):
                raise RuntimeError("merged_clean.csv: Unable to detect schema. Need either edge-list or sequential columns.")

            prev = {}  # line -> (prev_station, prev_cum)
            for row in rdr:
                ln = str(row[col_line]).strip()
                st = str(row[col_st]).strip()
                station_to_lines[st].add(ln)

                sec = None
                if col_sec and row[col_sec] not in (None, ""):
                    try:
                        sec = int(row[col_sec])
                    except Exception:
                        sec = mmss_to_sec(row[col_sec])
                else:
                    sec = mmss_to_sec(row[col_mmss])

                cum = None
                if col_cum and row.get(col_cum):
                    try:
                        cum = float(row[col_cum])
                    except Exception:
                        cum = None

                if ln in prev:
                    pst, pc = prev[ln]
                    # if cumulative drops -> break segment
                    if sec and sec > 0 and not (pc is not None and cum is not None and cum < pc):
                        edges.append((ln, pst, st, int(sec)))
                prev[ln] = (st, cum)

    # Deduplicate edges (keep undirected unique)
    seen = set()
    dedup = []
    for ln, a, b, sec in edges:
        key = (ln, a, b, sec)
        rev = (ln, b, a, sec)
        if key in seen or rev in seen:
            continue
        seen.add(key); seen.add(rev)
        dedup.append((ln, a, b, sec))
    return dedup, station_to_lines


def build_graph_from_merged(merged_path: Path, transfer_sec: int):
    # Node indexing for (station, line)
    node_id = {}
    id_node = []

    def get_id(st, ln):
        key = (st, ln)
        if key not in node_id:
            node_id[key] = len(id_node)
            id_node.append(key)
        return node_id[key]

    adj = defaultdict(list)
    edges, station_to_lines = load_ride_edges_from_merged(merged_path)

    # Ride edges (undirected)
    for ln, a, b, sec in edges:
        u = get_id(a, ln); v = get_id(b, ln)
        adj[u].append((v, int(sec))); adj[v].append((u, int(sec)))

    # Transfer edges (within same station across different lines)
    node_lookup = {(st, ln): i for i, (st, ln) in enumerate(id_node)}
    for st, lines in station_to_lines.items():
        ls = sorted(list(lines))
        for i in range(len(ls)):
            for j in range(i + 1, len(ls)):
                u = node_lookup.get((st, ls[i]))
                v = node_lookup.get((st, ls[j]))
                if u is None or v is None:
                    continue
                adj[u].append((v, transfer_sec))
                adj[v].append((u, transfer_sec))

    return node_id, id_node, adj


def dijkstra_multi(adj, sources, V):
    INF = 10 ** 15
    dist = [INF] * V
    pq = []
    for s in sources:
        dist[s] = 0
        heapq.heappush(pq, (0, s))
    while pq:
        d, u = heapq.heappop(pq)
        if d != dist[u]:
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def to_minutes(sec: int) -> int:
    """Return integer minutes from seconds (floor). Change to round/ceil if desired."""
    return int(sec) // (60 * 60)


def main():
    ap = argparse.ArgumentParser(description="Export station→station travel times using merged_clean.csv")
    ap.add_argument("--merged-csv", type=Path, default=MERGED)
    ap.add_argument("--transfer-sec", type=int, default=180, help="환승 기본 초(기본 180)")
    ap.add_argument("--out-all", type=Path, default=BASE / "station_pairs_all_from_merged.csv")
    ap.add_argument("--source-station", type=str, default=None, help="특정 출발역 CSV도 추가 생성")
    args = ap.parse_args()

    node_id, id_node, adj = build_graph_from_merged(args.merged_csv, args.transfer_sec)
    V = len(id_node)

    # Station index
    station_to_nodes = defaultdict(list)
    for nid, (st, ln) in enumerate(id_node):
        station_to_nodes[st].append(nid)
    stations = sorted(station_to_nodes.keys())

    # 1) 전체 역→역 CSV (minutes 컬럼 포함)
    with open(args.out_all, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["src_station", "dst_station", "seconds", "minutes"])  # minutes 로 변경
        for s in stations:
            dist = dijkstra_multi(adj, station_to_nodes[s], V)
            for t, nodes in station_to_nodes.items():
                if t == s:
                    continue
                best_sec = min(dist[n] for n in nodes)
                if best_sec < 10 ** 15:
                    w.writerow([s, t, int(best_sec), to_minutes(best_sec)])
    print(f"[OK] Wrote {args.out_all.name}  (stations={len(stations)}, nodes={V}, transfer={args.transfer_sec}s)")

    # 2) 특정 출발역 CSV (옵션)
    if args.source_station and args.source_station in station_to_nodes:
        out_single = BASE / f"station_pairs_from_{args.source_station}.csv"
        with open(out_single, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["src_station", "dst_station", "seconds", "minutes"])  # minutes 로 변경
            dist = dijkstra_multi(adj, station_to_nodes[args.source_station], V)
            for t, nodes in station_to_nodes.items():
                if t == args.source_station:
                    continue
                best_sec = min(dist[n] for n in nodes)
                if best_sec < 10 ** 15:
                    w.writerow([args.source_station, t, int(best_sec), to_minutes(best_sec)])
        print(f"[OK] Wrote {out_single.name}")


if __name__ == "__main__":
    main()
