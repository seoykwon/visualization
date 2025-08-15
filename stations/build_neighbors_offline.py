#!/usr/bin/env python3
import argparse, os, sys
from datetime import datetime
import pandas as pd

def log(msg):  # 항상 바로 출력
    print(msg, flush=True)

def build(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 필요한 컬럼 체크
    need = {"stationID", "stationName", "lineName", "external_ID"}
    missing = need - set(df.columns)
    if missing:
        raise ValueError(f"input CSV missing columns: {sorted(missing)}")

    # external_ID 숫자화 & 기본 정리
    df["external_ID"] = pd.to_numeric(df["external_ID"], errors="coerce")
    df = df.dropna(subset=["external_ID", "stationID", "stationName", "lineName"])
    df["external_ID"] = df["external_ID"].astype(int)

    # 라인 내 이전/다음역
    df = df.sort_values(["lineName", "external_ID"]).reset_index(drop=True)
    df["prevStationID"] = df.groupby("lineName")["stationID"].shift(1)
    df["nextStationID"] = df.groupby("lineName")["stationID"].shift(-1)

    id_to_name = dict(zip(df["stationID"], df["stationName"]))
    id_to_line = dict(zip(df["stationID"], df["lineName"]))

    df["prevStationName"] = df["prevStationID"].map(lambda x: "" if pd.isna(x) else id_to_name.get(int(x) if isinstance(x, float) else x, ""))
    df["nextStationName"] = df["nextStationID"].map(lambda x: "" if pd.isna(x) else id_to_name.get(int(x) if isinstance(x, float) else x, ""))

    # 환승: 동일 역명끼리(다른 노선)
    name_groups = df.groupby("stationName")["stationID"].apply(list)
    def exchanges(row):
        ids = [s for s in name_groups.get(row["stationName"], []) if s != row["stationID"]]
        ex_ids   = ",".join(map(str, ids))
        ex_lines = ",".join(id_to_line[s] for s in ids)
        ex_names = ",".join([row["stationName"]]*len(ids))
        return ex_ids, ex_lines, ex_names

    ex_ids, ex_lines, ex_names = zip(*df.apply(exchanges, axis=1))

    out = pd.DataFrame({
        "stationID": df["stationID"].astype(int),
        "stationName": df["stationName"],
        "lineName": df["lineName"],
        "external_ID": df["external_ID"].astype(int),

        # API 없이 채우는 칼럼들
        "odsay_stationID": "",
        "laneName_from_API": "",

        "prevStationIDs": df["prevStationID"].fillna("").astype(str).str.replace(".0", "", regex=False),
        "prevStationNames": df["prevStationName"],
        "nextStationIDs": df["nextStationID"].fillna("").astype(str).str.replace(".0", "", regex=False),
        "nextStationNames": df["nextStationName"],
        "exchangeStationIDs": list(ex_ids),
        "exchangeLineNames": list(ex_lines),
        "exchangeStationNames": list(ex_names),

        "api_status": "offline",
        "api_error": "",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    })
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i","--input", required=True)
    ap.add_argument("-o","--output", required=True, help="output CSV path")
    ap.add_argument("-v","--verbose", action="store_true")
    args = ap.parse_args()

    in_path  = os.path.abspath(args.input)
    out_path = os.path.abspath(args.output)

    log(f"[IN]  {in_path} exists={os.path.exists(in_path)}")
    try:
        df = pd.read_csv(in_path, encoding="utf-8-sig")
    except Exception as e:
        log(f"[ERR] read failed: {e}")
        sys.exit(1)

    if args.verbose:
        log(f"[READ] rows={len(df)} cols={list(df.columns)}")

    try:
        out_df = build(df)
    except Exception as e:
        log(f"[ERR] build failed: {e}")
        sys.exit(2)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    try:
        out_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    except Exception as e:
        log(f"[ERR] write failed: {e}")
        sys.exit(3)

    log(f"[DONE] wrote -> {out_path} (rows={len(out_df)})")

if __name__ == "__main__":
    main()
