import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  MapContainer,
  TileLayer,
  useMapEvents,
  Marker,
  Popup,
  useMap,
  Circle,
  Polygon
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

// 등고선을 그리는 컴포넌트
interface Station {
  name: string;
  lat: number;
  lng: number;
  time: number;
}

interface ContourData {
  [timeKey: string]: {
    time_limit: number;
    stations: Station[];
    count: number;
    center_lat?: number; // 등고선 중심 좌표
    center_lng?: number; // 등고선 중심 좌표
  };
}

function ContourLines({ contourData, nearestStation }: { 
  contourData: ContourData | null; 
  nearestStation: any; 
}) {
  if (!contourData || !nearestStation) return null;
  
  const timeColors: { [key: string]: string } = {
    '10분': '#00FF00',    // 초록색
    '20분': '#32CD32',    // 라임그린
    '30분': '#FFFF00',    // 노란색
    '40분': '#FFA500',    // 주황색
    '50분': '#FF4500'     // 빨간색
  };
  
  console.log('ContourLines 렌더링:', contourData);
  
  if (!contourData || typeof contourData !== 'object') {
    console.log('ContourLines: 데이터 없음');
    return null;
  }
  
  const timeKeys = Object.keys(contourData);
  console.log('ContourLines: 데이터 있음, 역 개수:', timeKeys.map(k => `${k}: ${contourData[k].count}개`));
  
  return (
    <>
      {timeKeys.map((timeKey) => {
        const data = contourData[timeKey];
        const color = timeColors[timeKey] || '#000000';
        
        // 시간대별로 투명도 조정 (겹치지 않도록)
        const opacity = timeKey === '10분' ? 0.8 : 
                      timeKey === '20분' ? 0.7 : 
                      timeKey === '30분' ? 0.6 : 
                      timeKey === '40분' ? 0.5 : 0.4;
        
        if (!data.stations || !Array.isArray(data.stations)) {
          console.log(`ContourLines: ${timeKey} 데이터 문제`, data);
          return null;
        }
        
        console.log(`ContourLines: ${timeKey} 렌더링 중, ${data.count}개 역`);
        
        // 구불구불한 등고선을 그리기 위한 다각형 생성
        if (data.stations.length > 2) {
          // 역들을 연결한 경계선 좌표 생성
          const coordinates = data.stations.map(station => [station.lat, station.lng]);
          
          // Convex Hull 알고리즘을 사용하여 경계선 생성
          // 간단한 버전: 중앙점에서 가장 먼 역들을 연결
          const centerLat = data.center_lat || nearestStation.lat;
          const centerLng = data.center_lng || nearestStation.lng;
          
          // 중앙에서 가장 먼 역들을 찾아서 경계선 생성
          const boundaryStations = [];
          const angles = [];
          
          data.stations.forEach(station => {
            if (station.name !== nearestStation.name) {
              const angle = Math.atan2(
                station.lat - centerLat,
                station.lng - centerLng
              );
              angles.push({ angle, station });
            }
          });
          
          // 각도별로 정렬하여 경계선 생성
          angles.sort((a, b) => a.angle - b.angle);
          const boundaryCoords = angles.map(item => [item.station.lat, item.station.lng]);
          
          // 시작 역을 경계선에 추가
          boundaryCoords.unshift([centerLat, centerLng]);
          boundaryCoords.push([centerLat, centerLng]); // 닫힌 다각형
          
          return (
            <Polygon
              key={`contour-${timeKey}`}
              positions={boundaryCoords}
              pathOptions={{
                color: color,
                fillColor: color,
                fillOpacity: opacity,
                weight: 2
              }}
            />
          );
        }
        
        return null;
      })}
    </>
  );
}

