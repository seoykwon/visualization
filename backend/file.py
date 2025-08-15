import pandas as pd
import re
import glob
import os

# 현재 폴더 내 CSV 파일 전부 가져오기
csv_files = glob.glob("*.csv")

for file in csv_files:
    df = pd.read_csv(file)

    # 노선 열 처리: '선명' → '노선'
    if "노선" not in df.columns:
        if "선명" in df.columns:
            df = df.rename(columns={"선명": "노선"})
        elif "호선" in df.columns:
            df = df.rename(columns={"호선": "노선"})
        else:
            df["노선"] = ""  # 없으면 빈값 채움

    # 역명_clean, 전역_clean 생성 (괄호 제거, NaN → 빈 문자열)
    if "역명" in df.columns:
        df["역명_clean"] = df["역명"].fillna("").apply(lambda x: re.sub(r"\(.*?\)", "", str(x)).strip())
    else:
        df["역명_clean"] = ""

    if "전역" in df.columns:
        df["전역_clean"] = df["전역"].fillna("").apply(lambda x: re.sub(r"\(.*?\)", "", str(x)).strip())
    else:
        df["전역_clean"] = ""

    # 소요시간 열이 없으면 빈값 채움
    if "소요시간" not in df.columns:
        df["소요시간"] = ""

    # 필요한 열만 추출
    cols_to_keep = ["노선", "역명_clean", "전역_clean", "소요시간"]
    df_clean = df[cols_to_keep]

    # 저장
    clean_filename = file.replace(".csv", "_clean.csv")
    df_clean.to_csv(clean_filename, index=False)

    print(f"{file} → {clean_filename} 저장 완료")
