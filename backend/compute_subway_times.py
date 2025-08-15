
import pandas as pd, numpy as np, heapq, json, math, re
from pathlib import Path
from collections import defaultdict

# ----------------------- Utilities -----------------------
def mmss_to_sec(x):
    import re, numpy as np
    if x is None or (isinstance(x, float) and np.isnan(x)): 
        return np.nan
    s = str(x).strip()
    m = re.match(r"^(\d+):(\d{2})$", s)
    if m:
        return int(m.group(1))*60 + int(m.group(2))
    try:
        f = float(s)
        return int(round(f*60))
    except:
        return np.nan

def sec_to_mmss(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m):02d}:{int(s):02d}"

def canon_line(s: str) -> str:
    s = str(s).strip()
    m = re.match(r"^(\d+)\s*호선$", s)
    if m:
        return m.group(1)
    return s

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2*R*math.asin(math.sqrt(a))

# ----------------------- Graph ---------------------------
Node = tuple[str, str]  # (station, line)
class Graph:
    def __init__(self):
        self.adj: dict[Node, list[tuple[Node,int,str]]] = defaultdict(list)
        self.nodes_present = set()
    def add_edge(self, u: Node, v: Node, sec: int, kind="ride", undirected=True):
        self.adj[u].append((v, sec, kind))
        self.nodes_present.add(u); self.nodes_present.add(v)
        if undirected:
            self.adj[v].append((u, sec, kind))

def dijkstra(adj: dict, src: Node):
    INF = 10**15
    dist = {src: 0}
    pq = [(0, src)]
    while pq:
        d,u = heapq.heappop(pq)
        if d != dist[u]: 
            continue
        for v, w, _ in adj[u]:
            nd = d + w
            if nd < dist.get(v, INF):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist

# ---------------------- Builders -------------------------
def build_ride_edges_from_official(official_csv_path: Path) -> pd.DataFrame:
    # Read with cp949; fall back to euc-kr
    try:
        df = pd.read_csv(official_csv_path, encoding="cp949")
    except Exception:
        df = pd.read_csv(official_csv_path, encoding="euc-kr")
    df["seconds"] = df["소요시간"].map(mmss_to_sec)
    edges = []
    for line, g in df.groupby("호선", sort=False):
        g = g.reset_index(drop=True)
        for i in range(1, len(g)):
            prev_name = str(g.loc[i-1, "역명"]).strip()
            curr_name = str(g.loc[i,   "역명"]).strip()
            sec = g.loc[i, "seconds"]
            if pd.isna(sec) or sec == 0:
                continue
            # optional: cut when cumulative decreases (segment restart)
            if "호선별누계(km)" in g.columns:
                prev_cum = g.loc[i-1, "호선별누계(km)"]
                curr_cum = g.loc[i,   "호선별누계(km)"]
                if pd.notna(prev_cum) and pd.notna(curr_cum) and curr_cum < prev_cum:
                    continue
            rec = {"line": str(line).strip(), "from_station": prev_name, "to_station": curr_name, "seconds": int(sec), "kind":"ride"}
            edges.append(rec)
            edges.append({"line": str(line).strip(), "from_station": curr_name, "to_station": prev_name, "seconds": int(sec), "kind":"ride"})
    return pd.DataFrame(edges).drop_duplicates()

def add_transfer_edges_from_neighbors(g: Graph, neighbors_csv_path: Path, default_transfer_sec=240):
    nb = pd.read_csv(neighbors_csv_path, encoding="utf-8-sig")
    nb = nb.dropna(subset=["exchangeStationNames","exchangeLineNames"])
    for _, r in nb.iterrows():
        st = str(r["stationName"]).strip()
        line_here = canon_line(r["lineName"])
        u = (st, line_here)
        if u not in g.nodes_present:
            continue
        ex_stations = [s.strip() for s in str(r["exchangeStationNames"]).split(",")]
        ex_lines    = [canon_line(s) for s in str(r["exchangeLineNames"]).split(",")]
        for ex_st, ex_ln in zip(ex_stations, ex_lines):
            v = (ex_st, ex_ln)
            if v in g.nodes_present:
                g.add_edge(u, v, int(default_transfer_sec), kind="transfer", undirected=True)

