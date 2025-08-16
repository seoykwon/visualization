import pandas as pd
import glob

# 현재 폴더 내 _clean.csv 파일 모두 찾기
clean_files = glob.glob("*_clean.csv")

dfs = []
for file in clean_files:
    df = pd.read_csv(file)

    # 혹시 누락된 컬럼이 있으면 빈값으로 채움
    for col in ["노선", "역명_clean", "전역_clean", "소요시간"]:
        if col not in df.columns:
            df[col] = ""

    # 순서 맞추기
    df = df[["노선", "역명_clean", "전역_clean", "소요시간"]]
    dfs.append(df)

# 전체 병합
merged_df = pd.concat(dfs, ignore_index=True)

# 병합 결과 저장
merged_df.to_csv("merged_clean.csv", index=False)

print(f"총 {len(clean_files)}개 파일 병합 완료 → merged_clean.csv 저장")


