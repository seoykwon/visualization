import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  MapContainer,
  TileLayer,
  useMapEvents,
  Marker,
  Popup,
  useMap
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { LeafletMouseEvent } from 'leaflet';
import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

function getColorByTime(time: number): string {
  if (time <= 30) return 'green';    // 30분 이하: 초록색 (접근성 좋음)
  if (time <= 60) return 'orange';   // 60분 이하: 주황색 (접근성 보통)
  return 'red';                      // 90분 이상: 빨간색 (접근성 나쁨)
}

function getCustomIcon(color: string) {
  return new L.Icon({
    iconUrl: `/marker-icon-${color}.png`,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
    shadowSize: [41, 41],
  });
}

// 🚇 가장 가까운 지하철역용 특별한 아이콘
function getNearestStationIcon() {
  return new L.Icon({
    iconUrl: `/marker-icon-blue.png`, // 파란색 마커 (없으면 기본 마커 사용)
    iconSize: [30, 48], // 조금 더 크게
    iconAnchor: [15, 48],
    popupAnchor: [1, -40],
    shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
    shadowSize: [50, 50],
  });
}

function MapCenterUpdater({ coords }: { coords: Coords }) {
  const map = useMap();

  useEffect(() => {
    map.setView([parseFloat(coords.lat), parseFloat(coords.lng)], map.getZoom());
  }, [coords, map]);

  return null;
}

// Leaflet 기본 마커 이미지 수동 설정
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

interface ReachableStation {
  station: string;
  lat: number;
  lng: number;
  time: number;
}

// 🚇 가장 가까운 지하철역 인터페이스
interface NearestStation {
  name: string;
  lat: string;
  lng: string;
  distance_km: number;
  travel_time: number | null;
}

interface Coords {
  lat: string;
  lng: string;
}

function ClickableMap({ onSelect }: { onSelect: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e: LeafletMouseEvent) {
      onSelect(e.latlng.lat, e.latlng.lng);
    }
  });
  return null;
}

// 네이버 부동산 열기 함수
function openNaverLand(lat: number, lng: number) {
  // 네이버 부동산 지도 URL (해당 위치로 이동)
  const naverLandUrl = `https://land.naver.com/article/articleList.naver?rletTypeCd=A01%3AA03%3AB01%3AB02%3AB03%3AB04&tradTypeCd=A1%3AB1%3AB2%3AB3&hscpTypeCd=A01%3AA02%3AA03%3AA04&cortarNo=1168000000&mapX=${lng}&mapY=${lat}&mapLevel=12`;
  window.open(naverLandUrl, '_blank');
}

