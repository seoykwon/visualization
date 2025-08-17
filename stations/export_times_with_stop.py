#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export all station-to-station (역→역) travel times (Dijkstra) to CSV
USING ONLY:
  - merged_clean.csv       (ride edges)
  - transfer_times.csv     (transfer edges: per-station or line-pair overrides)

Fixes:
- (1) transfer_times.csv에 정보가 없어도, merged_clean.csv에서 같은 역의 다중 호선으로 환승 간선을 자동 생성
- (2) 모든 시간 입력을 '초'로 엄격 파싱: M:SS만 분:초, 그 외 숫자는 그대로 '초'

Dwell:
- ride 간선으로 역에 '도착'할 때마다 dwell_sec(기본 40초) 가산
- 최종 목적지 도착 시 dwell 1회는 제거 → 한 정거장 직행은 정차시간 증가 없음

Output:
- 기본 파일명은 station_pairs_all_with_stop.csv (stop 포함)
"""
import argparse, csv, re, heapq
from pathlib import Path
from collections import defaultdict

BASE = Path(".")
MERGED = BASE / "merged_clean.csv"
TRANSFER_TIMES = BASE / "transfer_times.csv"

# ----------------------------
# I/O helpers
# ----------------------------
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

def norm_colnames(names): return [str(c).strip().lower() for c in names]

def pick_col(names, candidates):
    low = norm_colnames(names)
    for cand in candidates:
        if cand in low:
            return names[low.index(cand)]
    return None

# ----------------------------
# Time parsing  (STRICT SECONDS)
# ----------------------------
def parse_seconds_strict(x):
    """
    문자열/숫자를 '초'로 파싱.
    - 'M:SS'만 분:초로 인식해 초 환산
    - 그 외 숫자(정수/실수, 천단위 콤마 포함)는 '그 값 그대로 초'
    - 절대 ×60 안 함
    """
    if x is None: return None
    s = str(x).strip().replace(",", "")
    if not s: return None
    m = re.match(r"^(\d+):(\d{2})$", s)
    if m:
        return int(m.group(1))*60 + int(m.group(2))
    try:
        return int(round(float(s)))
    except Exception:
        return None

def to_minutes(sec:int)->int:
    return int(sec)//60

# ----------------------------
# Label normalize
# ----------------------------
def normalize_line_label(s: str) -> str:
    """통일된 호선 라벨: '9호선', '9호선급행' 등. 비숫자 라벨은 공백 제거만."""
    s = safe_strip(s).replace(" ", "")
    s = s.replace("(급행)", "급행").replace("[급행]", "급행")
    m = re.match(r"^(\d+)(호선)?(급행)?$", s)
    if m:
        base = f"{m.group(1)}호선"
        return base + ("급행" if m.group(3) else "")
    return s

def to_graph_line_label(s: str) -> str:
    s = safe_strip(s)
    m1 = re.match(r"^(\d+)$", s)
    if m1: return f"{m1.group(1)}호선"
    m2 = re.match(r"^(\d+)\s*호선$", s)
    if m2: return f"{m2.group(1)}호선"
    return normalize_line_label(s)

# ----------------------------
# Loaders
# ----------------------------
def load_ride_edges_from_merged(merged_path: Path):
    """
    merged_clean.csv에서 호선 내 이웃역 간 소요(초)를 읽어 라이드 간선 생성
    반환: ([(line, a, b, seconds), ...], station_to_lines)
    """
    edges = []
    station_to_lines = defaultdict(set)
    with open_csv_kr(merged_path) as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames or []
        col_line = pick_col(cols, ["line","호선","line_id","노선","노선명"])
        col_from = pick_col(cols, ["from_station","출발역","from","시작역","전역_clean"])
        col_to   = pick_col(cols, ["to_station","도착역","to","끝역","역명_clean"])
        # 초 확정 컬럼(있으면 사용)
        col_sec  = pick_col(cols, ["seconds","sec","time_sec","duration_s","소요초","소요시간(초)"])
        # 표현형 컬럼(여기 포함값은 parse_seconds_strict로 처리)
        col_expr = pick_col(cols, ["mmss","소요시간","time","duration"])

        if col_line and col_from and col_to and (col_sec or col_expr):
            for row in rdr:
                ln = normalize_line_label(row[col_line])
                a  = safe_strip(row[col_from]); b = safe_strip(row[col_to])
                if not a or not b or not ln: continue
                raw = None
                if col_sec and row.get(col_sec) not in (None,""): raw = row[col_sec]
                elif col_expr and row.get(col_expr) not in (None,""): raw = row[col_expr]
                sec = parse_seconds_strict(raw)
                if not sec or sec <= 0: continue
                edges.append((ln, a, b, int(sec)))
                station_to_lines[a].add(ln); station_to_lines[b].add(ln)
        else:
            # 연속역 표(누계/구간소요)에서 이웃 추출
            col_line = pick_col(cols, ["line","호선","line_id","노선","노선명"])
            col_st   = pick_col(cols, ["역명","station","station_name","name"])
            col_sec  = pick_col(cols, ["seconds","sec","time_sec","duration_s","소요초","소요시간(초)"])
            col_expr = pick_col(cols, ["mmss","소요시간","time","duration"])
            col_cum  = pick_col(cols, ["호선별누계(km)","누계","누계km","cumulative_km"])
            if not (col_line and col_st and (col_sec or col_expr)):
                raise RuntimeError("merged_clean.csv schema not detected.")
            prev = {}
            for row in rdr:
                ln = normalize_line_label(row[col_line])
                st = safe_strip(row[col_st])
                station_to_lines[st].add(ln)
                raw = None
                if col_sec and row.get(col_sec) not in (None,""): raw = row[col_sec]
                elif col_expr and row.get(col_expr) not in (None,""): raw = row[col_expr]
                sec = parse_seconds_strict(raw)
                cum = None
                if col_cum and row.get(col_cum):
                    try: cum = float(row[col_cum])
                    except Exception: cum = None
                if ln in prev:
                    pst, pc = prev[ln]
                    if sec and sec>0 and not (pc is not None and cum is not None and cum < pc):
                        edges.append((ln, pst, st, int(sec)))
                prev[ln] = (st, cum)

    # 중복 제거(동일 호선 내 무방향 간선)
    seen=set(); dedup=[]
    for ln,a,b,sec in edges:
        key=(ln,a,b,sec); rev=(ln,b,a,sec)
        if key in seen or rev in seen: continue
        seen.add(key); seen.add(rev); dedup.append((ln,a,b,sec))
    return dedup, station_to_lines

def load_transfer_times_csv(path: Path):
    """
    transfer_times.csv 읽기
    - per_station: {역명: sec}
    - per_pair: {(역명, line_from, line_to): sec}   (양방향은 자동 대응)
    * 초 단위로 엄격 파싱. 표현형은 parse_seconds_strict로 처리.
    """
    per_station = {}
    per_pair = {}
    with open_csv_kr(path) as f:
        rdr = csv.DictReader(f)
        cols = rdr.fieldnames or []
        c_station = pick_col(cols, ["station","역","역명","station_name","환승역명"])
        c_lfrom   = pick_col(cols, ["line_from","from_line","linefrom","출발호선","호선from","호선"])
        c_lto     = pick_col(cols, ["line_to","to_line","lineto","도착호선","호선to","환승노선"])
        # seconds 후보(확실한 '초' 명시)
        c_sec     = pick_col(cols, ["transfer_seconds","seconds","sec","소요초","환승초","환승시간(초)"])
        # 표현형 후보
        c_expr    = pick_col(cols, ["mmss","소요시간","환승시간","time","환승소요시간"])
        if not c_station:
            raise RuntimeError("transfer_times.csv must include 'station' column")
        for row in rdr:
            st = safe_strip(row[c_station])
            if not st: 
                continue
            raw = None
            if c_sec and row.get(c_sec) not in (None,""): raw = row[c_sec]
            elif c_expr and row.get(c_expr) not in (None,""): raw = row[c_expr]
            sec = parse_seconds_strict(raw)
            if not sec or sec <= 0:
                continue
            if c_lfrom and c_lto and row.get(c_lfrom) not in (None,"") and row.get(c_lto) not in (None,""):
                lf = normalize_line_label(to_graph_line_label(row[c_lfrom]))
                lt = normalize_line_label(to_graph_line_label(row[c_lto]))
                if lf and lt and lf != lt:
                    per_pair[(st, lf, lt)] = int(sec)
            else:
                per_station[st] = int(sec)
    return per_station, per_pair

# ----------------------------
# Graph build
# ----------------------------
def build_graph(merged_path: Path, transfer_times_path: Path, default_transfer_sec: int):
    """
    인접 리스트 생성. 각 간선에 is_transfer 플래그 포함.
    adj[u] -> list of (v, weight_seconds, is_transfer: bool)
    """
    node_id = {}; id_node = []
    def get_id(st, ln):
        key=(st,ln)
        if key not in node_id:
            node_id[key]=len(id_node); id_node.append(key)
        return node_id[key]
    adj = defaultdict(list)

    # 1) ride edges
    edges, station_to_lines = load_ride_edges_from_merged(merged_path)
    for ln,a,b,sec in edges:
        u=get_id(a,ln); v=get_id(b,ln)
        adj[u].append((v,int(sec),False)); adj[v].append((u,int(sec),False))

    # 2) transfer edges
    per_station, per_pair = load_transfer_times_csv(transfer_times_path)

    # 역별로, 존재하는 모든 호선쌍에 대해 환승 간선 자동 생성
    node_lookup = {(st,ln): i for i,(st,ln) in enumerate(id_node)}
    for st, lines in station_to_lines.items():
        ls = sorted(list(lines))
        for i in range(len(ls)):
            for j in range(i+1,len(ls)):
                lf, lt = ls[i], ls[j]
                # 우선순위: per_pair override → 역별 기본 → CLI 기본값
                sec = (per_pair.get((st,lf,lt)) or per_pair.get((st,lt,lf)) 
                       or per_station.get(st) or default_transfer_sec)
                a=node_lookup.get((st,lf)); b=node_lookup.get((st,lt))
                if a is not None and b is not None:
                    adj[a].append((b,int(sec),True)); adj[b].append((a,int(sec),True))
    return node_id, id_node, adj

# ----------------------------
# Dijkstra with dwell
# ----------------------------
def dijkstra_multi_modes(adj, sources, V, dwell_sec: int):
    """
    상태 분리 다익스트라:
    - distT[v]: 환승 간선으로 v에 도착 (도착 시 dwell 미적용)
    - distR[v]: ride 간선으로 v에 도착 (도착 시 dwell 적용된 값)
    시작점은 '도착'이 아니므로 distT[s]=0으로 시작.
    """
    INF = 10**15
    distT = [INF]*V
    distR = [INF]*V
    pq = []

    for s in sources:
        distT[s] = 0
        heapq.heappush(pq, (0, s, 0))  # 0=transfer, 1=ride

    while pq:
        d, u, st = heapq.heappop(pq)
        if st == 0 and d != distT[u]: continue
        if st == 1 and d != distR[u]: continue

        for v, w, is_transfer in adj.get(u, []):
            if is_transfer:
                nd = d + w
                if nd < distT[v]:
                    distT[v] = nd
                    heapq.heappush(pq, (nd, v, 0))
            else:
                nd = d + w + dwell_sec
                if nd < distR[v]:
                    distR[v] = nd
                    heapq.heappush(pq, (nd, v, 1))
    return distT, distR

def best_seconds_for_station(distT, distR, nodes, dwell_sec):
    """목적지 집합에 대한 최단값 선택(도착역 dwell 1회 제거)."""
    INF = 10**15
    best = INF
    for n in nodes:
        if distT[n] < best:
            best = distT[n]
        if distR[n] < INF:
            cand = max(0, distR[n] - dwell_sec)
            if cand < best:
                best = cand
    return best

# ----------------------------
# Main
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--merged-csv", type=Path, default=MERGED)
    ap.add_argument("--transfer-times-csv", type=Path, default=TRANSFER_TIMES)
    ap.add_argument("--default-transfer-sec", type=int, default=180)
    ap.add_argument("--dwell-sec", type=int, default=40,
                    help="Per-stop dwell seconds for intermediate stations (applied on arrival via ride).")
    ap.add_argument("--out-all", type=Path, default=BASE/"station_pairs_all_with_stop.csv")
    ap.add_argument("--source-station", type=str, default=None)
    args = ap.parse_args()

    node_id, id_node, adj = build_graph(args.merged_csv, args.transfer_times_csv, args.default_transfer_sec)
    V=len(id_node)

    # 역 -> 해당 역의 (역,호선) 노드 목록
    station_to_nodes=defaultdict(list)
    for nid,(st,ln) in enumerate(id_node):
        station_to_nodes[st].append(nid)
    stations=sorted(station_to_nodes.keys())

    # 전체 쌍 출력
    with open(args.out_all, "w", encoding="utf-8-sig", newline="") as f:
        w=csv.writer(f); w.writerow(["src_station","dst_station","seconds","minutes"])
        for s in stations:
            distT, distR = dijkstra_multi_modes(adj, station_to_nodes[s], V, args.dwell_sec)
            for t,nodes in station_to_nodes.items():
                if t==s: continue
                best = best_seconds_for_station(distT, distR, nodes, args.dwell_sec)
                if best < 10**15:
                    w.writerow([s, t, int(best), to_minutes(best)])
    print(f"[OK] Wrote {args.out_all.name} (stations={len(stations)}, nodes={V})")

    # (선택) 특정 출발역 파일
    if args.source_station and args.source_station in station_to_nodes:
        out_single = BASE/f"station_pairs_from_{args.source_station}_with_stop.csv"
        with open(out_single, "w", encoding="utf-8-sig", newline="") as f:
            w=csv.writer(f); w.writerow(["src_station","dst_station","seconds","minutes"])
            distT, distR = dijkstra_multi_modes(adj, station_to_nodes[args.source_station], V, args.dwell_sec)
            for t,nodes in station_to_nodes.items():
                if t==args.source_station: continue
                best = best_seconds_for_station(distT, distR, nodes, args.dwell_sec)
                if best < 10**15:
                    w.writerow([args.source_station, t, int(best), to_minutes(best)])
        print(f"[OK] Wrote {Path(out_single).name}")

if __name__=="__main__":
    main()
