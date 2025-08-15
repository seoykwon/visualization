# app.py
import os
import json
import requests
from flask import request, jsonify
from dotenv import load_dotenv
from haversine import haversine
from flask_cors import CORS

# short_time.py의 Flask 앱 불러오기
from backend.station_OD import create_app
app = create_app()  # short_time.py의 경로탐색 API 포함
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# Load API keys
load_dotenv()
ODSAY_KEY = os.getenv("ODSAY_API_KEY")

# Load station coordinates from JSON
with open("station_coords.json", encoding='utf-8') as f:
    STATIONS = json.load(f)

# ------------------------------
# 기존 app.py 기능 그대로 유지
# ------------------------------

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

    reachable_stations = []

    for station in STATIONS:
        try:
            station_lat = float(station['lat'])
            station_lng = float(station['lng'])

            url = f"https://api.odsay.com/v1/api/searchPubTransPathT?SX={user_lng}&SY={user_lat}&EX={station_lng}&EY={station_lat}&OPT=0&apiKey={ODSAY_KEY}"
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

@app.route('/api/station-times', methods=['POST'])
def station_times():
    data = request.json
    station_name = data.get('station')
    
    if not station_name:
        return jsonify({"error": "Missing station name"}), 400
        
    # Find the target station
    target_station = next((s for s in STATIONS if s['name'] == station_name), None)
    if not target_station:
        return jsonify({"error": "Station not found"}), 404
        
    results = []
    target_lat = float(target_station['lat'])
    target_lng = float(target_station['lng'])
    
    # Find nearby stations (within approximately 2km)
    nearby_stations = [
        s for s in STATIONS 
        if s['name'] != station_name and 
        haversine((target_lat, target_lng), (float(s['lat']), float(s['lng']))) <= 2
    ]
    
    for station in nearby_stations:
        try:
            url = f"https://api.odsay.com/v1/api/searchPubTransPathT"
            params = {
                "SX": target_lng,
                "SY": target_lat,
                "EX": station['lng'],
                "EY": station['lat'],
                "OPT": 0,
                "apiKey": ODSAY_KEY
            }
            
            res = requests.get(url, params=params)
            if res.status_code != 200:
                continue
                
            data = res.json()
            path_info = data['result']['path'][0]
            
            # Get transfer and total time information
            total_time = path_info['info']['totalTime']
            transfer_count = path_info['info'].get('subwayTransitCount', 0)
            
            # Get detailed path information
            sub_paths = [p for p in path_info['subPath'] if p['trafficType'] == 1]  # 1 means subway
            
            results.append({
                "station_name": station['name'],
                "distance": round(haversine((target_lat, target_lng), 
                                         (float(station['lat']), float(station['lng'])), 
                                         unit='km'), 2),
                "total_time": total_time,
                "transfer_count": transfer_count,
                "lat": station['lat'],
                "lng": station['lng'],
                "line_info": [{'line_name': p.get('lane')[0]['name'], 
                             'duration': p.get('sectionTime')} 
                            for p in sub_paths if 'lane' in p]
            })
            
        except Exception as e:
            print(f"Error processing station {station['name']}: {e}")
            continue
            
    return jsonify({
        "source_station": station_name,
        "nearby_stations": sorted(results, key=lambda x: x['total_time'])
    })

if __name__ == "__main__":
    app.run(debug=True)
