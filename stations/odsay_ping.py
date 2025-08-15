import os
import pandas as pd

IN_FILE  = "서울교통공사_노선별 지하철역 정보.csv"
OUT_FILE = "station_codes_renamed.csv"

# 1) 읽기
df = pd.read_csv(IN_FILE, dtype=str, encoding="utf-8")
df.columns = [c.strip() for c in df.columns]
df = df.applymap(lambda v: v.strip() if isinstance(v, str) else v)

# 2) 컬럼명 표준화
df = df.rename(columns={
    "전철역코드": "stationID",
    "전철역명":   "stationName",
    "호선":       "lineName",
    "외부코드":   "external_ID",
    "exteranl_ID": "external_ID",  # 오타 대비
})

# 3) 다국어 컬럼 제거 (있으면만)
df = df.drop(columns=["전철명명(영문)", "전철명명(중문)", "전철명명(일문)"], errors="ignore")

# 4) 필요한 4개 컬럼만 남기기 (나머지는 강제 제거)
keep = ["stationID", "stationName", "lineName", "external_ID"]
for col in keep:
    if col not in df.columns:
        df[col] = pd.NA
df = df[keep]

# 5) stationID 숫자화 + 결측/중복 제거 + 정렬
df["stationID"] = pd.to_numeric(df["stationID"], errors="coerce").astype("Int64")
df = (
    df.dropna(subset=["stationID"])
      .drop_duplicates(subset=["stationID"], keep="first")
      .sort_values(["lineName", "stationID"], kind="stable")
      .reset_index(drop=True)
)

# 6) 저장 (엑셀 호환 위해 utf-8-sig)
df.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")

print(f"[OUT] {os.path.abspath(OUT_FILE)}")
print("columns:", list(df.columns))
print("rows:", len(df))
