# app.py
import os
import json
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from haversine import haversine
from flask_cors import CORS

from coords import StationCoords
from times import PrecomputedTimes
from isochrone import polygons_from_station_times, build_featurecollection

# Load API keys
load_dotenv()
ODSAY_KEY = os.getenv("ODSAY_API_KEY")

app = Flask(__name__)
# CORS(app)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# 1) 역 좌표 & KD-tree (최근접역)
COORDS = StationCoords()
# 2) 미리 계산된 '역↔역 분단위 최단시간' CSV 로더
TIMES  = PrecomputedTimes()  # 기본 경로: backend/data/station_travel_times.csv

@app.route("/api/isochrone", methods=["POST"])
def api_isochrone():
    """
    입력(JSON): { lat, lng, thresholds?: [20,40,60,80,100], buffer_m?: 300 }
    출력: GeoJSON FeatureCollection
    """
    data = request.get_json(force=True)
    lat = float(data["lat"])
    lng = float(data["lng"])
    thresholds = data.get("thresholds") or [20, 40, 60, 80, 100]
    buffer_m   = int(data.get("buffer_m", 300))

    # 1) 클릭점에서 가장 가까운 '원점 역'
    origin = COORDS.nearest_station(lat, lng)

    # 2) (계산 X) 미리 계산된 CSV에서 원점 기준 {역:분} 읽기
    station_times = TIMES.times_from(origin)

    # 3) 20/40/60/80/100분 밴드별 역세권 버퍼 합집합 → GeoJSON
    bands = polygons_from_station_times(station_times, COORDS.station_pos,
                                        thresholds=thresholds,
                                        buffer_m_per_station=buffer_m)
    fc = build_featurecollection(bands)
    return jsonify(fc)

@app.route("/api/health", methods=["GET"])
def health():
    return {"ok": True}


# 📍 API: 좌표 받아서 소요 시간 반환
@app.route("/api/subway-times", methods=["POST"])
def subway_times():
    data = request.get_json()
    user_lat = data.get("lat")
    user_lng = data.get("lng")
    if not user_lat or not user_lng:
        return jsonify({"error": "Missing coordinates"}), 400

    results = get_subway_times_from(user_lat, user_lng)
    return jsonify(results)

@app.route('/api/accessible', methods=['POST'])
def accessible():
    data = request.json
    user_lat = float(data['lat'])
    user_lng = float(data['lng'])
    user_coord = (user_lat, user_lng)

    reachable_stations = []

    for station in STATIONS:
        try:
            station_lat = float(station['lat'])
            station_lng = float(station['lng'])

            url = f"https://api.odsay.com/v1/api/searchPubTransPathT?SX={user_lng}&SY={user_lat}&EX={station_lng}&EY={station_lat}&OPT=0&apiKey={ODSAY_API_KEY}"
            res = requests.get(url)
            res_data = res.json()

            # 지하철만 포함된 경로 찾기
            for path in res_data['result']['path']:
                if path['subPath'][0]['trafficType'] == 1:  # 1: subway
                    total_time = path['info']['totalTime']
                    reachable_stations.append({
                        "station": station['name'],
                        "lat": station_lat,
                        "lng": station_lng,
                        "time": total_time
                    })
                    break
        except Exception as e:
            print(f"Error for station {station['name']}: {e}")
            continue

    return jsonify(reachable_stations)

if __name__ == "__main__":
    app.run(debug=True)
