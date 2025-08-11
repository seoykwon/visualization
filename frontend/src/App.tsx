import React, { useState } from 'react';
import axios from 'axios';
import {
  MapContainer,
  TileLayer,
  useMapEvents,
  Marker,
  Popup
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { LeafletMouseEvent } from 'leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import { useMap } from 'react-leaflet';
import { useEffect } from 'react';

function getColorByTime(time: number): string {
  if (time <= 15) return 'green';
  if (time <= 30) return 'orange';
  return 'red';
}

function getCustomIcon(color: string) {
  return new L.Icon({
    iconUrl: `/marker-icon-${color}.png`, // 또는 직접 색상 svg 아이콘 사용
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowUrl: require('leaflet/dist/images/marker-shadow.png'),
    shadowSize: [41, 41],
  });
}

function MapCenterUpdater({ coords }: { coords: Coords }) {
  const map = useMap();

  // coords가 바뀔 때마다 중심 이동
  useEffect(() => {
    map.setView([parseFloat(coords.lat), parseFloat(coords.lng)], map.getZoom());
  }, [coords]);

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

function App() {
  const [address, setAddress] = useState('');
  const [coords, setCoords] = useState<Coords | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reachableStations, setReachableStations] = useState<ReachableStation[]>([]);

  const handleSearch = async () => {
    try {
      const res = await axios.post<Coords>('http://localhost:5000/api/geocode', {
        address,
      });
      setCoords(res.data);
      setErrorMessage(null);
    } catch (error) {
      console.error('검색 실패:', error);
      setCoords(null);
      setErrorMessage('주소 또는 장소를 찾을 수 없습니다.');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <div>
      <h1>서울 접근성 지도</h1>
      {/* <input
        type="text"
        value={address}
        onChange={(e) => setAddress(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="주소 또는 지하철역 이름 입력"
        style={{ width: '300px', marginRight: '1rem' }}
      />
      <button onClick={handleSearch}>위치 검색</button>

      {coords && (
        <p>
          위도: {coords.lat} <br />
          경도: {coords.lng}
        </p>
      )} */}

      <MapContainer
        center={coords ? [parseFloat(coords.lat), parseFloat(coords.lng)] : [37.5665, 126.9780]}
        zoom={11}
        style={{ height: '500px', marginTop: '1rem' }}
      >
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
        />

        {coords && (
          <>
            <Marker position={[parseFloat(coords.lat), parseFloat(coords.lng)]}>
              <Popup>
                위도: {coords.lat}, <br />경도: {coords.lng}
              </Popup>
            </Marker>
            <MapCenterUpdater coords={coords} /> {/* ✅ 중심 이동 담당 */}
          </>
        )}

        <ClickableMap
          onSelect={(lat, lng) => {
            const newCoords = { lat: lat.toString(), lng: lng.toString() };
            setCoords(newCoords);

            axios
              .post<ReachableStation[]>('http://localhost:5000/api/accessible', newCoords)
              .then((res) => {
                console.log('접근 가능 영역 결과:', res.data);
                // TODO: 결과 기반으로 등고선 또는 마커 그리기
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


      {errorMessage && <p style={{ color: 'red' }}>{errorMessage}</p>}
    </div>
  );
}

export default App;
