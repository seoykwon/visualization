# app.py
import os
import json
import requests
import pandas as pd
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from haversine import haversine
from flask_cors import CORS
import re # Added for normalize_station_name

# Load API keys
load_dotenv()
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# Load station coordinates from JSON
with open("station_coords.json", encoding='utf-8') as f:
    STATIONS = json.load(f)

# Load travel time data
TRAVEL_TIMES_DF = None
try:
    TRAVEL_TIMES_DF = pd.read_csv("data/station_pairs_all_with_transfer.csv")
    print(f"Travel time data loaded: {len(TRAVEL_TIMES_DF)} routes")
except Exception as e:
    print(f"Warning: Could not load travel times data: {e}")

# 사용자 클릭 위치에서 가장 가까운 역 찾기
def find_nearest_station(user_lat, user_lng):
    user_loc = (user_lat, user_lng)
    nearest = min(
        STATIONS,
        key=lambda station: haversine(user_loc, (float(station["lat"]), float(station["lng"])))
    )
    distance = haversine(user_loc, (float(nearest["lat"]), float(nearest["lng"])))
    return {
        "name": nearest["name"],
        "lat": float(nearest["lat"]),
        "lng": float(nearest["lng"]),
        "distance": round(distance, 2)  # km 단위로 반올림
    }

# 📍 새로 추가: 가장 가까운 지하철역 찾기 API
@app.route("/api/nearest-station", methods=["POST"])
def nearest_station():
    data = request.get_json()
    user_lat = data.get("lat")
    user_lng = data.get("lng")
    
    if not user_lat or not user_lng:
        return jsonify({"error": "Missing coordinates"}), 400
    
    try:
        nearest = find_nearest_station(float(user_lat), float(user_lng))
        return jsonify(nearest)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 📍 주소를 좌표로 변환하는 API (카카오 API 사용)
# 📍 주소를 좌표로 변환하는 API (카카오 주소검색 우선, 키워드 검색 폴백)
@app.route("/api/geocode", methods=["POST"])
def geocode():
    data = request.get_json() or {}
    keyword = (data.get("address") or "").strip()
    if not keyword:
        return jsonify({"error": "Missing address"}), 400

    if not KAKAO_API_KEY:
        return jsonify({"error": "KAKAO_API_KEY not set"}), 500

    # 1) 카카오 '주소검색' (정확한 도로명/지번 주소용)
    try:
        url = "https://dapi.kakao.com/v2/local/search/address.json"
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        params = {"query": keyword}
        r = requests.get(url, headers=headers, params=params, timeout=8)
        j = r.json() if r.content else {}

        docs = j.get("documents", []) if isinstance(j, dict) else []
        if docs:
            first = docs[0]
            # 카카오는 x=lng, y=lat
            lng = first.get("x")
            lat = first.get("y")
            if lng and lat:
                return jsonify({
                    "lat": str(lat),
                    "lng": str(lng),
                    "address_name": first.get("address_name") or keyword
                })
    except Exception as e:
        print("[geocode] kakao address error:", e)

    # 2) 주소검색 결과가 없으면 '키워드검색' 폴백 (장소명/건물명 등)
    try:
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        params = {"query": keyword}
        r = requests.get(url, headers=headers, params=params, timeout=8)
        j = r.json() if r.content else {}

        docs = j.get("documents", []) if isinstance(j, dict) else []
        if docs:
            first = docs[0]
            lng = first.get("x")
            lat = first.get("y")
            if lng and lat:
                return jsonify({
                    "lat": str(lat),
                    "lng": str(lng),
                    "address_name": first.get("place_name") or keyword
                })
    except Exception as e:
        print("[geocode] kakao keyword error:", e)

    # 3) 모두 실패
    return jsonify({"error": "Address not found"}), 404

