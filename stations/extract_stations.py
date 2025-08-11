import pandas as pd
import re

# CSV 파일 로딩
df = pd.read_csv('서울교통공사_노선별 지하철역 정보.csv', encoding='cp949')

# 노선명 전처리
def clean_line_name(raw_line: str) -> str:
    if raw_line == "인천선":
        return "인천1호선"
    elif raw_line == "우이신설경전철":
        return "우이신설선"
    elif raw_line.endswith("호선"):
        return raw_line.lstrip("0")  # "01호선" → "1호선"
    return raw_line

# 역 이름 특수문자 제거
def clean_station_name(name: str) -> str:
    return re.sub(r"[^\w가-힣]", "", name)

# 역 + 호선 전처리 조합
def format_station_line(row):
    station = clean_station_name(row['전철역명'].strip())
    line = clean_line_name(row['호선'].strip())
    if not station.endswith("역"):
        station += "역"
    return f"{station} {line}"

# 전처리 적용
df = df.dropna(subset=['전철역명', '호선'])  # 결측 제거
station_line_names = df.apply(format_station_line, axis=1).unique().tolist()

# 결과 확인
print(f"총 {len(station_line_names)}개의 역+호선 조합을 추출했습니다.")
print(station_line_names)
