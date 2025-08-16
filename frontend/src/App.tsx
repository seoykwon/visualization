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
import 'leaflet/dist/leaflet.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

// Leaflet 기본 마커 이미지 수정
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

function getColorByTime(time: number): string {
  if (time <= 15) return 'green';
  if (time <= 30) return 'orange';
  return 'red';
}

function getCustomIcon(color) {
  return new L.Icon({
    iconUrl: `data:image/svg+xml;base64,${btoa(`
      <svg width="25" height="41" viewBox="0 0 25 41" xmlns="http://www.w3.org/2000/svg">
        <path d="M12.5 0C5.6 0 0 5.6 0 12.5c0 12.5 12.5 28.5 12.5 28.5s12.5-16 12.5-28.5C25 5.6 19.4 0 12.5 0z" fill="${color}"/>
        <circle cx="12.5" cy="12.5" r="6" fill="white"/>
      </svg>
    `)}`,
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
  });
}

function getNearestStationIcon() {
  return new L.Icon({
    iconUrl: `data:image/svg+xml;base64,${btoa(`
      <svg width="30" height="46" viewBox="0 0 30 46" xmlns="http://www.w3.org/2000/svg">
        <path d="M15 0C6.7 0 0 6.7 0 15c0 15 15 31 15 31s15-16 15-31C30 6.7 23.3 0 15 0z" fill="#0066FF"/>
        <circle cx="15" cy="15" r="8" fill="white"/>
        <text x="15" y="20" text-anchor="middle" fill="#0066FF" font-size="12" font-weight="bold">N</text>
      </svg>
    `)}`,
    iconSize: [30, 46],
    iconAnchor: [15, 46],
    popupAnchor: [1, -38],
  });
}

function getSelectedLocationIcon() {
  return new L.Icon({
    iconUrl: `data:image/svg+xml;base64,${btoa(`
      <svg width="30" height="46" viewBox="0 0 30 46" xmlns="http://www.w3.org/2000/svg">
        <path d="M15 0C6.7 0 0 6.7 0 15c0 15 15 31 15 31s15-16 15-31C30 6.7 23.3 0 15 0z" fill="#FF6B35"/>
        <circle cx="15" cy="15" r="8" fill="white"/>
        <text x="15" y="20" text-anchor="middle" fill="#FF6B35" font-size="12" font-weight="bold">P</text>
      </svg>
    `)}`,
    iconSize: [30, 46],
    iconAnchor: [15, 46],
    popupAnchor: [1, -38],
  });
}

function MapCenterUpdater({ coords }) {
  const map = useMap();

  useEffect(() => {
    if (coords) {
      map.setView([parseFloat(coords.lat), parseFloat(coords.lng)], map.getZoom());
    }
  }, [coords, map]);

  return null;
}

function ClickableMap({ onSelect }) {
  useMapEvents({
    click(e) {
      onSelect(e.latlng.lat, e.latlng.lng);
    }
  });
  return null;
}

// 네이버 부동산 rooms 새탭 열기 (확대된 축척으로)
function openNaverRoomsAt(lat: number, lng: number): void {
  const zoom = 15; // 더 큰 축척으로 설정 (기본 13에서 15로 변경)
  const url = `https://new.land.naver.com/rooms?ms=${lat},${lng},${zoom}&a=APT:OPST:ABYG:OBYG:GM:OR:DDDGG:JWJT:SGJT:HOJT:VL&e=RETAIL&aa=SMALLSPCRENT`;
  window.open(url, "_blank", "noopener,noreferrer");
}

interface ReachableStation {
  station: string;
  lat: number;
  lng: number;
  time: number;
}

interface Coords {
  lat: string;
  lng: string;
}

