import pandas as pd
import glob

# 노선 정렬 순서
line_order = [
    "1호선", "2호선", "3호선", "4호선", "5호선", "6호선", "7호선", "8호선", "9호선",
    "경강선", "경의중앙선", "경춘선", "공항철도", "수인분당선", "신분당선",
    "우이신설경전철", "의정부경전철", "인천1호선", "인천2호선", "용인경전철"
]

all_files = glob.glob("*_소요시간_초.csv")
df_list = []

for file in all_files:
    df = pd.read_csv(file, encoding="utf-8-sig")

    # 컬럼명 통일
    col_map = {}
    if "호선" in df.columns:
        col_map["호선"] = "노선"
    elif "선명" in df.columns:
        col_map["선명"] = "노선"

    if "역명" in df.columns:
        col_map["역명"] = "역명_clean" if "역명_clean" not in df.columns else "역명"
    elif "당역" in df.columns:
        col_map["당역"] = "역명"

    if "소요시간(초)" in df.columns:
        col_map["소요시간(초)"] = "소요시간"

    df = df.rename(columns=col_map)

    # 역명_clean이 없으면 생성
    if "역명_clean" not in df.columns and "역명" in df.columns:
        df["역명_clean"] = df["역명"].str.replace(r"\(.*?\)", "", regex=True).str.strip()

    # 필요한 컬럼만 남기기
    needed_cols = ["노선", "역명_clean", "전역", "소요시간"]
    for col in needed_cols:
        if col not in df.columns:
            print(f"⚠ {file} 에 '{col}' 컬럼이 없습니다.")
            break
    else:
        df_list.append(df[needed_cols])

# 합치기
merged_df = pd.concat(df_list, ignore_index=True)

# 노선 순서 정렬
merged_df["노선"] = pd.Categorical(merged_df["노선"], categories=line_order, ordered=True)
merged_df = merged_df.sort_values(["노선"]).reset_index(drop=True)

# 저장
merged_df.to_csv("edges.csv", index=False, encoding="utf-8-sig")
print("✅ edges.csv 생성 완료")
