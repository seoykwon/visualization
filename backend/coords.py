# backend/coords.py
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree

DATA_DIR = Path(__file__).parent / "data"

def read_csv_smart(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path, encoding="utf-8", engine="python", on_bad_lines="skip")

class StationCoords:
    """
    station_coords.csv를 읽어 역 이름 → (lat,lng) 매핑과 KD-tree(최근접역 탐색)를 제공합니다.
    컬럼명은 유연하게 감지합니다: name/station/역명, lat/위도, lng/lon/경도
    """
    def __init__(self, csv_path: Path = DATA_DIR / "station_coords.csv"):
        df = read_csv_smart(csv_path)
        df.columns = [c.strip() for c in df.columns]

        def pick(colnames, keys):
            for k in keys:
                for c in colnames:
                    if k in c.lower():
                        return c
            return None

        name_col = pick(df.columns, ("name", "station", "역", "역명", "place_name"))
        lat_col  = pick(df.columns, ("lat", "latitude", "위도"))
        lng_col  = pick(df.columns, ("lng", "lon", "long", "longitude", "경도"))
        if not (name_col and lat_col and lng_col):
            raise ValueError("station_coords.csv에서 name/lat/lng 컬럼을 찾지 못했습니다.")

        # 정규화
        df[name_col] = df[name_col].astype(str).str.strip()
        df[lat_col]  = df[lat_col].astype(str).str.strip().astype(float)
        df[lng_col]  = df[lng_col].astype(str).str.strip().astype(float)

        # 매핑
        self.station_pos = {
            row[name_col]: (float(row[lat_col]), float(row[lng_col]))
            for _, row in df.iterrows()
        }

        # KD-tree 준비 (lat,lng)
        coords = np.array([[v[0], v[1]] for v in self.station_pos.values()])
        self._kdtree = cKDTree(coords)
        self._kdtree_names = list(self.station_pos.keys())

    def nearest_station(self, lat: float, lng: float) -> str:
        dist, idx = self._kdtree.query([lat, lng], k=1)
        return self._kdtree_names[int(idx)]