// 등고선 범례 컴포넌트
function ContourLegend({ contourData }: { contourData: ContourData | null }) {
  if (!contourData) return null;

  const timeColors: { [key: string]: string } = {
    '20분': '#00FF00',
    '40분': '#FFFF00',
    '60분': '#FFA500',
    '80분': '#FF4500',
    '100분': '#8B0000'
  };

  return (
    <div style={{
      position: 'absolute',
      top: '10px',
      right: '10px',
      backgroundColor: 'white',
      padding: '10px',
      borderRadius: '5px',
      boxShadow: '0 2px 10px rgba(0,0,0,0.1)',
      zIndex: 1000,
      minWidth: '150px'
    }}>
      <h4 style={{ margin: '0 0 10px 0', fontSize: '14px' }}>도달 시간 등고선</h4>
      {Object.entries(contourData).map(([timeKey, data]) => (
        <div key={timeKey} style={{ 
          display: 'flex', 
          alignItems: 'center', 
          marginBottom: '5px',
          fontSize: '12px'
        }}>
          <div style={{
            width: '15px',
            height: '15px',
            backgroundColor: timeColors[timeKey],
            borderRadius: '50%',
            marginRight: '8px',
            opacity: 0.7
          }} />
          <span>{timeKey}: {data.count}개 역</span>
        </div>
      ))}
    </div>
  );
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
  const [nearestStation, setNearestStation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [contourData, setContourData] = useState<ContourData | null>(null);
  
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
      const response = await axios.post('http://localhost:5000/api/nearest-station', {
        lat,
        lng
      });
      
      setNearestStation(response.data);
      console.log('가장 가까운 역:', response.data);
      
      // 등고선 데이터 가져오기
      if (response.data.name) {
        try {
          console.log('등고선 데이터 요청 중... 역명:', response.data.name);
          const contourResponse = await axios.post('http://localhost:5000/api/contour-data', {
            station_name: response.data.name
          });
          console.log('등고선 데이터 응답:', contourResponse.data);
          
          // 등고선 데이터 구조 확인
          if (contourResponse.data) {
            console.log('등고선 데이터 키들:', Object.keys(contourResponse.data));
            Object.entries(contourResponse.data).forEach(([timeKey, data]) => {
              console.log(`${timeKey}: ${data.count}개 역`);
            });
          }
          
          setContourData(contourResponse.data);
        } catch (error) {
          console.error('등고선 데이터 가져오기 실패:', error);
          setContourData(null);
        }
      }
    } catch (error) {
      console.error('가장 가까운 역 찾기 실패:', error);
      setNearestStation(null);
      setContourData(null);
    }
  };

  // 주소 검색 핸들러
 const handleSearch = async () => {
    if (!address.trim()) return;
    
    setLoading(true);
    try {
      const response = await axios.post('http://localhost:5000/api/geocode', {
        address
      });

      const newCoords = { lat: response.data.lat, lng: response.data.lng };
      setCoords(newCoords);
      setErrorMessage(null);
      
      // 가장 가까운 지하철역 찾기
      await findNearestStation(parseFloat(response.data.lat), parseFloat(response.data.lng));
      
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
    
    // 가장 가까운 지하철역 찾기 (등고선 데이터도 함께 가져옴)
    await findNearestStation(lat, lng);
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
            {contourData && (
              <div style={{ marginTop: '5px', fontSize: '12px', color: '#28a745' }}>
                ✅ 등고선 데이터 로드 완료: {Object.entries(contourData).map(([k, v]) => `${k}(${v.count}개)`).join(', ')}
              </div>
            )}
            {!contourData && (
              <div style={{ marginTop: '5px', fontSize: '12px', color: '#dc3545' }}>
                ⏳ 등고선 데이터 로딩 중...
              </div>
            )}
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

          {/* 등고선 컴포넌트 */}
          {nearestStation && (
            <ContourLines contourData={contourData} nearestStation={nearestStation} />
          )}

          {/* 등고선 범례 */}
          {contourData && <ContourLegend contourData={contourData} />}

          <ClickableMap onSelect={handleMapClick} />
        </MapContainer>

        {/* 범례 */}
        {contourData && (
          <div style={{ padding: '10px', fontSize: '12px', color: '#666', backgroundColor: '#f9f9f9' }}>
            <strong>범례:</strong>
            <div style={{ marginTop: '5px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#00FF00', borderRadius: '50%' }}></div>
                <span>● 10분 이하</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#32CD32', borderRadius: '50%' }}></div>
                <span>● 11-20분</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#FFFF00', borderRadius: '50%' }}></div>
                <span>● 21-30분</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#FFA500', borderRadius: '50%' }}></div>
                <span>● 31-40분</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <div style={{ width: '12px', height: '12px', backgroundColor: '#FF4500', borderRadius: '50%' }}></div>
                <span>● 41-50분</span>
              </div>
            </div>
            <div style={{ marginTop: '5px', fontSize: '11px' }}>
              🚇 가장 가까운 역<br/>
              📍 선택한 위치
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;