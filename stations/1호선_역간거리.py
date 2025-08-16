import pandas as pd
import numpy as np

# 파일 경로
DIST_CSV = "국가철도공단_수도권1호선_역간거리_20241015.csv"  # 네가 가진 1호선 거리 파일명 사용
SPEED_CSV = "지하철_속도.csv"
OUTPUT_CSV = "수도권1호선_소요시간(초)_추가.csv"

def read_csv_smart(path):
    for enc in ("cp949", "euc-kr", "utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    return pd.read_csv(path, encoding="cp949", engine="python", on_bad_lines="skip")

# 1) 로드
dist = read_csv_smart(DIST_CSV)
spd  = read_csv_smart(SPEED_CSV)

orig_cols = dist.columns.tolist()
dist.columns = [c.strip() for c in dist.columns]
spd.columns  = [c.strip() for c in spd.columns]

# 2) 컬럼 파악
col_line  = next((c for c in dist.columns if any(k in c for k in ["선명","노선","호선","Line"])), None)
col_oper  = next((c for c in dist.columns if any(k in c for k in ["운영기관","운영","기관"])), None)
col_stat  = next((c for c in dist.columns if any(k in c for k in ["역명","정거장","Station"])), None)
col_gap   = next((c for c in dist.columns if "역간거리" in c or "거리(" in c or "km" in c.lower()), None)
if col_gap is None:
    raise ValueError("거리 CSV에서 '역간거리' 컬럼을 찾지 못했습니다.")

col_sp_line = next((c for c in spd.columns if any(k in c for k in ["노선","선명","호선","Line"])), None)
col_sp_gen  = next((c for c in spd.columns if "속도(일반" in c or "일반" in c), None)
col_sp_exp  = next((c for c in spd.columns if "속도(급행" in c or "급행" in c), None)
if col_sp_line is None:
    raise ValueError("속도 CSV에서 노선명 컬럼을 찾지 못했습니다.")

# 3) 경인/경부 속도 읽기 (일반 우선, 없으면 급행, 없으면 숫자평균)
if col_sp_gen and pd.api.types.is_numeric_dtype(spd[col_sp_gen]):
    spd["_속도_kmh"] = pd.to_numeric(spd[col_sp_gen], errors="coerce")
elif col_sp_exp and pd.api.types.is_numeric_dtype(spd[col_sp_exp]):
    spd["_속도_kmh"] = pd.to_numeric(spd[col_sp_exp], errors="coerce")
else:
    num_cols = [c for c in spd.columns if pd.api.types.is_numeric_dtype(spd[c])]
    spd["_속도_kmh"] = spd[num_cols].astype(float).mean(axis=1) if num_cols else np.nan

def subline_key(s: str) -> str:
    s = str(s)
    if "1호선" in s and "경인" in s: return "경인"
    if "1호선" in s and "경부" in s: return "경부"
    if "1호선" in s and "경원" in s: return "경원"
    return ""

spd_1 = spd[spd[col_sp_line].astype(str).str.contains("1호선")].copy()
spd_1["__하위"] = spd_1[col_sp_line].apply(subline_key)
speed_map = dict(zip(spd_1["__하위"], spd_1["_속도_kmh"]))

# 경원선 속도가 표에 없으면 기본값 (원하면 바꾸세요)
speed_map.setdefault("경원", 34.0)

# 공용구간(청량리~구로)용 평균 속도
avg_trunk_speed = np.nanmean([speed_map.get("경인"), speed_map.get("경부")])

# 4) 역명 기반 분류 세트 (필요시 확장)
gyeongin_st = {
    "인천","동인천","제물포","도원","도화","주안","간석","동암","백운","부평","부개","송내",
    "중동","부천","소사","역곡","오류동","온수","개봉","구일","구로"
}
gyeongbu_st = {
    "금천구청","독산","가산디지털단지","광명","석수","관악","안양","명학","금정","군포","당정","의왕","성균관대", "화서",
    "수원","세류","병점","서동탄","세마","오산대","오산","진위","송탄","서정리","평택지제","평택",
    "성환","직산","두정","천안","봉명","쌍용(나사렛대)","아산","탕정","배방","온양온천","신창(순천향대)"
}
gyeongwon_st = {
    "연천","전곡","청산","소요산","동두천","보산","동두천중앙","지행","덕정","덕계","양주",
    "녹양","가능","의정부","회룡","망월사","도봉산","도봉","방학","창동","녹천","월계","광운대",
    "석계","신이문","외대앞","회기","청량리(서울시립대입구)"
}
# 공용구간(서울교통공사 운영, 청량리~구로 방향)
trunk_st = {
    "제기동","신설동","동묘앞","동대문","종로5가","종로3가","종각","시청","서울역","남영","용산","노량진","대방","신길","영등포","신도림","구로"
}

def classify_branch(row):
    st = str(row[col_stat]) if col_stat else ""
    op = str(row[col_oper]) if col_oper else ""
    # 명시적 역명 우선
    if st in gyeongin_st:  return "경인"
    if st in gyeongbu_st:  return "경부"
    if st in gyeongwon_st: return "경원"
    if st in trunk_st:     return "TRUNK"  # 공용구간
    # 운영기관 힌트: 서울교통공사면 공용구간일 확률 높음
    if "서울교통공사" in op:
        return "TRUNK"
    return ""  # 미분류

dist["_분류"] = dist.apply(classify_branch, axis=1)

# 5) 속도 할당
dist["_역간거리_km"] = pd.to_numeric(dist[col_gap], errors="coerce")
dist["_속도_kmh"] = np.nan
dist.loc[dist["_분류"]=="경인",  "_속도_kmh"] = speed_map.get("경인")
dist.loc[dist["_분류"]=="경부",  "_속도_kmh"] = speed_map.get("경부")
dist.loc[dist["_분류"]=="경원",  "_속도_kmh"] = speed_map.get("경원")
dist.loc[dist["_분류"]=="TRUNK","_속도_kmh"] = avg_trunk_speed

# 6) 소요시간(초, 정수) 계산
dist["소요시간"] = ((dist["_역간거리_km"] / dist["_속도_kmh"]) * 3600).round(0).astype("Int64")

# 7) 결과 저장 (기존 컬럼 + 소요시간)
result = dist[orig_cols + ["소요시간"]].copy()
result.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
print(f"[완료] 저장: {OUTPUT_CSV}")
print("미분류 행 수:", int((dist['_분류']=="").sum()))
