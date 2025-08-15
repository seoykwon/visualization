
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export all station-to-station (역→역) travel times (Dijkstra) to CSV.
- Nodes = (station, line)
- Ride edges from official CSV (연속 역)
- Transfer edges from neighbors CSV (기본 240초)

Inputs (same folder):
  - 서울교통공사 역간거리 및 소요시간_240810.csv
  - station_neighbors_offline_updated.csv

Outputs:
  - station_pairs_all.csv          (src_station,dst_station,seconds,mmss)
  - station_pairs_from_사당.csv    (optional convenience file if '사당' 존재)

Usage:
  python3 export_station_pairs.py
"""
import csv, re, json, heapq
from pathlib import Path
from collections import defaultdict

BASE = Path(".")
OFFICIAL = BASE / "서울교통공사 역간거리 및 소요시간_240810.csv"
NEIGHBORS = BASE / "station_neighbors_offline_updated.csv"
OUT_ALL = BASE / "station_pairs_all.csv"
OUT_DAEBANG = BASE / "station_pairs_from_사당.csv"
DEFAULT_TRANSFER = 240

def open_csv_kr(path: Path):
    for enc in ("cp949","euc-kr","utf-8-sig","utf-8"):
        try:
            f = open(path, "r", encoding=enc, newline="")
            # prime
            f.readline(); f.seek(0)
            return f
        except Exception:
            pass
    raise RuntimeError(f"Failed to open: {path}")

def mmss_to_sec(s):
    s = str(s).strip()
    m = re.match(r"^(\d+):(\d{2})$", s)
    if m: return int(m.group(1))*60 + int(m.group(2))
    try: return int(round(float(s)*60))
    except: return None

def canon_line(s: str) -> str:
    s = str(s).strip()
    m = re.match(r"^(\d+)\s*호선$", s)
    return m.group(1) if m else s

# Build graph (node=(station,line) -> neighbors with weights)
node_id = {}
id_node = []
def get_id(st, ln):
    key = (st, ln)
    if key not in node_id:
        node_id[key] = len(id_node)
        id_node.append(key)
    return node_id[key]

adj = defaultdict(list)

# 1) ride edges
with open_csv_kr(OFFICIAL) as f:
    rdr = csv.DictReader(f)
    need = ("호선","역명","소요시간")
    for c in need:
        if c not in rdr.fieldnames: raise RuntimeError("Official CSV missing "+c)
    prev = {}  # line -> (station, cum)
    for row in rdr:
        line = str(row["호선"]).strip()
        st = str(row["역명"]).strip()
        sec = mmss_to_sec(row["소요시간"])
        cum = None
        if "호선별누계(km)" in row and row["호선별누계(km)"]!="":
            try: cum = float(row["호선별누계(km)"])
            except: cum = None
        if line in prev:
            pst, pc = prev[line]
            if sec and sec>0 and not (pc is not None and cum is not None and cum < pc):
                a = get_id(pst, line); b = get_id(st, line)
                adj[a].append((b, int(sec))); adj[b].append((a, int(sec)))
        prev[line] = (st, cum)

# 2) transfer edges
with open(NEIGHBORS, "r", encoding="utf-8-sig", newline="") as f:
    rdr = csv.DictReader(f)
    need2 = ("stationName","lineName","exchangeStationNames","exchangeLineNames")
    for c in need2:
        if c not in rdr.fieldnames: raise RuntimeError("Neighbors CSV missing "+c)
    for row in rdr:
        st = str(row["stationName"]).strip()
        ln = canon_line(row["lineName"])
        u = (st, ln)
        if u not in node_id: 
            continue
        ex_sts = [s.strip() for s in str(row["exchangeStationNames"]).split(",")]
        ex_lns = [canon_line(s) for s in str(row["exchangeLineNames"]).split(",")]
        for es, el in zip(ex_sts, ex_lns):
            v = (es, el)
            if v in node_id:
                a = node_id[u]; b = node_id[v]
                adj[a].append((b, DEFAULT_TRANSFER)); adj[b].append((a, DEFAULT_TRANSFER))

V = len(id_node)

# Station index
station_to_nodes = defaultdict(list)
for nid, (st, ln) in enumerate(id_node):
    station_to_nodes[st].append(nid)
stations = sorted(station_to_nodes.keys())

def dijkstra_multi(sources):
    INF=10**15
    dist=[INF]*V
    pq=[]
    for s in sources:
        dist[s]=0; heapq.heappush(pq,(0,s))
    while pq:
        d,u=heapq.heappop(pq)
        if d!=dist[u]: continue
        for v,w in adj.get(u, []):
            nd=d+w
            if nd<dist[v]:
                dist[v]=nd; heapq.heappush(pq,(nd,v))
    return dist

def mmss(sec:int)->str:
    m,s=divmod(int(sec),60); return f"{m:02d}:{s:02d}"

# Compute & write CSV
import csv as _csv
with open(OUT_ALL, "w", encoding="utf-8-sig", newline="") as f:
    w = _csv.writer(f)
    w.writerow(["src_station","dst_station","seconds","mmss"])
    for s in stations:
        dist = dijkstra_multi(station_to_nodes[s])
        # aggregate per station
        best = {}
        for t, nodes in station_to_nodes.items():
            if t==s: continue
            best_sec = min(dist[n] for n in nodes)
            if best_sec < 10**15:
                w.writerow([s, t, int(best_sec), mmss(best_sec)])

# Optional convenience: Daebang-only slice
if "사당" in station_to_nodes:
    import csv as _csv
    with open(OUT_DAEBANG, "w", encoding="utf-8-sig", newline="") as f:
        w=_csv.writer(f); w.writerow(["src_station","dst_station","seconds","mmss"])
        dist = dijkstra_multi(station_to_nodes["대방"])
        for t, nodes in station_to_nodes.items():
            if t=="대방": continue
            best_sec = min(dist[n] for n in nodes)
            if best_sec < 10**15:
                w.writerow(["대방", t, int(best_sec), mmss(best_sec)])

print(f"[OK] Wrote {OUT_ALL.name}  (stations={len(stations)}, nodes={V})")
