# app.py
import os
import json
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from haversine import haversine
from flask_cors import CORS

# Load API keys
load_dotenv()
ODSAY_KEY = os.getenv("ODSAY_API_KEY")

app = Flask(__name__)
# CORS(app)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# Load station coordinates from JSON
with open("station_coords.json", encoding='utf-8') as f:
    STATIONS = json.load(f)

# 사용자 클릭 위치에서 가장 가까운 역 찾기
def find_nearest_station(user_lat, user_lng):
    user_loc = (user_lat, user_lng)
    nearest = min(
        STATIONS,
        key=lambda station: haversine(user_loc, (float(station["lat"]), float(station["lng"])))
    )
    return nearest

# 출발역에서 모든 지하철역까지의 소요시간 계산
def get_subway_times_from(start_lat, start_lng):
    results = []
    for station in STATIONS:
        url = f"https://api.odsay.com/v1/api/searchPubTransPathT?"
        params = {
            "SX": start_lng,
            "SY": start_lat,
            "EX": station["lng"],
            "EY": station["lat"],
            "OPT": 0,
            "apiKey": ODSAY_KEY
        }
        res = requests.get(url, params=params)
        if res.status_code != 200:
            continue
        try:
            time = res.json()["result"]["path"][0]["info"]["totalTime"]
            results.append({
                "name": station["name"],
                "lat": station["lat"],
                "lng": station["lng"],
                "time": time
            })
        except (KeyError, IndexError):
            continue
    return results

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
