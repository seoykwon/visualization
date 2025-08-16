# app.py
import os
import json
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.colors import LinearSegmentedColormap
from flask import Flask, request, jsonify, send_file
from dotenv import load_dotenv
from haversine import haversine
from flask_cors import CORS
import io
import base64

# Load API keys
load_dotenv()
ODSAY_KEY = os.getenv("ODSAY_API_KEY")
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")

app = Flask(__name__)
# CORS(app)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# Load station coordinates from JSON
current_dir = os.path.dirname(os.path.abspath(__file__))
station_coords_path = os.path.join(current_dir, "station_coords.json")
with open(station_coords_path, encoding='utf-8') as f:
    STATIONS = json.load(f)
print(f"역 좌표 로드 완료: {len(STATIONS)}개 역")

# 사용자 클릭 위치에서 가장 가까운 역 찾기
def find_nearest_station(user_lat, user_lng):
    try:
        print(f"가장 가까운 역 찾기 시작: ({user_lat}, {user_lng})")
        print(f"STATIONS 개수: {len(STATIONS)}")
        
        user_loc = (user_lat, user_lng)
        nearest = min(
            STATIONS,
            key=lambda station: haversine(user_loc, (float(station["lat"]), float(station["lng"])))
        )
        distance = haversine(user_loc, (float(nearest["lat"]), float(nearest["lng"])))
        
        result = {
            "name": nearest["name"],
            "lat": float(nearest["lat"]),
            "lng": float(nearest["lng"]),
            "distance": round(distance, 2)  # km 단위로 반올림
        }
        
        print(f"가장 가까운 역: {result['name']} (거리: {result['distance']}km)")
        return result
        
    except Exception as e:
        print(f"가장 가까운 역 찾기 오류: {str(e)}")
        raise e

# 📍 새로 추가: 가장 가까운 지하철역 찾기 API
@app.route("/api/nearest-station", methods=["POST"])
def nearest_station():
    try:
        print("=== 가장 가까운 역 찾기 API 호출 ===")
        data = request.get_json()
        print(f"받은 데이터: {data}")
        
        user_lat = data.get("lat")
        user_lng = data.get("lng")
        
        print(f"좌표: lat={user_lat}, lng={user_lng}")
        
        if not user_lat or not user_lng:
            print("좌표 누락")
            return jsonify({"error": "Missing coordinates"}), 400
        
        nearest = find_nearest_station(float(user_lat), float(user_lng))
        print(f"결과: {nearest}")
        return jsonify(nearest)
        
    except Exception as e:
        print(f"API 오류: {str(e)}")
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


def generate_contour_plot(center_lat, center_lng, radius_km=50):
    """
    중심점을 기준으로 등고선을 생성하여 소요시간을 시각화
    scipy.interpolate.griddata를 사용하여 정확한 등고선 생성
    """
    try:
        print(f"등고선 생성 시작: 중심점 ({center_lat}, {center_lng})")
        
        # matplotlib 백엔드를 Agg로 설정 (서버 환경에서 GUI 없이 실행)
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from scipy.interpolate import griddata
        
        # 1. 출발 좌표에서 각 역까지 시간 계산
        results = get_subway_times_from(center_lat, center_lng)
        
        if not results or len(results) < 3:
            return None, "충분한 역 데이터가 없습니다. (최소 3개 역 필요)"
        
        print(f"역 데이터 로드 완료: {len(results)}개 역")
        
        # 좌표와 시간 데이터 추출
        xs = [float(r["lng"]) for r in results]
        ys = [float(r["lat"]) for r in results]
        ts = [float(r["time"]) for r in results]
        
        print(f"좌표 범위: 경도 {min(xs):.4f}~{max(xs):.4f}, 위도 {min(ys):.4f}~{max(ys):.4f}")
        print(f"시간 범위: {min(ts):.1f}~{max(ts):.1f}분")
        
        # 2. 보간을 위한 격자 생성 (더 세밀하게)
        grid_x, grid_y = np.mgrid[min(xs):max(xs):200j, min(ys):max(ys):200j]
        
        # 3. griddata를 사용한 보간
        grid_z = griddata((xs, ys), ts, (grid_x, grid_y), method="cubic", fill_value=999)
        
        print("보간 완료")
        
        # 4. 등고선 그리기
        plt.figure(figsize=(12, 10))
        
        # 한글 폰트 설정
        plt.rcParams['font.family'] = 'DejaVu Sans'
        
        # 등고선 레벨 설정 (20분 간격, 20-100분)
        levels = np.arange(20, 101, 20)
        
        # 파스텔 핑크-퍼플 컬러맵 생성
        colors = ['#FFE6F2', '#F0E6FF', '#E6F0FF', '#E6FFF0', '#FFF0E6']
        cmap = LinearSegmentedColormap.from_list('pastel_pink_purple', colors, N=len(levels))
        
        # 등고선 그리기
        contour = plt.contourf(grid_x, grid_y, grid_z, levels=levels, cmap=cmap, alpha=0.8)
        plt.contour(grid_x, grid_y, grid_z, levels=levels, colors='black', linewidths=0.5, alpha=0.7)
        
        # 역 위치 표시
        plt.scatter(xs, ys, c='red', s=30, alpha=0.8, label='지하철역')
        
        # 중심점 표시
        plt.scatter(center_lng, center_lat, c='blue', s=100, marker='*', label='선택한 위치')
        
        # 컬러바 추가
        cbar = plt.colorbar(contour)
        cbar.set_label('소요시간 (분)', fontsize=12)
        cbar.set_ticks(levels)
        
        # 축 레이블과 제목
        plt.xlabel('경도', fontsize=12)
        plt.ylabel('위도', fontsize=12)
        plt.title(f'지하철 소요시간 등고선 (20분 간격, 파스텔 핑크-퍼플)', fontsize=14)
        
        # 범례 추가
        plt.legend()
        
        # 격자 추가
        plt.grid(True, alpha=0.3)
        
        print("등고선 그리기 완료, 이미지 저장 중...")
        
        # 이미지를 바이트로 변환
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()
        
        # base64로 인코딩
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        print("등고선 생성 완료!")
        return img_base64, None
        
    except Exception as e:
        print(f"등고선 생성 오류: {str(e)}")
        return None, str(e)

# 등고선 생성 API 엔드포인트
@app.route("/api/contour-plot", methods=["POST"])
def contour_plot():
    data = request.get_json()
    center_lat = data.get("lat")
    center_lng = data.get("lng")
    radius_km = data.get("radius_km", 50)
    
    if not center_lat or not center_lng:
        return jsonify({"error": "Missing coordinates"}), 400
    
    try:
        img_base64, error = generate_contour_plot(float(center_lat), float(center_lng), radius_km)
        
        if error:
            return jsonify({"error": error}), 500
        
        return jsonify({
            "image": img_base64,
            "message": "등고선 이미지가 생성되었습니다."
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
