import pandas as pd
import numpy as np

# ====== 파일 경로 ======
DIST_CSV = "국가철도공단_수도권1호선_역간거리_20241015.csv"
SPEED_CSV = "지하철_속도.csv"
OUTPUT_CSV = "수도권1호선_소요시간(초)_추가.csv"

# ====== 유틸: 인코딩 자동 로드 ======
def read_csv_smart(path):
    for enc in ("cp949", "euc-kr", "utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    # 최후 수단
    return pd.read_csv(path, encoding="cp949", engine="python", on_bad_lines="skip")

# ====== 데이터 로드 ======
dist = read_csv_smart(DIST_CSV)
spd  = read_csv_smart(SPEED_CSV)

# 원본 컬럼 보존
orig_cols = dist.columns.tolist()

# 공백 제거
dist.columns = [c.strip() for c in dist.columns]
spd.columns  = [c.strip() for c in spd.columns]

# ====== 컬럼 추정(파일 형식이 약간 달라도 동작하도록) ======
# 거리 파일
col_line = next((c for c in dist.columns if any(k in c for k in ["선명","노선","호선","Line"])), None)
col_station = next((c for c in dist.columns if any(k in c for k in ["역명","정거장","Station"])), None)
col_gap = next((c for c in dist.columns if ("역간거리" in c) or ("거리" in c) or ("km" in c.upper())), None)

if col_gap is None:
    raise ValueError("거리 CSV에서 역간거리 컬럼을 찾지 못했습니다.")

# 속도 파일: 1호선(경인선), 1호선(경부선)과 일반/급행 속도
col_speed_line = next((c for c in spd.columns if any(k in c for k in ["노선","선명","호선","Line"])), None)
col_speed_gen  = next((c for c in spd.columns if "속도(일반" in c or "일반" in c), None)
col_speed_exp  = next((c for c in spd.columns if "속도(급행" in c or "급행" in c), None)

if col_speed_line is None:
    raise ValueError("속도 CSV에서 노선명 컬럼을 찾지 못했습니다.")

# 사용할 속도: 일반 속도를 우선, 없으면 급행, 그것도 없으면 숫자형 평균
if col_speed_gen and pd.api.types.is_numeric_dtype(spd[col_speed_gen]):
    spd["_속도_kmh"] = pd.to_numeric(spd[col_speed_gen], errors="coerce")
elif col_speed_exp and pd.api.types.is_numeric_dtype(spd[col_speed_exp]):
    spd["_속도_kmh"] = pd.to_numeric(spd[col_speed_exp], errors="coerce")
else:
    num_cols = [c for c in spd.columns if pd.api.types.is_numeric_dtype(spd[c])]
    spd["_속도_kmh"] = spd[num_cols].astype(float).mean(axis=1) if num_cols else np.nan

# ====== 1호선 하위노선(경인/경부) 속도 사전 만들기 ======
# 예: "1호선(경인선)" -> "경인", "1호선(경부선)" -> "경부"
def subline_key(s: str) -> str:
    s = str(s)
    if "1호선" in s and "경인" in s:
        return "경인"
    if "1호선" in s and "경부" in s:
        return "경부"
    return ""

spd_1 = spd[spd[col_speed_line].astype(str).str.contains("1호선")].copy()
spd_1["__하위"] = spd_1[col_speed_line].apply(subline_key)
speed_map = dict(zip(spd_1["__하위"], spd_1["_속도_kmh"]))  # {"경인": 37.6, "경부": 44.6} 형태 기대

# ====== 거리 데이터의 하위노선 분류 ======
def norm(s):
    if pd.isna(s): return s
    return str(s).replace(" ", "").replace("\u00a0", "")

# 1) 선명/노선 컬럼에 '경인' 또는 '경부'가 들어있으면 우선 사용
if col_line:
    dist["__하위"] = dist[col_line].astype(str).apply(norm)
    dist.loc[dist["__하위"].str.contains("경인", na=False), "__하위"] = "경인"
    dist.loc[dist["__하위"].str.contains("경부", na=False), "__하위"] = "경부"
else:
    dist["__하위"] = ""

# 2) 그래도 비어 있으면 역명 기반 보정(대표역 목록; 필요시 자유롭게 추가/수정)
if col_station:
    gyeongin_st = {
        "인천","동인천","제물포","도화","주안","간석","동암","백운","부평","부개","송내",
        "중동","부천","소사","역곡","오류동","온수","개봉","구일","구로"
    }
    gyeongbu_st = {
        "금천구청","석수","관악","안양","명학","금정","군포","당정","의왕","성균관대","수원",
        "세류","병점","서정리","송탄","진위","평택","성환","두정","천안"
    }

    # 역명이 대표 목록에 걸리면 하위노선 지정
    m_null = (dist["__하위"] != "경인") & (dist["__하위"] != "경부")
    dist.loc[m_null & dist[col_station].isin(gyeongin_st), "__하위"] = "경인"
    dist.loc[m_null & dist[col_station].isin(gyeongbu_st), "__하위"] = "경부"

# 3) 그래도 못 정하면 빈값 그대로 두되 속도 NaN → 소요시간 NaN 처리
dist["_역간거리_km"] = pd.to_numeric(dist[col_gap], errors="coerce")
dist["_속도_kmh"] = dist["__하위"].map(speed_map)  # 경인/경부 매핑

# ====== 소요시간(초, 정수) 계산 ======
dist["소요시간"] = ((dist["_역간거리_km"] / dist["_속도_kmh"]) * 3600).round(0).astype("Int64")

# ====== 결과 저장: 기존 테이블 + 소요시간 ======
result = dist[orig_cols + ["소요시간"]].copy()
result.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
print(f"[완료] 저장: {OUTPUT_CSV}")
# 참고: 소요시간이 비어 있으면 하위노선 분류가 안 된 행이니 역명 목록/선명 값을 보강해 주세요.
