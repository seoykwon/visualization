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
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")

print(f"🔑 KAKAO_API_KEY 로드됨: {KAKAO_API_KEY[:10] if KAKAO_API_KEY else 'None'}...")
print(f"🔑 ODSAY_KEY 로드됨: {ODSAY_KEY[:10] if ODSAY_KEY else 'None'}...")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "http://localhost:3000"}})

# Load station coordinates from JSON
with open("station_coords.json", encoding='utf-8') as f:
    STATIONS = json.load(f)

# 주소를 좌표로 변환 (Kakao API 사용) - 디버깅 강화
def geocode_address(address):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": address}
    
    print(f"🔍 주소 검색 시도: '{address}'")
    print(f"🌐 요청 URL: {url}")
    print(f"📋 파라미터: {params}")
    print(f"🔐 헤더: Authorization: KakaoAK {KAKAO_API_KEY[:10]}...")
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"📊 HTTP 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📝 응답 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data['documents']:
                result = data['documents'][0]
                coord_result = {
                    'lat': float(result['y']),
                    'lng': float(result['x']),
                    'address': result['address_name']
                }
                print(f"✅ 좌표 변환 성공: {coord_result}")
                return coord_result
            else:
                print("❌ 검색 결과가 없습니다 (documents 배열이 비어있음)")
        else:
            print(f"❌ HTTP 오류: {response.status_code}")
            print(f"❌ 오류 내용: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 네트워크 오류: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 오류: {str(e)}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {str(e)}")
    
    return None

# 🆕 좌표를 주소로 변환 (Kakao API 사용)
def reverse_geocode(lat, lng):
    url = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"x": lng, "y": lat}
    
    print(f"🔍 좌표→주소 변환 시도: ({lat}, {lng})")
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"📊 HTTP 상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"📝 응답 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if data['documents']:
                # 도로명 주소 우선, 없으면 지번 주소
                result = data['documents'][0]
                if result.get('road_address'):
                    address = result['road_address']['address_name']
                elif result.get('address'):
                    address = result['address']['address_name']
                else:
                    address = f"위도: {lat}, 경도: {lng}"
                
                print(f"✅ 주소 변환 성공: {address}")
                return address
            else:
                print("❌ 검색 결과가 없습니다")
        else:
            print(f"❌ HTTP 오류: {response.status_code}")
            print(f"❌ 오류 내용: {response.text}")
            
    except Exception as e:
        print(f"❌ 역 지오코딩 오류: {str(e)}")
    
    return f"위도: {lat}, 경도: {lng}"

# 사용자 클릭 위치에서 가장 가까운 역 찾기
def find_nearest_station(user_lat, user_lng):
    user_loc = (user_lat, user_lng)
    nearest = min(
        STATIONS,
        key=lambda station: haversine(user_loc, (float(station["lat"]), float(station["lng"])))
    )
    return nearest

# 🚇 가장 가까운 역에서 모든 지하철역까지의 소요시간 계산 (단순화된 버전)
def get_subway_accessibility_from_nearest(nearest_station):
    """가장 가까운 역에서 모든 역까지의 대중교통 소요시간 계산"""
    print(f"🚇 {nearest_station['name']}에서 모든 역까지의 접근성 계산 시작...")
    
    results = []
    start_lat = float(nearest_station["lat"])
    start_lng = float(nearest_station["lng"])
    
    for target_station in STATIONS:
        # 같은 역은 건너뛰기
        if target_station["name"] == nearest_station["name"]:
            continue
            
        try:
            target_lat = float(target_station["lat"])
            target_lng = float(target_station["lng"])
            
            url = f"https://api.odsay.com/v1/api/searchPubTransPathT?"
            params = {
                "SX": start_lng,
                "SY": start_lat,
                "EX": target_lng,
                "EY": target_lat,
                "OPT": 0,  # 0: 최적 경로
                "apiKey": ODSAY_KEY
            }
            
            res = requests.get(url, params=params)
            if res.status_code != 200:
                print(f"❌ {target_station['name']} API 호출 실패: {res.status_code}")
                continue
                
            res_data = res.json()
            
            # 가장 빠른 경로의 시간을 가져오기 (교통수단 상관없이)
            if res_data.get('result', {}).get('path'):
                # 첫 번째 경로가 보통 최적 경로
                best_path = res_data['result']['path'][0]
                total_time = best_path['info']['totalTime']
                
                results.append({
                    "station": target_station['name'],
                    "lat": target_lat,
                    "lng": target_lng,
                    "time": total_time
                })
                print(f"✅ {target_station['name']}: {total_time}분")
            else:
                print(f"⚠️ {target_station['name']}: 경로 없음")
                
        except Exception as e:
            print(f"❌ {target_station['name']} 처리 중 오류: {str(e)}")
            continue
    
    print(f"🎯 총 {len(results)}개 역의 접근성 계산 완료")
    return results

