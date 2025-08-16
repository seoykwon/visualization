import pandas as pd

# CSV 파일 경로
distance_path = "국가철도공단_우이신설역간거리_20230425.csv"

# CSV 불러오기 (인코딩은 파일 저장 형식에 맞게 변경 가능)
df = pd.read_csv(distance_path, encoding="cp949")

# 의정부경전철 평균 속도 (km/h)
speed_kmh = 33.8

# 소요시간(초) 계산 = (거리 / 속도) * 3600
df["소요시간"] = ((df["역간거리"] / speed_kmh) * 3600).round(0).astype(int)

# 결과 저장
output_path = "우이신설선_소요시간.csv"
df.to_csv(output_path, index=False, encoding="utf-8-sig")

print(f"계산 완료! '{output_path}' 파일이 생성되었습니다.")
