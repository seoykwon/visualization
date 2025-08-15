import pandas as pd
import re

# 안전한 CSV 읽기 함수
'''def safe_read_csv(path, **kwargs):
    try:
        return pd.read_csv(path, encoding="utf-8-sig", **kwargs)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="cp949", **kwargs)

# 예시 사용
df = safe_read_csv("3호선 추가소요시간.csv", dtype=str)
df_air = safe_read_csv("공항철도 소요시간.csv", dtype=str)
df_4 = safe_read_csv("4호선 추가 소요시간.csv", dtype=str)
df_9 = safe_read_csv("9호선 소요시간.csv", dtype=str)
df_경강 = safe_read_csv("경강선 소요시간.csv", dtype=str)
df_경의중앙 = safe_read_csv("경의중앙선 소요시간.csv", dtype=str)
df_수인 = safe_read_csv("수인선 소요시간.csv", dtype=str)
df_신분당선 = safe_read_csv("신분당선 소요시간.csv", dtype=str)
df_incheon = safe_read_csv("인천1,2호선 및 7호선 일부 소요시간.csv", dtype=str)
df_경춘 = safe_read_csv("경춘선 소요시간.csv", dtype=str)
df_우의신설 = safe_read_csv("우이신설선_소요시간.csv", dtype=str)
df_의정부경전철 = safe_read_csv("의정부경전철_소요시간.csv", dtype=str)


# ===== 소요시간을 정수 초단위로 환산 =====
df["소요시간"] = df["소요시간(초)"].astype(float).fillna(0).astype(int)
df_air["소요시간"] = df_air["소요시간(초)"].astype(float).fillna(0).astype(int)
df_4["소요시간"] = df_4["소요시간(초)"].astype(float).fillna(0).astype(int)
df_9["소요시간"] = df_9["소요시간(초)"].astype(float).fillna(0).astype(int)
df_경강["소요시간"] = df_경강["소요시간(초)"].astype(float).fillna(0).astype(int)
df_경의중앙["소요시간"] = df_경의중앙["소요시간(초)"].astype(float).fillna(0).astype(int)
df_수인["소요시간"] = df_수인["소요시간(초)"].astype(float).fillna(0).astype(int)
df_신분당선["소요시간"] = df_신분당선["소요시간(초)"].astype(float).fillna(0).astype(int)

def time_to_seconds(t):
    if isinstance(t, str) and ":" in t:
        m, s = t.split(":")
        return int(m) * 60 + int(s)
    elif isinstance(t, (int, float)):
        return int(t)  # 이미 숫자일 경우
    else:
        return None  # 빈칸/NaN 처리

df_incheon["소요시간"] = df_incheon["소요시간"].apply(time_to_seconds)

# 역명으로 모두 정리
df_incheon = df.rename(columns={"당역": "역명"})

# ===== 호선/선명 정리 =====
line_name_map = {
    "1": "1호선",
    "2": "2호선",
    "3": "3호선",
    "4": "4호선",
    "5": "5호선",
    "6": "6호선",
    "7": "7호선",
    "8": "8호선",
    "9": "9호선",
    "경강": "경강선",
    "경의중앙": "경의중앙선",
    "경춘": "경춘선",
    "공항": "공항철도",
    "수인분당": "수인분당선",
    "신분당": "신분당선",
    "우이신설": "우이신설경전철",
    "의정부": "의정부경전철",
    "인천 1호선": "인천1호선",
    "인천 2호선": "인천2호선",
    "에버라인" : "용인경전철"
}

# '선명' 컬럼 변환
for df_line in [df_경의중앙, df_경춘, df_air, df_수인, df_신분당선, df_우의신설, df_의정부경전철]:
    if "선명" in df_line.columns:
        df_line["선명"] = df_line["선명"].astype(str).apply(lambda x: line_name_map.get(x, x))

# ===== 역명_clean 추가 =====
def make_clean_name(station_name):
    return re.sub(r"\(.*?\)", "", str(station_name)).strip()

all_dfs = [df, df_air, df_4, df_9, df_경강, df_경의중앙, df_수인, df_신분당선,
           df_incheon, df_경춘, df_우의신설, df_의정부경전철]

for df_line in all_dfs:
    if "역명" in df_line.columns:
        df_line["역명_clean"] = df_line["역명"].apply(make_clean_name)

# ===== 저장 =====
df_incheon.to_csv("인천1호선 소요시간_초.csv", index=False, encoding="utf-8")
df.to_csv("3호선_추가소요시간_초.csv", index=False, encoding="utf-8")
df_air.to_csv("공항철도_소요시간_초.csv", index=False, encoding="utf-8")
df_4.to_csv("4호선_추가소요시간_초.csv", index=False, encoding="utf-8")
df_9.to_csv("9호선_소요시간_초.csv", index=False, encoding="utf-8")
df_경강.to_csv("경강선_소요시간_초.csv", index=False, encoding="utf-8")
df_경의중앙.to_csv("경의중앙선_소요시간_초.csv", index=False, encoding="utf-8")
df_수인.to_csv("수인선_소요시간_초.csv", index=False, encoding="utf-8")
df_신분당선.to_csv("신분당선_소요시간_초.csv", index=False, encoding="utf-8")
df_incheon.to_csv("인천1호선_소요시간_초.csv", index=False, encoding="utf-8")
df_경춘.to_csv("경춘선_소요시간_초.csv", index=False, encoding="utf-8")
df_우의신설.to_csv("우이신설경전철_소요시간_초.csv", index=False, encoding="utf-8")
df_의정부경전철.to_csv("의정부경전철_소요시간_초.csv", index=False, encoding="utf-8")

import pandas as pd
import re

# 대상 파일 목록
files = [
    "용인경전철_에버라인역_소요시간.csv",
    "의정부경전철_소요시간.csv",
    "인천1,2호선 및 7호선 일부 소요시간.csv",
    "공항철도_소요시간.csv",
    "수도권1호선_소요시간.csv"
]

def time_to_seconds(t):
    if isinstance(t, str) and ":" in t:
        m, s = t.split(":")
        return int(m) * 60 + int(s)
    elif isinstance(t, (int, float)):
        return int(t)
    else:
        return None

def make_clean_name(name):
    return re.sub(r"\(.*?\)", "", str(name)).strip()

for file in files:
    df = pd.read_csv(file, encoding="utf-8-sig", dtype=str)

    # 소요시간 → 초 단위 변환
    if "소요시간" in df.columns:
        df["소요시간"] = df["소요시간"].apply(time_to_seconds)

    # 역명_clean 생성
    if "역명" in df.columns:
        df["역명_clean"] = df["역명"].apply(make_clean_name)

    # 저장
    df.to_csv(file.replace(".csv", "_updated.csv"), index=False, encoding="utf-8-sig")

print("변환 완료")

import pandas as pd
import re

file_path = "인천1,2호선 및 7호선 일부 소요시간_updated.csv"

df = pd.read_csv(file_path, encoding="utf-8-sig", dtype=str)

# 당역 → 역명
df = df.rename(columns={"당역": "역명"})

# 역명_clean 생성
df["역명_clean"] = df["역명"].apply(lambda x: re.sub(r"\(.*?\)", "", str(x)).strip())

# 저장
df.to_csv("인천1,2호선 및 7호선 일부 소요시간_clean.csv", index=False, encoding="utf-8-sig")
print("변환 완료")

import os

rename_map = {
    "인천1,2호선 및 7호선 일부 소요시간_clean.csv": "인천1,2호선_소요시간_초.csv",
    "용인경전철_에버라인역_소요시간_updated.csv": "용인경전철_소요시간_초.csv",
    "의정부경전철_소요시간_updated.csv": "의정부경전철_소요시간_초.csv"
}

for old_name, new_name in rename_map.items():
    if os.path.exists(old_name):
        os.rename(old_name, new_name)
        print(f"{old_name} → {new_name}")'''