# 등고선 데이터 생성 함수
def generate_contour_data(start_station_name, time_intervals=[5, 10, 15, 20, 25]):
    """
    시작 역으로부터 각 시간 단위별로 도달 가능한 역들을 그룹화하여 등고선 데이터 생성
    """
    if TRAVEL_TIMES_DF is None:
        return {"error": "Travel time data not available"}
    
    # 역명 매칭을 위한 정규화 함수
    def normalize_station_name(name):
        # "역" 접미사 제거
        name = name.replace('역', '')
        # 노선 정보 제거 (예: " 1호선", " 경의선" 등)
        name = re.sub(r'\s*[0-9]호선', '', name)
        name = re.sub(r'\s*경의선', '', name)
        name = re.sub(r'\s*우이신설선', '', name)
        name = re.sub(r'\s*의정부경전철', '', name)
        name = re.sub(r'\s*에버라인', '', name)
        return name.strip()
    
    # CSV에서 역명 찾기 (정규화된 이름으로 매칭)
    normalized_start = normalize_station_name(start_station_name)
    
    # CSV의 src_station 컬럼에서 매칭되는 역 찾기
    matching_stations = []
    for _, row in TRAVEL_TIMES_DF.iterrows():
        csv_station = row['src_station']
        if normalize_station_name(csv_station) == normalized_start:
            matching_stations.append(csv_station)
    
    if not matching_stations:
        return {"error": f"No routes found from station: {start_station_name} (normalized: {normalized_start})"}
    
    # 첫 번째 매칭되는 역 사용
    csv_station_name = matching_stations[0]
    print(f"Station matched: '{start_station_name}' -> '{csv_station_name}'")
    
    start_routes = TRAVEL_TIMES_DF[TRAVEL_TIMES_DF['src_station'] == csv_station_name].copy()
    if start_routes.empty:
        return {"error": f"No routes found from CSV station: {csv_station_name}"}
    
    # 25분을 초과하는 역들은 완전히 제외
    start_routes = start_routes[start_routes['minutes'] <= 25].copy()
    print(f"Total routes within 25 minutes: {len(start_routes)}")
    
    # 시작 역의 좌표 찾기
    start_station_coord = None
    for s in STATIONS:
        if normalize_station_name(s['name']) == normalized_start:
            start_station_coord = s
            break
    
    if not start_station_coord:
        return {"error": f"Start station coordinates not found: {start_station_name}"}
    
    contour_data = {}
    for i, time_limit in enumerate(time_intervals):
        # 해당 시간 내에 도달 가능한 역들
        reachable_stations = start_routes[start_routes['minutes'] <= time_limit].copy()
        
        # 이전 시간대의 역들을 제외 (중복 제거)
        if i > 0:
            prev_time = time_intervals[i-1]
            prev_stations = start_routes[start_routes['minutes'] <= prev_time]
            # 이전 시간대에 포함된 역들을 현재에서 제외
            reachable_stations = reachable_stations[~reachable_stations.index.isin(prev_stations.index)]
        
        stations_with_coords = []
        
        for _, route in reachable_stations.iterrows():
            dst_station = route['dst_station']
            
            # 역 좌표 찾기 - 역명 매칭 개선
            station_coord = None
            
            # 1) 정확한 매칭 시도
            station_coord = next((s for s in STATIONS if s['name'] == dst_station), None)
            
            # 2) "역" 접미사 제거 후 매칭 시도
            if not station_coord:
                station_name_without_suffix = dst_station.replace('역', '')
                station_coord = next((s for s in STATIONS if station_name_without_suffix in s['name']), None)
            
            # 3) 정규화된 이름으로 매칭 시도
            if not station_coord:
                normalized_dst = normalize_station_name(dst_station)
                for s in STATIONS:
                    if normalize_station_name(s['name']) == normalized_dst:
                        station_coord = s
                        break
            
            if station_coord:
                stations_with_coords.append({
                    'name': dst_station,
                    'lat': float(station_coord['lat']),
                    'lng': float(station_coord['lng']),
                    'time': int(route['minutes'])
                })
        
        # 시작 역 좌표 추가 (중앙점)
        stations_with_coords.append({
            'name': start_station_name,
            'lat': float(start_station_coord['lat']),
            'lng': float(start_station_coord['lng']),
            'time': 0
        })
        
        # 경계선을 위한 역들을 정렬 (중앙에서부터 거리순)
        if len(stations_with_coords) > 1:
            center_lat = float(start_station_coord['lat'])
            center_lng = float(start_station_coord['lng'])
            
            # 거리 계산 함수
            def calculate_distance(lat1, lng1, lat2, lng2):
                return ((lat1 - lat2) ** 2 + (lng1 - lng2) ** 2) ** 0.5
            
            # 중앙에서부터 거리순으로 정렬
            stations_with_coords.sort(key=lambda x: calculate_distance(
                center_lat, center_lng, x['lat'], x['lng']
            ))
        
        print(f"{time_limit}분: {len(stations_with_coords)}개 역 포함 (중복 제거 후)")
        
        contour_data[f"{time_limit}분"] = {
            'time_limit': time_limit,
            'stations': stations_with_coords,
            'count': len(stations_with_coords),
            'center_lat': float(start_station_coord['lat']),
            'center_lng': float(start_station_coord['lng'])
        }
    
    return contour_data

# 등고선 데이터 API
@app.route("/api/contour-data", methods=["POST"])
def contour_data():
    data = request.get_json()
    start_station_name = data.get("station_name")
    
    if not start_station_name:
        return jsonify({"error": "Missing station name"}), 400
    
    try:
        contour_data = generate_contour_data(start_station_name)
        return jsonify(contour_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 역지오코딩 API 엔드포인트 추가
@app.route("/api/reverse-geocode", methods=["POST"])
def reverse_geocode():
    data = request.get_json()
    lat = data.get("lat")
    lng = data.get("lng")
    
    if not lat or not lng:
        return jsonify({"error": "Missing coordinates"}), 400
    
    try:
        # 카카오 지도 API를 사용한 역지오코딩
        url = f"https://dapi.kakao.com/v2/local/geo/coord2address.json"
        headers = {
            "Authorization": f"KakaoAK {KAKAO_API_KEY}"
        }
        params = {
            "x": lng,  # 경도
            "y": lat   # 위도
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            return jsonify({"error": "Failed to get address"}), 400
            
        result = response.json()
        
        if result.get("documents") and len(result["documents"]) > 0:
            address_info = result["documents"][0]
            
            # 도로명 주소가 있으면 우선 사용, 없으면 지번 주소 사용
            address = ""
            if address_info.get("road_address"):
                address = address_info["road_address"]["address_name"]
            elif address_info.get("address"):
                address = address_info["address"]["address_name"]
            
            if address:
                return jsonify({"address": address})
            else:
                return jsonify({"error": "Address not found"}), 404
        else:
            return jsonify({"error": "Address not found"}), 404
            
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
        return jsonify({"error": "Failed to process reverse geocoding"}), 500

if __name__ == "__main__":
    app.run(debug=True)
