import pandas as pd
import numpy as np
import re

# 1) CSV 읽기 (CP949)
df = pd.read_csv("time.csv", encoding="cp949")

# 2) mm:ss → 초 변환
def mmss_to_sec(x):
    if pd.isna(x): 
        return np.nan
    s = str(x).strip()
    m = re.match(r"^(\d+):(\d{2})$", s)
    if m:
        return int(m.group(1))*60 + int(m.group(2))
    # 분(숫자)로 들어온 경우
    try:
        f = float(s)
        return int(round(f*60))
    except:
        return np.nan

df["seconds"] = df["소요시간"].map(mmss_to_sec)

# 3) 간선 리스트 만들기
#    규칙: 같은 호선에서 연속 행을 연결.
#    - 현재 행의 seconds = (바로 이전 역 → 현재 역) 소요시간
#    - 소요시간이 0(00:00)이면 "구간 시작"으로 보고 연결 생략
#    - (선택) 호선별누계가 감소하면 분기/재시작으로 보고 연결 생략
edges = []
for line, g in df.groupby("호선", sort=False):
    g = g.reset_index(drop=True)
    for i in range(1, len(g)):
        prev_name = str(g.loc[i-1, "역명"]).strip()
        curr_name = str(g.loc[i,   "역명"]).strip()
        sec = g.loc[i, "seconds"]
        if pd.isna(sec) or sec == 0:
            # 라인 세그먼트 시작/리셋
            continue
        # (선택) 누계 감소 시 세그먼트 리셋
        if "호선별누계(km)" in g.columns:
            prev_cum = g.loc[i-1, "호선별누계(km)"]
            curr_cum = g.loc[i,   "호선별누계(km)"]
            if pd.notna(prev_cum) and pd.notna(curr_cum) and curr_cum < prev_cum:
                continue

        rec = {
            "line": str(line),
            "from_station": prev_name,
            "to_station": curr_name,
            "seconds": int(sec),
            "kind": "ride",
        }
        edges.append(rec)
        # 양방향(대칭) 간선도 추가
        edges.append({
            "line": str(line),
            "from_station": curr_name,
            "to_station": prev_name,
            "seconds": int(sec),
            "kind": "ride",
        })

edges_df = pd.DataFrame(edges).drop_duplicates()
print(edges_df.head(10))
edges_df.to_csv("subway_edges_from_official.csv", index=False, encoding="utf-8-sig")
print("saved -> subway_edges_from_official.csv")
