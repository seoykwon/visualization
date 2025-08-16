# backend/graph.py
import pandas as pd
import networkx as nx
from pathlib import Path
from scipy.spatial import cKDTree
import numpy as np

DATA_DIR = Path(__file__).parent / "data"

def read_csv_smart(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    # 최후 시도
    return pd.read_csv(path, encoding="utf-8", engine="python", on_bad_lines="skip")

class SubwayGraph:
    def __init__(self):
        # 1) 역 좌표 CSV 로드
        coords_df = read_csv_smart(DATA_DIR / "station_coords.csv")
        coords_df.columns = [c.strip() for c in coords_df.columns]

        # 컬럼 추정: name / lat / lng
        def guess_name_col(cols):
            cands = [c for c in cols if c.lower() in ("name","station","역","역명","place_name")]
            if cands: return cands[0]
            # name* 같은 우선
            for c in cols:
                if "name" in c.lower() or "역" in c or "station" in c.lower():
                    return c
            raise ValueError("station_coords.csv에서 역 이름 컬럼을 찾지 못했습니다.")

        def guess_lat_col(cols):
            for key in ("lat","latitude","위도"):
                for c in cols:
                    if key in c.lower():
                        return c
            raise ValueError("station_coords.csv에서 위도(lat) 컬럼을 찾지 못했습니다.")

        def guess_lng_col(cols):
            for key in ("lng","lon","long","longitude","경도"):
                for c in cols:
                    if key in c.lower():
                        return c
            raise ValueError("station_coords.csv에서 경도(lng) 컬럼을 찾지 못했습니다.")

        name_col = guess_name_col(coords_df.columns)
        lat_col  = guess_lat_col(coords_df.columns)
        lng_col  = guess_lng_col(coords_df.columns)

        # 문자열/공백 정리
        coords_df[name_col] = coords_df[name_col].astype(str).str.strip()
        coords_df[lat_col]  = coords_df[lat_col].astype(str).str.strip().astype(float)
        coords_df[lng_col]  = coords_df[lng_col].astype(str).str.strip().astype(float)

        # 역명 → (lat, lng)
        self.station_pos = {
            row[name_col]: (float(row[lat_col]), float(row[lng_col]))
            for _, row in coords_df.iterrows()
        }

        # KD-Tree (좌표 → 가장 가까운 역명)
        coords = np.array([[v[0], v[1]] for v in self.station_pos.values()])
        self._kdtree = cKDTree(coords)
        self._kdtree_names = list(self.station_pos.keys())

        # 2) 엣지(소요시간 분) 로드
        df = read_csv_smart(DATA_DIR / "station_pairs_all_with_transfer.csv")
        df.columns = [c.strip() for c in df.columns]

        def guess_minutes_col(columns):
            last = columns[-1]
            if any(k in last.lower() for k in ["분", "time", "minute", "minutes", "소요"]):
                return last
            for c in reversed(columns):
                if any(k in c.lower() for k in ["분", "time", "minute", "minutes", "소요"]):
                    return c
            raise ValueError("분 단위 소요시간 컬럼을 찾지 못했습니다. CSV 컬럼명을 확인하세요.")

        def guess_from_to(columns):
            # 흔한 패턴 우선
            cand_from = [c for c in columns if c.lower() in ["from","src","start","출발","source","station_u","u","역1"]]
            cand_to   = [c for c in columns if c.lower() in ["to","dst","end","도착","target","station_v","v","역2"]]
            if cand_from and cand_to:
                return cand_from[0], cand_to[0]
            # station* 두 개 추정
            stations = [c for c in columns if "station" in c.lower() or "역" in c]
            if len(stations) >= 2:
                return stations[0], stations[1]
            raise ValueError("출발/도착 역 컬럼을 찾지 못했습니다.")

        minutes_col = guess_minutes_col(df.columns)
        ucol, vcol  = guess_from_to(df.columns)

        # 3) 그래프 구성
        G = nx.Graph()
        for name, (lat, lng) in self.station_pos.items():
            G.add_node(name, lat=lat, lng=lng)

        # 유효한 엣지만 추가
        for _, row in df.iterrows():
            u = str(row[ucol]).strip()
            v = str(row[vcol]).strip()
            try:
                w = float(row[minutes_col])
            except Exception:
                continue
            if u in self.station_pos and v in self.station_pos and w >= 0:
                G.add_edge(u, v, weight=w)

        self.G = G

    def nearest_station_by_coord(self, lat, lng):
        # KDTree는 (lat, lng) 기준
        dist, idx = self._kdtree.query([lat, lng], k=1)
        return self._kdtree_names[int(idx)]

    def minutes_from(self, origin_name):
        # 단위: 분. Dijkstra 단일-소스 최단거리
        return nx.single_source_dijkstra_path_length(self.G, origin_name, weight="weight")
