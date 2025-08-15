# station_OD.py  — ext ID 먼저 시도, 실패 시 searchStation으로 보정
import os, time, argparse, requests, pandas as pd
from datetime import datetime

ODSAY_BASE = "https://api.odsay.com/v1/api"

def is_int_like(x):
    try:
        int(str(x).strip())
        return True
    except:
        return False

def norm_line(line: str) -> str:
    if not isinstance(line, str):
        return ""
    s = line.strip().replace("수도권 ", "")
    if s.endswith("호선"):
        head = s.replace("호선","")
        if head.isdigit():
            s = f"{int(head)}호선"
    return s

def call_api(path, params):
    url = f"{ODSAY_BASE}/{path}"
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    j = r.json()
    # ODSAY는 실패 시 {"error":{code,msg}} 형태를 돌려줌
    if isinstance(j, dict) and "error" in j and "result" not in j:
        err = j["error"]
        return None, err.get("code"), err.get("message") or err.get("msg")
    return j, None, None

def try_subway_info(api_key, sid):
    j, code, msg = call_api("subwayStationInfo", {"apiKey": api_key, "lang": 0, "stationID": sid})
    if j is None or "result" not in j:
        return None, code, msg
    res = j["result"]
    def take_list(obj, key):
        if not isinstance(obj, dict): return []
        v = obj.get(key)
        return v if isinstance(v, list) else []

    prevL = take_list(res.get("prevOBJ") or {}, "station")
    nextL = take_list(res.get("nextOBJ") or {}, "station")
    exL   = take_list(res.get("exOBJ")   or {}, "station")

    def pick(L, k): return [str(d.get(k)) for d in L if isinstance(d, dict) and d.get(k) is not None]

    return {
        "laneName_from_API": (res.get("laneName") or "").replace("수도권 ", ""),
        "prevStationIDs": ",".join(pick(prevL, "stationID")),
        "prevStationNames": ",".join(pick(prevL, "stationName")),
        "nextStationIDs": ",".join(pick(nextL, "stationID")),
        "nextStationNames": ",".join(pick(nextL, "stationName")),
        "exchangeStationIDs": ",".join(pick(exL, "stationID")),
        "exchangeLineNames": ",".join([(d.get("laneName") or "").replace("수도권 ","") for d in exL if isinstance(d, dict)]),
        "exchangeStationNames": ",".join(pick(exL, "stationName")),
    }, None, None

def pick_from_search(search_json, want_line_norm, want_name):
    res = (search_json or {}).get("result") or {}
    arr = res.get("station") or []
    if not isinstance(arr, list): arr = []
    # 1순위: 노선 일치
    for s in arr:
        lane = (s.get("laneName") or "").replace("수도권 ", "")
        if want_line_norm and want_line_norm in lane:
            return s
    # 2순위: 역명 완전일치
    for s in arr:
        if (s.get("stationName") or "") == want_name:
            return s
    return arr[0] if arr else None

def find_sid_via_search(api_key, name, want_line_norm):
    j, code, msg = call_api("searchStation", {"apiKey": api_key, "lang": 0, "stationName": name})
    if j is None: 
        return None, code, msg
    cand = pick_from_search(j, want_line_norm, name)
    if not cand: 
        return None, "SEARCH_EMPTY", "no candidate from searchStation"
    return int(cand["stationID"]), None, None

def enrich_row(row, api_key):
    name = str(row.get("stationName") or "").strip()
    line = norm_line(str(row.get("lineName") or ""))
    ext  = row.get("external_ID")
    used_sid = None
    source = ""
    error_code = ""
    error_msg = ""

    # 1) external_ID가 숫자면 먼저 시도
    if is_int_like(ext):
        used_sid = int(ext)
        info, code, msg = try_subway_info(api_key, used_sid)
        if info:
            info.update({"odsay_stationID": used_sid, "api_status":"ok", "api_error":""})
            return info
        # 실패 → 서치로 보정
        source = "fallback_search"
        error_code, error_msg = code or "", msg or ""
        used_sid = None

    # 2) searchStation로 sid 찾기
    sid, code, msg = find_sid_via_search(api_key, name, line)
    if sid is None:
        return {
            "laneName_from_API":"", "prevStationIDs":"", "prevStationNames":"",
            "nextStationIDs":"", "nextStationNames":"", "exchangeStationIDs":"",
            "exchangeLineNames":"", "exchangeStationNames":"",
            "odsay_stationID":"", "api_status":"error",
            "api_error": f"{source or 'search'} failed ({code}): {msg}",
        }

    # 3) 찾은 sid로 재시도
    used_sid = sid
    info, code, msg = try_subway_info(api_key, used_sid)
    if info:
        info.update({"odsay_stationID": used_sid, "api_status":"search_used" if source else "ok", "api_error":""})
        return info

    return {
        "laneName_from_API":"", "prevStationIDs":"", "prevStationNames":"",
        "nextStationIDs":"", "nextStationNames":"", "exchangeStationIDs":"",
        "exchangeLineNames":"", "exchangeStationNames":"",
        "odsay_stationID": used_sid, "api_status":"error",
        "api_error": f"subwayStationInfo failed ({code}): {msg}",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i","--input", default="station_codes_renamed.csv")
    ap.add_argument("-o","--output", default="station_neighbors_enriched.csv")
    ap.add_argument("--sleep", type=float, default=0.12)
    args = ap.parse_args()

    api_key = os.getenv("ODSAY_API_KEY")
    if not api_key:
        raise SystemExit("❌ ODSAY_API_KEY 환경변수를 먼저 설정하세요.")

    df = pd.read_csv(args.input, dtype=str)
    for col in ["stationID","stationName","lineName","external_ID"]:
        if col not in df.columns:
            raise SystemExit("입력 CSV에 stationID, stationName, lineName, external_ID 네 컬럼이 있어야 합니다.")
    total = len(df)

    out_rows = []
    for i, row in df.iterrows():
        payload = enrich_row(row, api_key)
        out_rows.append({
            "stationID": row.get("stationID"),
            "stationName": row.get("stationName"),
            "lineName": row.get("lineName"),
            "external_ID": row.get("external_ID"),
            **payload,
            "fetched_at": datetime.now().isoformat(timespec="seconds")
        })
        st = payload.get("api_status")
        used_sid = payload.get("odsay_stationID")
        if st == "error":
            print(f"[ERR] {i+1}/{total} rowSID={row.get('stationID')} usedSID={used_sid} -> {payload.get('api_error')}")
        else:
            p = payload.get("prevStationIDs","")
            n = payload.get("nextStationIDs","")
            ex= payload.get("exchangeStationIDs","")
            print(f"[OK] {i+1}/{total} rowSID={row.get('stationID')} usedSID={used_sid} (prev:{len(p.split(',')) if p else 0}, next:{len(n.split(',')) if n else 0}, ex:{len(ex.split(',')) if ex else 0})")
        time.sleep(args.sleep)

    cols = [
        "stationID","stationName","lineName","external_ID",
        "odsay_stationID","laneName_from_API",
        "prevStationIDs","prevStationNames",
        "nextStationIDs","nextStationNames",
        "exchangeStationIDs","exchangeLineNames","exchangeStationNames",
        "api_status","api_error","fetched_at"
    ]
    out_df = pd.DataFrame(out_rows)[cols]
    out_df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\n✅ wrote -> {os.path.abspath(args.output)}  (rows={len(out_df)})")

if __name__ == "__main__":
    main()