function App() {
  const [address, setAddress] = useState('');
  const [coords, setCoords] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [reachableStations, setReachableStations] = useState([]);
  const [nearestStation, setNearestStation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [contourImage, setContourImage] = useState('');
  const [contourLoading, setContourLoading] = useState(false);
  
  // 백엔드를 통한 카카오 역지오코딩
 // 백엔드를 통한 카카오 역지오코딩
const reverseGeocode = async (lat: string, lng: string): Promise<string> => {
  try {
    console.log('역지오코딩 요청:', { lat, lng });

    const response = await axios.post('http://localhost:5000/api/reverse-geocode', {
      lat: parseFloat(lat),
      lng: parseFloat(lng),
    });

    console.log('카카오 역지오코딩 응답:', response.data);

    const addr = response?.data?.address;
    if (addr && typeof addr === 'string' && addr.trim() && !addr.includes('위도') && !addr.includes('경도')) {
      setAddress(addr);
      setErrorMessage(null);
      return addr;
    }

    // 주소가 비어있거나 좌표 문자열일 때
    throw new Error('유효한 주소를 찾을 수 없습니다');
  } catch (error) {
    console.error('역지오코딩 오류:', error);
    const fallbackAddress = `위도: ${parseFloat(lat).toFixed(6)}, 경도: ${parseFloat(lng).toFixed(6)}`;
    setAddress(fallbackAddress);
    return fallbackAddress;
  }
};


   // 가장 가까운 지하철역 찾기
  const findNearestStation = async (lat, lng) => {
    try {
      console.log('가장 가까운 역 찾기 요청:', { lat, lng });
      const response = await axios.post('http://localhost:5000/api/nearest-station', {
        lat,
        lng
      });
      
      console.log('가장 가까운 역 응답:', response.data);
      setNearestStation(response.data);
    } catch (error) {
      console.error('가장 가까운 역 찾기 실패:', error);
      setNearestStation(null);
      // 사용자에게 오류 메시지 표시
      setErrorMessage('가장 가까운 역을 찾을 수 없습니다. 백엔드 서버를 확인해주세요.');
    }
  };

  // 주소 검색 핸들러
 const handleSearch = async () => {
    if (!address.trim()) return;
    
    setLoading(true);
    setErrorMessage(null);
    
    try {
      console.log('주소 검색 요청:', address);
      const response = await axios.post('http://localhost:5000/api/geocode', {
        address
      });

      console.log('주소 검색 응답:', response.data);
      const newCoords = { lat: response.data.lat, lng: response.data.lng };
      setCoords(newCoords);
      setErrorMessage(null);
      
      // 가장 가까운 지하철역 찾기
      await findNearestStation(parseFloat(response.data.lat), parseFloat(response.data.lng));
      
    } catch (error) {
      console.error('검색 실패:', error);
      setCoords(null);
      setNearestStation(null);
      if (error.response?.status === 500) {
        setErrorMessage('백엔드 서버 오류가 발생했습니다. 서버를 확인해주세요.');
      } else {
        setErrorMessage('주소 또는 장소를 찾을 수 없습니다.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // 등고선 생성 함수
  const generateContour = async () => {
    if (!coords) {
      alert('먼저 지도에서 위치를 선택해주세요.');
      return;
    }
    
    setContourLoading(true);
    try {
      const response = await axios.post('http://localhost:5000/api/contour-plot', {
        lat: parseFloat(coords.lat),
        lng: parseFloat(coords.lng),
        radius_km: 50
      });
      
      if (response.data.image) {
        setContourImage(`data:image/png;base64,${response.data.image}`);
      }
    } catch (error) {
      console.error('등고선 생성 실패:', error);
      alert('등고선 생성에 실패했습니다.');
    } finally {
      setContourLoading(false);
    }
  };

  // 지도 클릭 핸들러 개선 (역지오코딩 우선 시도)
  const handleMapClick = async (lat, lng) => {
    const newCoords = { lat: lat.toString(), lng: lng.toString() };
    setCoords(newCoords);
    
    // 먼저 역지오코딩 시도 (주소 가져오기)
    try {
      const obtainedAddress = await reverseGeocode(lat.toString(), lng.toString());
      console.log('획득한 주소:', obtainedAddress);
    } catch (error) {
      console.error('역지오코딩 실패:', error);
    }
    
    // 가장 가까운 지하철역 찾기
    await findNearestStation(lat, lng);

    // 접근 가능한 모든 역 계산
    try {
      const response = await axios.post('http://localhost:5000/api/accessible', {
        lat,
        lng
      });
      
      setReachableStations(response.data);
    } catch (error) {
      console.error('접근 가능 영역 계산 실패:', error);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* 헤더 */}
      <div
        style={{
          padding: '15px',
          backgroundColor: '#f5f5f5',
          borderBottom: '1px solid #ddd',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <h1 style={{ margin: 0 }}>서울 지하철 역간 접근성 지도</h1>
        </div>

        {/* 검색/버튼 줄 */}
        <div
          style={{
            display: 'flex',
            gap: '10px',
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="📍 주소 입력 또는 지도 클릭"
            style={{
              width: '300px',
              padding: '8px',
              fontSize: '14px',
            }}
          />
          <button
            onClick={handleSearch}
            disabled={loading}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              backgroundColor: loading ? '#ccc' : '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? '검색 중...' : '위치 검색'}
          </button>

          {/* 네이버 부동산 버튼 개선 */}
          <button
            onClick={() => {
              if (!coords) return;
              const lat = parseFloat(coords.lat);
              const lng = parseFloat(coords.lng);
              openNaverRoomsAt(lat, lng); // 개선된 함수 사용
            }}
            disabled={!coords}
            style={{
              padding: '8px 16px',
              fontSize: '14px',
              backgroundColor: coords ? '#00C73C' : '#ccc',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: coords ? 'pointer' : 'not-allowed',
            }}
          >
            🏠 매물 보기
          </button>
        </div>

        {/* 선택된 위치 표시 (주소 우선, 없으면 좌표) */}
        {coords && (
          <div 
            style={{ 
              padding: '10px',
              backgroundColor: '#fff3cd',
              borderRadius: '5px',
              fontSize: '14px',
              border: '1px solid #ffeaa7'
            }}
          >
            <strong>P 선택된 위치:</strong> {
              address && !address.includes('위도') && !address.includes('경도') 
                ? address 
                : `위도: ${parseFloat(coords.lat).toFixed(4)}, 경도: ${parseFloat(coords.lng).toFixed(4)}`
            }
            {address && address.includes('위도') && (
              <div style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
                💡 정확한 주소를 가져오는 중입니다...
              </div>
            )}
          </div>
        )}

        {/* 가장 가까운 역 정보 */}
        {nearestStation && (
          <div
            style={{
              padding: '10px',
              backgroundColor: '#e8f4f8',
              borderRadius: '5px',
              fontSize: '14px',
            }}
          >
            <strong>🚇 가장 가까운 지하철역:</strong> {nearestStation.name}
            <span style={{ color: '#666' }}>
              {' '}
              (거리:{' '}
              {(
                (nearestStation as any).distance_km ??
                (nearestStation as any).distance
              ) ?? '—'}
              km)
            </span>
          </div>
        )}

        {errorMessage && (
          <div style={{ padding: '8px', color: '#d32f2f', backgroundColor: '#ffebee', borderRadius: '4px' }}>
            {errorMessage}
          </div>
        )}
      </div>

      {/* 지도 영역 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <MapContainer
          center={
            coords
              ? [parseFloat(coords.lat), parseFloat(coords.lng)]
              : [37.5665, 126.978]
          }
          zoom={13}
          style={{
            flex: 1,
            width: '100%',
            border: '1px solid #ddd',
            borderRadius: '8px',
          }}
        >
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {coords && <MapCenterUpdater coords={coords} />}

          {/* 클릭한 위치 마커 (개선된 아이콘) */}
          {coords && (
            <Marker 
              position={[parseFloat(coords.lat), parseFloat(coords.lng)]}
              icon={getSelectedLocationIcon()}
            >
              <Popup>
                <strong>P 선택한 위치</strong>
                <br />
                {address && !address.includes('위도') && !address.includes('경도') 
                  ? address 
                  : `위도: ${parseFloat(coords.lat).toFixed(4)}, 경도: ${parseFloat(coords.lng).toFixed(4)}`}
                <br />
                <button
                  onClick={() => {
                    const lat = parseFloat(coords.lat);
                    const lng = parseFloat(coords.lng);
                    openNaverRoomsAt(lat, lng);
                  }}
                  style={{
                    marginTop: '5px',
                    padding: '5px 10px',
                    backgroundColor: '#00C73C',
                    color: 'white',
                    border: 'none',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontSize: '12px'
                  }}
                >
                  🏠 매물 보기
                </button>
              </Popup>
            </Marker>
          )}

          {/* 가장 가까운 지하철역 마커 */}
          {nearestStation && (
            <Marker
              position={[
                Number((nearestStation as any).lat),
                Number((nearestStation as any).lng),
              ]}
              icon={getNearestStationIcon()}
            >
              <Popup>
                <strong>🚇 가장 가까운 역</strong>
                <br />
                {(nearestStation as any).name}
                <br />
                거리:{' '}
                {(
                  (nearestStation as any).distance_km ??
                  (nearestStation as any).distance
                ) ?? '—'}
                km
              </Popup>
            </Marker>
          )}

          {/* 접근 가능한 모든 역들 마커 */}
          {reachableStations.map((station, idx) => (
            <Marker
              key={`${station.station}-${idx}`}
              position={[station.lat, station.lng]}
              icon={getCustomIcon(getColorByTime(station.time))}
            >
              <Popup>
                <strong>{station.station}</strong>
                <br />
                도달 시간: {station.time}분
              </Popup>
            </Marker>
          ))}

          <ClickableMap onSelect={handleMapClick} />
        </MapContainer>

        {/* 범례 */}
        {reachableStations.length > 0 && (
          <div style={{ padding: '10px', fontSize: '12px', color: '#666', backgroundColor: '#f9f9f9' }}>
            <strong>범례:</strong>
            <span style={{ color: 'green', marginLeft: '10px' }}>● 15분 이하</span>
            <span style={{ color: 'orange', marginLeft: '10px' }}>● 16-30분</span>
            <span style={{ color: 'red', marginLeft: '10px' }}>● 30분 초과</span>
            <span style={{ color: '#0066FF', marginLeft: '10px' }}>🚇 가장 가까운 역</span>
            <span style={{ color: '#FF6B35', marginLeft: '10px' }}>P 선택한 위치</span>
          </div>
        )}

        {/* 등고선 생성 섹션 */}
        {coords && (
          <div style={{ 
            marginTop: '20px', 
            padding: '20px', 
            backgroundColor: '#f9f9f9', 
            borderRadius: '8px',
            textAlign: 'center'
          }}>
            <h3 style={{ marginBottom: '15px', color: '#333' }}>
              🗺️ 지하철 소요시간 등고선 생성
            </h3>
            <p style={{ marginBottom: '15px', color: '#666', fontSize: '14px' }}>
              선택한 위치를 중심으로 20분 간격의 등고선을 생성합니다 (20-100분)
            </p>
            
            <button
              onClick={generateContour}
              disabled={contourLoading}
              style={{
                padding: '12px 24px',
                backgroundColor: '#4CAF50',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: contourLoading ? 'not-allowed' : 'pointer',
                fontSize: '16px',
                fontWeight: 'bold',
                opacity: contourLoading ? 0.6 : 1
              }}
            >
              {contourLoading ? '생성 중...' : '등고선 생성하기'}
            </button>

            {/* 등고선 이미지 표시 */}
            {contourImage && (
              <div style={{ marginTop: '20px' }}>
                <h4 style={{ marginBottom: '10px', color: '#333' }}>생성된 등고선</h4>
                <img 
                  src={contourImage} 
                  alt="지하철 소요시간 등고선" 
                  style={{ 
                    maxWidth: '100%', 
                    height: 'auto', 
                    border: '2px solid #ddd',
                    borderRadius: '8px',
                    boxShadow: '0 4px 8px rgba(0,0,0,0.1)'
                  }} 
                />
                <p style={{ marginTop: '10px', fontSize: '12px', color: '#666' }}>
                  💡 파스텔 핑크-퍼플 색상으로 20분 간격의 소요시간을 표시합니다
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;