import pandas as pd
df_1 = pd.read_csv('인천1,2호선_소요시간_초.csv')
df_2 = pd.read_csv('우이신설선_소요시간.csv')
df_3 = pd.read_csv('용인경전철_소요시간_초.csv')
df_4 = pd.read_csv('의정부경전철_소요시간_초.csv')
# 호선명 매핑
line_name_map = {
    "우이신설": "우이신설경전철",
    "의정부": "의정부경전철",
    "인천 1호선": "인천1호선",
    "인천 2호선": "인천2호선",
    "에버라인": "용인경전철"
}

# 매핑 적용
for df in [df_1, df_2, df_3, df_4]:
    if "호선" in df.columns:
        df["호선"] = df["호선"].replace(line_name_map)
    elif "선명" in df.columns:  # 일부 파일이 '선명' 컬럼 사용 가능
        df["선명"] = df["선명"].replace(line_name_map)

# 저장
df_1.to_csv("인천1,2호선_소요시간_초.csv", index=False, encoding="utf-8-sig")
df_2.to_csv("우이신설경전철_소요시간_초.csv", index=False, encoding="utf-8-sig")
df_3.to_csv("용인경전철_소요시간_초.csv", index=False, encoding="utf-8-sig")
df_4.to_csv("의정부경전철_소요시간_초.csv", index=False, encoding="utf-8-sig")

print("호선명 변경 및 저장 완료")