def attach_walk_edges(g: Graph, click_lat, click_lng, station_coords_path: Path, k=3, max_radius_km=1.0, walk_speed_mps=1.2):
    """
    Add directed 'walk' edges from a virtual origin node to the k nearest station nodes (all lines for that station),
    within max_radius_km. Requires a coordinates JSON or CSV with at least: station name, lat, lng.
    """
    # Load coords
    coords = None
    if station_coords_path.suffix.lower() == ".json":
        coords = pd.DataFrame(json.load(open(station_coords_path, "r", encoding="utf-8")))
    else:
        coords = pd.read_csv(station_coords_path, encoding="utf-8-sig")
    # Normalize column names guesses
    rename_map = {}
    for c in coords.columns:
        if c.lower() in ("name","station","station_name","역명"):
            rename_map[c] = "station"
        if c.lower() in ("lat","latitude","위도"):
            rename_map[c] = "lat"
        if c.lower() in ("lng","lon","longitude","경도"):
            rename_map[c] = "lng"
    coords = coords.rename(columns=rename_map)
    coords = coords.dropna(subset=["station","lat","lng"])
    # Compute distances
    coords["km"] = coords.apply(lambda r: haversine_km(click_lat, click_lng, float(r["lat"]), float(r["lng"])), axis=1)
    near = coords[coords["km"] <= max_radius_km].nsmallest(k, "km")
    # Build virtual origin node
    origin = ("__ORIGIN__", "__WALK__")
    # For each nearby station, connect to all present line nodes for that station
    for st in near["station"]:
        for (node_st, node_ln) in list(g.nodes_present):
            if node_st == st:
                # walking time in seconds
                secs = int((near[near["station"]==st]["km"].values[0] * 1000) / walk_speed_mps)
                g.add_edge(origin, (node_st, node_ln), secs, kind="walk", undirected=False)
    return origin

def build_graph(official_csv_path: Path, neighbors_csv_path: Path) -> Graph:
    g = Graph()
    edges = build_ride_edges_from_official(official_csv_path)
    for _, r in edges.iterrows():
        g.add_edge((str(r["from_station"]).strip(), str(r["line"]).strip()),
                   (str(r["to_station"]).strip(),   str(r["line"]).strip()),
                   int(r["seconds"]), kind="ride", undirected=True)
    add_transfer_edges_from_neighbors(g, neighbors_csv_path, default_transfer_sec=240)
    return g

def compute_times_from_station(g: Graph, station: str, line: str, out_csv_path: Path):
    src = (station.strip(), line.strip())
    if src not in g.nodes_present:
        raise ValueError(f"Start node {src} not in graph (check station name and line id).")
    dist = dijkstra(g.adj, src)
    best = {}
    for (st, ln), sec in dist.items():
        best[st] = min(best.get(st, 10**15), sec)
    res = pd.DataFrame([{"station": st, "seconds": int(sec), "mmss": sec_to_mmss(int(sec))} for st, sec in best.items()]) \
            .sort_values("seconds")
    res.to_csv(out_csv_path, index=False, encoding="utf-8-sig")
    return res

def compute_times_from_coord(g: Graph, lat: float, lng: float, station_coords_path: Path, out_csv_path: Path,
                             k=3, max_radius_km=1.0, walk_speed_mps=1.2):
    origin = attach_walk_edges(g, lat, lng, station_coords_path, k=k, max_radius_km=max_radius_km, walk_speed_mps=walk_speed_mps)
    dist = dijkstra(g.adj, origin)
    best = {}
    for (st, ln), sec in dist.items():
        if st.startswith("__"):  # skip virtual
            continue
        best[st] = min(best.get(st, 10**15), sec)
    res = pd.DataFrame([{"station": st, "seconds": int(sec), "mmss": sec_to_mmss(int(sec))} for st, sec in best.items()]) \
            .sort_values("seconds")
    res.to_csv(out_csv_path, index=False, encoding="utf-8-sig")
    return res

if __name__ == "__main__":
    base = Path(".")
    official = base / "time.csv"
    neighbors = base / "station_neighbors_offline_updated.csv"
    g = build_graph(official, neighbors)
    # Example 1: from specific station/line
    out1 = base / "times_from_서울역_line1.csv"
    res1 = compute_times_from_station(g, "서울역", "1", out1)
    print(f"Saved {len(res1)} rows -> {out1}")
    # Example 2: from coordinate (requires station_coords.json/csv with station,lat,lng)
    # coords_file = base / "station_coords.json"
    # res2 = compute_times_from_coord(g, 37.5665, 126.9780, coords_file, base/"times_from_coord.csv")
    # print(f"Saved {len(res2)} rows -> times_from_coord.csv")
