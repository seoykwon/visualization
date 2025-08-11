import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
KEY = os.getenv("SEOUL_API_KEY")

# 예: station_master.csv에는 역명, 노선, 정류장ID 컬럼 포함
df = pd.read_csv("station_master.csv", encoding="cp949")

def get_avg_time(start_id, end_id):
    url = "https://data.seoul.go.kr/openapi/tnod/service/rest/TransitTimeSectionService"
    params = {
        "serviceKey": KEY,
        "startStationId": start_id,
        "endStationId": end_id,
        "startTime": "20250806",  # YYYYMMDD 형식 (latest 30일 데이터)
        "endTime": "20250806",
        "numOfRows": 1,
        "pageNo": 1
    }
    res = requests.get(url, params=params)
    data = res.json()
    row = data["TransitTimeSectionService"]["row"][0]
    return row["avgTravelTime"]  # 평균 시간(분)

# 예시: 순차 노선별 시간 계산
total_time = 0
path = [1001, 1002, 1003]  # 예: 역 ID 리스트
for i in range(len(path)-1):
    t = get_avg_time(path[i], path[i+1])
    print(f"{path[i]}→{path[i+1]}: {t}분")
    total_time += int(t)
print("총 예상 시간:", total_time, "분")