# 📍 새로운 API: 주소를 좌표로 변환
@app.route("/api/geocode", methods=["POST"])
def geocode():
    print("\n" + "="*50)
    print("🚀 /api/geocode 요청 받음")
    
    data = request.get_json()
    print(f"📥 받은 데이터: {data}")
    
    address = data.get("address")
    print(f"🏠 검색할 주소: '{address}'")
    
    if not address:
        print("❌ 주소가 비어있음")
        return jsonify({"error": "주소가 필요합니다"}), 400
    
    result = geocode_address(address)
    
    if result:
        response_data = {
            "lat": str(result['lat']),
            "lng": str(result['lng']),
            "address": result['address']
        }
        print(f"✅ 성공 응답: {response_data}")
        return jsonify(response_data)
    else:
        print("❌ 주소 검색 실패")
        return jsonify({"error": "주소를 찾을 수 없습니다"}), 404

# 🆕 API: 좌표를 주소로 변환 (역 지오코딩)
@app.route("/api/reverse-geocode", methods=["POST"])
def api_reverse_geocode():
    print("\n" + "="*50)
    print("🔄 /api/reverse-geocode 요청 받음")
    
    data = request.get_json()
    print(f"📥 받은 데이터: {data}")
    
    lat = data.get("lat")
    lng = data.get("lng")
    
    if not lat or not lng:
        print("❌ 좌표가 비어있음")
        return jsonify({"error": "위도와 경도가 필요합니다"}), 400
    
    try:
        lat = float(lat)
        lng = float(lng)
        print(f"📍 변환할 좌표: ({lat}, {lng})")
        
        address = reverse_geocode(lat, lng)
        
        response_data = {"address": address}
        print(f"✅ 성공 응답: {response_data}")
        return jsonify(response_data)
        
    except ValueError as e:
        print(f"❌ 좌표 형식 오류: {str(e)}")
        return jsonify({"error": "올바른 좌표 형식이 아닙니다"}), 400
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {str(e)}")
        return jsonify({"error": "서버 오류가 발생했습니다"}), 500

# 🚇 새로운 API: 가장 가까운 지하철역 하나만 반환
@app.route("/api/nearest-station", methods=["POST"])
def nearest_station():
    print("\n" + "="*50)
    print("🚇 /api/nearest-station 요청 받음")
    
    data = request.get_json()
    print(f"📥 받은 데이터: {data}")
    
    user_lat = data.get("lat")
    user_lng = data.get("lng")
    
    if not user_lat or not user_lng:
        print("❌ 좌표가 비어있음")
        return jsonify({"error": "위도와 경도가 필요합니다"}), 400
    
    try:
        user_lat = float(user_lat)
        user_lng = float(user_lng)
        print(f"📍 사용자 위치: ({user_lat}, {user_lng})")
        
        # 가장 가까운 역 찾기
        nearest = find_nearest_station(user_lat, user_lng)
        
        # 직선 거리 계산
        distance = haversine(
            (user_lat, user_lng), 
            (float(nearest["lat"]), float(nearest["lng"]))
        )
        
        # ODsay API로 실제 교통 정보 가져오기 (선택사항)
        travel_time = None
        try:
            url = f"https://api.odsay.com/v1/api/searchPubTransPathT?"
            params = {
                "SX": user_lng,
                "SY": user_lat,
                "EX": nearest["lng"],
                "EY": nearest["lat"],
                "OPT": 0,
                "apiKey": ODSAY_KEY
            }
            res = requests.get(url, params=params)
            if res.status_code == 200:
                travel_time = res.json()["result"]["path"][0]["info"]["totalTime"]
        except:
            pass  # 교통 정보를 가져올 수 없어도 계속 진행
        
        result = {
            "name": nearest["name"],
            "lat": nearest["lat"],
            "lng": nearest["lng"],
            "distance_km": round(distance, 2),  # 직선 거리 (km)
            "travel_time": travel_time  # 실제 교통 소요시간 (분), None일 수 있음
        }
        
        print(f"✅ 가장 가까운 역: {result}")
        return jsonify(result)
        
    except ValueError as e:
        print(f"❌ 좌표 형식 오류: {str(e)}")
        return jsonify({"error": "올바른 좌표 형식이 아닙니다"}), 400
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {str(e)}")
        return jsonify({"error": "서버 오류가 발생했습니다"}), 500

# 🎯 개선된 API: 가장 가까운 역 기준 지하철 접근성 계산
@app.route('/api/accessible', methods=['POST'])
def accessible():
    print("\n" + "="*50)
    print("🎯 /api/accessible 요청 받음")
    
    data = request.json
    user_lat = float(data['lat'])
    user_lng = float(data['lng'])
    
    print(f"📍 사용자 위치: ({user_lat}, {user_lng})")
    
    # 1. 가장 가까운 역 찾기
    nearest_station = find_nearest_station(user_lat, user_lng)
    print(f"🚇 가장 가까운 역: {nearest_station['name']}")
    
    # 2. 가장 가까운 역에서 모든 역까지의 지하철 소요시간 계산
    reachable_stations = get_subway_accessibility_from_nearest(nearest_station)
    
    print(f"✅ 총 {len(reachable_stations)}개 역 결과 반환")
    return jsonify(reachable_stations)

if __name__ == "__main__":
    app.run(debug=True)