import pandas as pd
from collections import defaultdict

# -----------------------
# 1. 기본 설정
# -----------------------
DEFAULT_TRAVEL_TIME = 2   # 분
DEFAULT_TRANSFER_TIME = 4 # 분

# -----------------------
# 2. 데이터 불러오기
# -----------------------
neighbors_df = pd.read_csv("station_neighbors_offline.csv")
subway_times_df = pd.read_csv("subway_times.csv")
transfer_times_df = pd.read_csv("transfer_times.csv")

# 소요시간 lookup 테이블 생성
travel_time_lookup = {}
for _, row in subway_times_df.iterrows():
    travel_time_lookup[(row["from"], row["to"])] = row["time_min"]
    travel_time_lookup[(row["to"], row["from"])] = row["time_min"]  # 양방향

transfer_time_lookup = {}
for _, row in transfer_times_df.iterrows():
    transfer_time_lookup[(row["from"], row["to"])] = row["time_min"]
    transfer_time_lookup[(row["to"], row["from"])] = row["time_min"]  # 양방향

# -----------------------
# 3. 인접역 dictionary 구성
# -----------------------
graph = defaultdict(list)

for _, row in neighbors_df.iterrows():
    station = row["stationName"]
    neighbors = str(row["neighbors"]).split(",")

    for nb in neighbors:
        nb = nb.strip()
        if not nb:
            continue

        # 환승 여부 판단: 같은 이름인데 호선만 다르면 환승
        is_transfer = station.split("(")[0] == nb.split("(")[0] and station != nb

        if is_transfer:
            time_val = transfer_time_lookup.get((station, nb), DEFAULT_TRANSFER_TIME)
        else:
            time_val = travel_time_lookup.get((station, nb), DEFAULT_TRAVEL_TIME)

        graph[station].append({"station": nb, "time": time_val})

# -----------------------
# 4. 저장
# -----------------------
import json
with open("station_graph_with_time.json", "w", encoding="utf-8") as f:
    json.dump(graph, f, ensure_ascii=False, indent=2)

print(f"[OK] {len(graph)}개 역에 대해 연결 정보 저장 완료")
