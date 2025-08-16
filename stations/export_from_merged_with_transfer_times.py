
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export all station-to-station (역→역) travel times (Dijkstra) to CSV
USING ONLY:
  - merged_clean.csv       (ride edges)
  - transfer_times.csv     (transfer edges: per-station or line-pair overrides)
"""
import argparse, csv, re, heapq
from pathlib import Path
from collections import defaultdict

BASE = Path(".")
MERGED = BASE / "merged_clean.csv"
TRANSFER_TIMES = BASE / "transfer_times.csv"

def open_csv_kr(path: Path):
    for enc in ("utf-8-sig","utf-8","cp949","euc-kr"):
        try:
            f = open(path, "r", encoding=enc, newline="")
            f.readline(); f.seek(0)
            return f
        except Exception:
            pass
    raise RuntimeError(f"Failed to open: {path} with common encodings")

def safe_strip(x):
    return str(x).strip() if x is not None else ""

def mmss_to_sec(s):
    if s is None: return None
    s = str(s).strip()
    m = re.match(r"^(\d+):(\d{2})$", s)
    if m: return int(m.group(1))*60 + int(m.group(2))
    try: return int(round(float(s)*60))
    except Exception: return None

def canon_line(s: str) -> str:
    s = safe_strip(s)
    m = re.match(r"^(\d+)\s*호선$", s)
    return m.group(1) if m else s

def to_graph_line_label(s: str) -> str:
    s = safe_strip(s)
    # normalize to labels used in merged_clean (e.g., '4호선')
    m1 = re.match(r"^(\d+)$", s)
    if m1:
        return f"{m1.group(1)}호선"
    m2 = re.match(r"^(\d+)\s*호선$", s)
    if m2:
        return f"{m2.group(1)}호선"
    return s

def norm_colnames(names):
    return [str(c).strip().lower() for c in names]

def pick_col(names, candidates):
    low = norm_colnames(names)
    for cand in candidates:
        if cand in low:
            return names[low.index(cand)]
    return None

def load_ride_edges_from_merged(merged_path: Path):
    edges = []
    station_to_lines = defaultdict(set)
    with open_csv_kr(merged_path) as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames or []
        col_line = pick_col(cols, ["line","호선","line_id","노선","노선명"])
        col_from = pick_col(cols, ["from_station","출발역","from","시작역","전역_clean"])
        col_to   = pick_col(cols, ["to_station","도착역","to","끝역","역명_clean"])
        col_sec  = pick_col(cols, ["seconds","sec","time_sec","duration_s","소요초","소요시간"])
        col_mmss = pick_col(cols, ["mmss","소요시간","time","duration"])
        if col_line and col_from and col_to and (col_sec or col_mmss):
            for row in rdr:
                ln = safe_strip(row[col_line])
                a  = safe_strip(row[col_from])
                b  = safe_strip(row[col_to])
                if not a or not b or not ln:
                    continue
                if col_sec and row[col_sec] not in (None, ""):
                    try: sec = int(row[col_sec])
                    except Exception: sec = mmss_to_sec(row[col_sec])
                else:
                    sec = mmss_to_sec(row[col_mmss])
                if not sec or sec <= 0:
                    continue
                edges.append((ln, a, b, int(sec)))
                station_to_lines[a].add(ln); station_to_lines[b].add(ln)
        else:
            col_line = pick_col(cols, ["line","호선","line_id","노선","노선명"])
            col_st   = pick_col(cols, ["역명","station","station_name","name"])
            col_sec  = pick_col(cols, ["seconds","sec","time_sec","duration_s"])
            col_mmss = pick_col(cols, ["mmss","소요시간","time","duration"])
            col_cum  = pick_col(cols, ["호선별누계(km)","누계","누계km","cumulative_km"])
            if not (col_line and col_st and (col_sec or col_mmss)):
                raise RuntimeError("merged_clean.csv schema not detected.")
            prev = {}
            for row in rdr:
                ln = safe_strip(row[col_line]); st = safe_strip(row[col_st])
                station_to_lines[st].add(ln)
                sec = None
                if col_sec and row[col_sec] not in (None, ""):
                    try: sec = int(row[col_sec])
                    except Exception: sec = mmss_to_sec(row[col_sec])
                else:
                    sec = mmss_to_sec(row[col_mmss])
                cum = None
                if col_cum and row.get(col_cum):
                    try: cum = float(row[col_cum])
                    except Exception: cum = None
                if ln in prev:
                    pst, pc = prev[ln]
                    if sec and sec>0 and not (pc is not None and cum is not None and cum < pc):
                        edges.append((ln, pst, st, int(sec)))
                prev[ln] = (st, cum)
    seen=set(); dedup=[]
    for ln,a,b,sec in edges:
        key=(ln,a,b,sec); rev=(ln,b,a,sec)
        if key in seen or rev in seen: continue
        seen.add(key); seen.add(rev); dedup.append((ln,a,b,sec))
    return dedup, station_to_lines

def load_transfer_times_csv(path: Path):
    per_station = {}
    per_pair = {}
    with open_csv_kr(path) as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames or []
        c_station = pick_col(cols, ["station","역","역명","station_name","환승역명"])
        c_lfrom   = pick_col(cols, ["line_from","from_line","linefrom","출발호선","호선from","호선"])
        c_lto     = pick_col(cols, ["line_to","to_line","lineto","도착호선","호선to","환승노선"])
        c_sec     = pick_col(cols, ["transfer_seconds","seconds","sec","소요초","환승초","환승시간(초)"])
        c_mmss    = pick_col(cols, ["mmss","소요시간","환승시간","time","환승소요시간"])
        if not c_station:
            raise RuntimeError("transfer_times.csv must include 'station' column")
        for row in rdr:
            st = safe_strip(row[c_station])
            if not st: 
                continue
            sec = None
            if c_sec and row.get(c_sec) not in (None,""):
                try: sec = int(row[c_sec])
                except Exception: sec = mmss_to_sec(row[c_sec])
            elif c_mmss and row.get(c_mmss) not in (None,""):
                sec = mmss_to_sec(row[c_mmss])
            if not sec or sec <= 0:
                continue
            if c_lfrom and c_lto and row.get(c_lfrom) not in (None,"") and row.get(c_lto) not in (None,""):
                lf = to_graph_line_label(row[c_lfrom]); lt = to_graph_line_label(row[c_lto])
                if lf and lt and lf != lt:
                    per_pair[(st, lf, lt)] = int(sec)
            else:
                per_station[st] = int(sec)
    return per_station, per_pair

def build_graph(merged_path: Path, transfer_times_path: Path, default_transfer_sec: int):
    node_id = {}; id_node = []
    def get_id(st, ln):
        key=(st,ln)
        if key not in node_id:
            node_id[key]=len(id_node); id_node.append(key)
        return node_id[key]
    adj = defaultdict(list)
    edges, station_to_lines = load_ride_edges_from_merged(merged_path)
    for ln,a,b,sec in edges:
        u=get_id(a,ln); v=get_id(b,ln)
        adj[u].append((v,int(sec))); adj[v].append((u,int(sec)))
    per_station, per_pair = load_transfer_times_csv(transfer_times_path)
    node_lookup = {(st,ln): i for i,(st,ln) in enumerate(id_node)}
    for st, lines in station_to_lines.items():
        ls = sorted(list(lines))
        for i in range(len(ls)):
            for j in range(i+1,len(ls)):
                lf,lt = ls[i], ls[j]
                sec = per_pair.get((st,lf,lt)) or per_pair.get((st,lt,lf)) or per_station.get(st) or default_transfer_sec
                a=node_lookup.get((st,lf)); b=node_lookup.get((st,lt))
                if a is not None and b is not None:
                    adj[a].append((b,int(sec))); adj[b].append((a,int(sec)))
    return node_id, id_node, adj

def dijkstra_multi(adj, sources, V):
    INF=10**15
    dist=[INF]*V; pq=[]
    for s in sources:
        dist[s]=0; pq.append((0,s))
    import heapq as _h; _h.heapify(pq)
    while pq:
        d,u=_h.heappop(pq)
        if d!=dist[u]: continue
        for v,w in adj.get(u, []):
            nd=d+w
            if nd<dist[v]:
                dist[v]=nd; _h.heappush(pq,(nd,v))
    return dist

def to_minutes(sec:int)->int:
    return int(sec)//(60*60)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged-csv", type=Path, default=MERGED)
    ap.add_argument("--transfer-times-csv", type=Path, default=TRANSFER_TIMES)
    ap.add_argument("--default-transfer-sec", type=int, default=180)
    ap.add_argument("--out-all", type=Path, default=BASE/"station_pairs_all_with_transfer.csv")
    ap.add_argument("--source-station", type=str, default=None)
    args = ap.parse_args()

    node_id, id_node, adj = build_graph(args.merged_csv, args.transfer_times_csv, args.default_transfer_sec)
    V=len(id_node)
    station_to_nodes=defaultdict(list)
    for nid,(st,ln) in enumerate(id_node):
        station_to_nodes[st].append(nid)
    stations=sorted(station_to_nodes.keys())

    with open(args.out_all, "w", encoding="utf-8-sig", newline="") as f:
        w=csv.writer(f); w.writerow(["src_station","dst_station","seconds","minutes"])
        for s in stations:
            dist=dijkstra_multi(adj, station_to_nodes[s], V)
            for t,nodes in station_to_nodes.items():
                if t==s: continue
                best=min(dist[n] for n in nodes)
                if best<10**15:
                    w.writerow([s,t,int(best),to_minutes(best)])
    print(f"[OK] Wrote {args.out_all.name} (stations={len(stations)}, nodes={V})")

    if args.source_station and args.source_station in station_to_nodes:
        out_single = BASE/f"station_pairs_from_{args.source_station}.csv"
        with open(out_single, "w", encoding="utf-8-sig", newline="") as f:
            w=csv.writer(f); w.writerow(["src_station","dst_station","seconds","minutes"])
            dist=dijkstra_multi(adj, station_to_nodes[args.source_station], V)
            for t,nodes in station_to_nodes.items():
                if t==args.source_station: continue
                best=min(dist[n] for n in nodes)
                if best<10**15:
                    w.writerow([args.source_station,t,int(best),to_minutes(best)])
        print(f"[OK] Wrote {out_single.name}")

if __name__=="__main__":
    main()