function App() {
  const [address, setAddress] = useState('');
  const [coords, setCoords] = useState<Coords | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reachableStations, setReachableStations] = useState<ReachableStation[]>([]);
  const [nearestStation, setNearestStation] = useState<NearestStation | null>(null); // 🚇 가장 가까운 역
  const [loading, setLoading] = useState(false);

  // 🔍 역 지오코딩 함수 (좌표 → 주소 변환)
  const reverseGeocode = async (lat: string, lng: string) => {
    try {
      const res = await axios.post<{ address: string }>('http://localhost:5000/api/reverse-geocode', {
        lat,
        lng
      });
      setAddress(res.data.address);
      console.log('역 지오코딩 결과:', res.data.address);
    } catch (error) {
      console.error('역 지오코딩 실패:', error);
      // 실패시 좌표를 주소란에 표시
      setAddress(`위도: ${parseFloat(lat).toFixed(6)}, 경도: ${parseFloat(lng).toFixed(6)}`);
    }
  };

  // 🚇 가장 가까운 지하철역 찾기 함수
  const findNearestStation = async (lat: string, lng: string) => {
    try {
      setLoading(true);
      const res = await axios.post<NearestStation>('http://localhost:5000/api/nearest-station', {
        lat,
        lng
      });
      setNearestStation(res.data);
      console.log('가장 가까운 역:', res.data);
    } catch (error) {
      console.error('가장 가까운 역 검색 실패:', error);
      setNearestStation(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    try {
      setLoading(true);
      const res = await axios.post<Coords>('http://localhost:5000/api/geocode', {
        address,
      });
      setCoords(res.data);
      setErrorMessage(null);
      
      await findNearestStation(res.data.lat, res.data.lng);
    } catch (error) {
      console.error('검색 실패:', error);
      setCoords(null);
      setNearestStation(null);
      setErrorMessage('주소 또는 장소를 찾을 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* 헤더 */}
      <div style={{ 
        padding: '15px', 
        backgroundColor: '#f5f5f5', 
        borderBottom: '1px solid #ddd',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px'
      }}>
        {/* 제목 */}
        <div style={{ 
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <h1 style={{ margin: 0 }}>서울 접근성 지도</h1>
        </div>

        {/* 주소 검색 */}
        <div style={{ 
          display: 'flex', 
          gap: '10px', 
          alignItems: 'center',
          flexWrap: 'wrap'
        }}>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="📍 주소 입력 또는 지도에서 클릭하여 위치 선택 (예: 강남구 테헤란로, 강남역)"
            style={{ 
              flex: 1,
              minWidth: '300px',
              padding: '8px 12px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          />
          <button 
            onClick={handleSearch}
            disabled={!address.trim() || loading}
            style={{
              padding: '8px 16px',
              backgroundColor: !address.trim() || loading ? '#ccc' : '#2196F3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: !address.trim() || loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              whiteSpace: 'nowrap'
            }}
          >
            {loading ? '검색중...' : '위치 검색'}
          </button>
          
          {/* 네이버 부동산 버튼 - 지도 상단으로 이동 */}
          <button 
            onClick={() => {
              if (nearestStation) {
                openNaverLand(parseFloat(nearestStation.lat), parseFloat(nearestStation.lng));
              } else if (coords) {
                openNaverLand(parseFloat(coords.lat), parseFloat(coords.lng));
              }
            }}
            disabled={!coords && !nearestStation}
            style={{
              padding: '8px 16px',
              backgroundColor: (!coords && !nearestStation) ? '#ccc' : '#00C73C',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: (!coords && !nearestStation) ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              whiteSpace: 'nowrap',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
            title={(!coords && !nearestStation) ? "주소를 먼저 검색해 주세요" : "네이버 부동산에서 해당 위치 매물 보기"}
          >
            🏠 네이버 부동산
          </button>
        </div>

        {/* 현재 위치 표시 */}
        {coords && (
          <div style={{ 
            fontSize: '12px', 
            color: '#666',
            backgroundColor: '#e8f5e8',
            padding: '8px',
            borderRadius: '4px'
          }}>
            📍 현재 위치: 위도 {parseFloat(coords.lat).toFixed(6)}, 경도 {parseFloat(coords.lng).toFixed(6)}
          </div>
        )}

        {/* 가장 가까운 역 정보 + 범례 */}
        {nearestStation && (
          <div style={{
            fontSize: '12px',
            color: '#333',
            backgroundColor: '#e3f2fd',
            padding: '8px',
            borderRadius: '4px',
            border: '1px solid #2196F3'
          }}>
            <div style={{ marginBottom: '8px' }}>
              🚇 가장 가까운 역: <strong>{nearestStation.name}</strong> 
              (직선거리: {nearestStation.distance_km}km
              {nearestStation.travel_time && `, 소요시간: ${nearestStation.travel_time}분`})
            </div>
            
            {/* 색상 범례 */}
            <div style={{ 
              display: 'flex', 
              gap: '12px', 
              alignItems: 'center',
              fontSize: '11px',
              paddingTop: '4px',
              borderTop: '1px solid #ddd'
            }}>
              <span style={{ fontWeight: 'bold' }}>지하철 소요시간:</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{ 
                  width: '12px', 
                  height: '12px', 
                  backgroundColor: 'green', 
                  borderRadius: '50%' 
                }}></div>
                <span>30분 이하</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{ 
                  width: '12px', 
                  height: '12px', 
                  backgroundColor: 'orange', 
                  borderRadius: '50%' 
                }}></div>
                <span>60분 이하</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <div style={{ 
                  width: '12px', 
                  height: '12px', 
                  backgroundColor: 'red', 
                  borderRadius: '50%' 
                }}></div>
                <span>90분 이상</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 지도 영역 - 전체 화면 사용 */}
      <div style={{ 
        flex: 1,
        display: 'flex',
        flexDirection: 'column'
      }}>
        <MapContainer
          center={coords ? [parseFloat(coords.lat), parseFloat(coords.lng)] : [37.5665, 126.9780]}
          zoom={11}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
          />

          {coords && (
            <>
              <Marker position={[parseFloat(coords.lat), parseFloat(coords.lng)]}>
                <Popup>
                  📍 선택한 위치<br />
                  위도: {coords.lat}, <br />경도: {coords.lng}
                </Popup>
              </Marker>
              <MapCenterUpdater coords={coords} />
            </>
          )}

          {nearestStation && (
            <Marker 
              position={[parseFloat(nearestStation.lat), parseFloat(nearestStation.lng)]}
            >
              <Popup>
                🚇 <strong>{nearestStation.name}</strong><br />
                직선거리: {nearestStation.distance_km}km<br />
                {nearestStation.travel_time ? `소요시간: ${nearestStation.travel_time}분` : '소요시간: 계산 불가'}
              </Popup>
            </Marker>
          )}

          <ClickableMap
            onSelect={async (lat, lng) => {
              const newCoords = { lat: lat.toString(), lng: lng.toString() };
              setCoords(newCoords);

              // 🔍 마커로 위치 선택시 주소 자동 입력
              await reverseGeocode(newCoords.lat, newCoords.lng);

              await findNearestStation(newCoords.lat, newCoords.lng);

              axios
                .post<ReachableStation[]>('http://localhost:5000/api/accessible', newCoords)
                .then((res) => {
                  console.log('접근 가능 영역 결과:', res.data);
                  setReachableStations(res.data);
                })
                .catch(err => {
                  console.error('접근 가능 영역 계산 실패:', err);
                });
            }}
          />

          {reachableStations.map((s, idx) => (
            <Marker
              key={idx}
              position={[s.lat, s.lng]}
              icon={getCustomIcon(getColorByTime(s.time))}
            >
              <Popup>
                {s.station} <br />
                도달 시간: {s.time}분
              </Popup>
            </Marker>
          ))}
        </MapContainer>

        {errorMessage && (
          <p style={{ color: 'red', padding: '10px', margin: 0, backgroundColor: '#fff3f3' }}>
            {errorMessage}
          </p>
        )}
      </div>
    </div>
  );
}

export default App;