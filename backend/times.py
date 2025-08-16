# backend/times.py
from pathlib import Path
import pandas as pd
from functools import lru_cache
from typing import Dict

DATA_DIR = Path(__file__).parent / "data"

def read_csv_smart(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path, encoding="utf-8", engine="python", on_bad_lines="skip")

class PrecomputedTimes:
    """
    station_pairs_all_with_transfer.csv 에서
    src_destination(출발), dst_station(도착), <마지막 컬럼=분단위 소요시간>을 사용.
    """

    def __init__(self, csv_path: Path = DATA_DIR / "station_pairs_all_with_transfer.csv"):
        df = read_csv_smart(csv_path)
        df.columns = [c.strip() for c in df.columns]

        # 고정 컬럼명
        if "src_station" not in df.columns or "dst_station" not in df.columns:
            raise ValueError("CSV에 'src_station' 또는 'dst_station' 컬럼이 없습니다.")

        self.origin_col = "src_station"
        self.dest_col   = "dst_station"
        self.time_col   = df.columns[-1]  # 마지막 컬럼 = 분단위 소요시간

        # 정규화
        df[self.origin_col] = df[self.origin_col].astype(str).str.strip()
        df[self.dest_col]   = df[self.dest_col].astype(str).str.strip()
        df[self.time_col]   = pd.to_numeric(df[self.time_col], errors="coerce")

        # NaN 시간 제거
        df = df.dropna(subset=[self.time_col])

        # 원점별 빠른 조회를 위해 인덱스 구성
        self.df = df.set_index([self.origin_col, self.dest_col]).sort_index()

    @lru_cache(maxsize=4096)
    def times_from(self, origin_name: str) -> Dict[str, float]:
        """원점 역 기준 {도착역: 분} 딕셔너리 반환 (없으면 빈 dict)."""
        try:
            sub = self.df.xs(origin_name, level=self.origin_col)
        except KeyError:
            return {}
        return sub[self.time_col].astype(float).to_dict()
