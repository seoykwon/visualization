// src/App.tsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  MapContainer,
  TileLayer,
  useMapEvents,
  Marker,
  Popup,
  useMap,
  Polygon,
  Tooltip,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

// ─────────────────────────────────────────────────────
// 0) Leaflet 기본 마커 이미지 설정
// ─────────────────────────────────────────────────────
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

// ─────────────────────────────────────────────────────
// 1) 타입
// ─────────────────────────────────────────────────────
interface Station {
  name: string;
  lat: number;
  lng: number;
  time: number; // 기준(원점) 역 → 이 역까지 소요시간(분)
}
interface ContourData {
  [timeKey: string]: {
    time_limit: number;
    stations: Station[];
    count: number;
    center_lat?: number;
    center_lng?: number;
  };
}
interface Coords {
  lat: string;
  lng: string;
}
type PinnedTip = {
  pos: { lat: number; lng: number };              // 사용자가 클릭한 지점
  nearName: string;                                // 그 지점의 최근접역 이름
  nearLatLng: { lat: number; lng: number };       // 최근접역 좌표
  timeMin: number;                                 // 원점역 ↔ 최근접역 소요시간(분)
  distanceKm: number;                              // 클릭 지점 ↔ 최근접역 거리
};

// ─────────────────────────────────────────────────────
// 2) 색상 팔레트(단일 소스) & 매핑/범례 항목
// ─────────────────────────────────────────────────────
const timeColors: Record<number, string> = {
  10: '#00FF00',
  20: '#32CD32',
  30: '#FFFF00',
  40: '#FFA500',
  50: '#FF4500',
};
const overTimeColor = '#808080'; // 50분 초과
const thresholdsAsc = Object.keys(timeColors).map(Number).sort((a, b) => a - b);

function getTimeColor(time: number): string {
  if (time > 50) return overTimeColor;
  for (const t of thresholdsAsc) {
    if (time <= t) return timeColors[t];
  }
  return overTimeColor;
}

const legendItems = [
  { label: '10분 이하', color: timeColors[10] },
  { label: '20분 이하', color: timeColors[20] },
  { label: '30분 이하', color: timeColors[30] },
  { label: '40분 이하', color: timeColors[40] },
  { label: '50분 이하', color: timeColors[50] },
  { label: '50분 초과', color: overTimeColor },
];

// ─────────────────────────────────────────────────────
/** 3) 거리/최근접 유틸 */
// ─────────────────────────────────────────────────────
function haversine(lat1: number, lng1: number, lat2: number, lng2: number) {
  const R = 6371;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a)); // km
}
function getNearestStationTime(lat: number, lng: number, stations: Station[]) {
  if (!stations.length) return 60;
  let minD = Infinity;
  let time = stations[0].time;
  for (const s of stations) {
    const d = haversine(lat, lng, s.lat, s.lng);
    if (d < minD) {
      minD = d;
      time = s.time;
    }
  }
  return time;
}
function collectAllStations(contourData: ContourData | null): Station[] {
  if (!contourData) return [];
  const out: Station[] = [];
  Object.values(contourData).forEach((t) => {
    (t.stations || []).forEach((s) => {
      const lat = Number(s.lat);
      const lng = Number(s.lng);
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        out.push({ ...s, lat, lng });
      }
    });
  });
  return out;
}
function getNearestStationDetail(
  lat: number,
  lng: number,
  stations: Station[]
): { station: Station; distanceKm: number } | null {
  if (!stations.length) return null;
  let best = stations[0];
  let bestD = haversine(lat, lng, best.lat, best.lng);
  for (let i = 1; i < stations.length; i++) {
    const s = stations[i];
    const d = haversine(lat, lng, s.lat, s.lng);
    if (d < bestD) {
      best = s;
      bestD = d;
    }
  }
  return { station: best, distanceKm: bestD };
}

// ─────────────────────────────────────────────────────
/** 4) 최근접 그리드 생성 (격자 해상도 gridSizeDeg로 조절) */
// ─────────────────────────────────────────────────────
function createNearestNeighborGrid(
  contourData: ContourData,
  bounds?: { north: number; south: number; east: number; west: number },
  gridSizeDeg = 0.003
) {
  const allStations: Station[] = [];
  Object.values(contourData).forEach((timeData) => {
    timeData.stations?.forEach((s) => {
      const lat = Number(s.lat);
      const lng = Number(s.lng);
      if (Number.isFinite(lat) && Number.isFinite(lng)) {
        allStations.push({ ...s, lat, lng });
      }
    });
  });
  if (!allStations.length) return [];

  const area =
    bounds || { north: 37.70, south: 37.43, east: 127.27, west: 126.70 };

  const cells: { bounds: [number, number][], color: string, time: number }[] = [];
  for (let lat = area.south; lat < area.north; lat += gridSizeDeg) {
    for (let lng = area.west; lng < area.east; lng += gridSizeDeg) {
      const cLat = lat + gridSizeDeg / 2;
      const cLng = lng + gridSizeDeg / 2;

      const time = getNearestStationTime(cLat, cLng, allStations);
      const color = getTimeColor(time);

      const poly: [number, number][] = [
        [lat, lng],
        [lat + gridSizeDeg, lng],
        [lat + gridSizeDeg, lng + gridSizeDeg],
        [lat, lng + gridSizeDeg],
      ];
      cells.push({ bounds: poly, color, time });
    }
  }
  return cells;
}

// ─────────────────────────────────────────────────────
/** 5) 맵 보조 컴포넌트 */
// ─────────────────────────────────────────────────────
function MapCenterUpdater({ coords }: { coords: Coords | null }) {
  const map = useMap();
  useEffect(() => {
    if (coords) {
      map.setView([parseFloat(coords.lat), parseFloat(coords.lng)], map.getZoom());
    }
  }, [coords, map]);
  return null;
}
function ClickableMap({
  onClickMap,
}: {
  onClickMap: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click(e) {
      onClickMap(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

// ─────────────────────────────────────────────────────
/** 6) 아이콘 */
// ─────────────────────────────────────────────────────
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

// ─────────────────────────────────────────────────────
/** 7) 범례 (legendItems만 사용 → 지도와 100% 일치) */
// ─────────────────────────────────────────────────────
function Legend() {
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
      minWidth: '160px'
    }}>
      <h4 style={{ margin: '0 0 10px 0', fontSize: '14px' }}>도달 시간(분)</h4>
      {legendItems.map((item) => (
        <div key={item.label} style={{ display: 'flex', alignItems: 'center', marginBottom: '6px', fontSize: '12px' }}>
          <div style={{
            width: '16px', height: '16px', backgroundColor: item.color,
            borderRadius: '3px', marginRight: '8px', border: '1px solid rgba(0,0,0,0.1)'
          }} />
          <span>{item.label}</span>
        </div>
      ))}
      <div style={{ fontSize: '11px', color: '#888', marginTop: '6px' }}>
        각 셀은 해당 위치에서 <b>가장 가까운 역</b>의 소요시간을 나타냅니다.
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────
/** 8) 색상 레이어 (최근접 그리드) */
// ─────────────────────────────────────────────────────
function UnifiedColorContours({
  contourData,
  nearestStation,
}: {
  contourData: ContourData | null;
  nearestStation: any;
}) {
  if (!contourData || !nearestStation) return null;
  const colorRegions = createNearestNeighborGrid(contourData, undefined, 0.003);
  return (
    <>
      {colorRegions.map((region, index) => (
        <Polygon
          key={`color-region-${index}`}
          positions={region.bounds}
          pathOptions={{
            color: 'transparent',
            fillColor: region.color,
            fillOpacity: 0.5,
            weight: 0,
            smoothFactor: 1.0,
          }}
        />
      ))}
    </>
  );
}

// ─────────────────────────────────────────────────────
/** 9) Kakao 지도 길찾기(웹) 열기 */
// ─────────────────────────────────────────────────────
function openKakaoTransitRoute(
  start: { lat: number; lng: number; name: string },
  end: { lat: number; lng: number; name: string },
  swap: boolean = false
) {
  const s = swap ? end : start;
  const e = swap ? start : end;

  const url = `https://map.kakao.com/?sName=${s.name}&sx=${s.lng}&sy=${s.lat}&eName=${e.name}&ex=${e.lng}&ey=${e.lat}&by=SUBWAY`;
  window.open(url, "_blank");
}


// ─────────────────────────────────────────────────────
/** 10) 커서 따라다니는 툴팁(hover 즉시) & 핀 고정 툴팁 */
// ─────────────────────────────────────────────────────
function CursorFollowerTooltip({
  contourData,
  originStationName,
  disabled,
}: {
  contourData: ContourData | null;
  originStationName?: string;
  disabled?: boolean;
}) {
  const map = useMap();
  const [pos, setPos] = React.useState<{ lat: number; lng: number } | null>(null);
  const [info, setInfo] = React.useState<{ nearName: string; timeMin: number; distanceKm: number } | null>(null);
  const stations = React.useMemo(() => collectAllStations(contourData), [contourData]);

  React.useEffect(() => {
    if (!map || disabled) return;
    const onMove = (e: any) => {
      const { lat, lng } = e.latlng || {};
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
      setPos({ lat, lng });
      const d = getNearestStationDetail(lat, lng, stations);
      if (!d) return setInfo(null);
      setInfo({
        nearName: d.station.name,
        timeMin: Math.round(d.station.time ?? 0),
        distanceKm: d.distanceKm,
      });
    };
    const onOut = () => { setPos(null); setInfo(null); };
    map.on('mousemove', onMove);
    map.on('mouseout', onOut);
    return () => {
      map.off('mousemove', onMove);
      map.off('mouseout', onOut);
    };
  }, [map, stations, disabled]);

  if (disabled || !pos || !info) return null;

  return (
    <Marker position={[pos.lat, pos.lng]} opacity={0} interactive={false} keyboard={false}>
      <Tooltip permanent direction="top" offset={[0, -10]} interactive>
        <div style={{ fontSize: 12, lineHeight: 1.4 }}>
          <div><b>커서 최근접역</b>: {info.nearName}</div>
          {originStationName ? (
            <div><b>{originStationName}</b> ↔ <b>{info.nearName}</b> : {info.timeMin}분</div>
          ) : (
            <div>소요시간: {info.timeMin}분</div>
          )}
          <div style={{ color: '#666' }}>(커서↔역: {info.distanceKm.toFixed(2)} km)</div>
        </div>
      </Tooltip>
    </Marker>
  );
}

function PinnedTooltip({
  pinned,
  originCoords,
  originStationName,
  onClose,
}: {
  pinned: PinnedTip;
  originCoords?: { lat: string; lng: string } | null;
  originStationName?: string;
  onClose: () => void;
}) {
  if (!pinned) return null;
  const pos = pinned.pos;
  return (
    <Marker position={[pos.lat, pos.lng]} opacity={0} interactive={false} keyboard={false}>
      <Tooltip permanent direction="top" offset={[0, -10]} interactive bubblingMouseEvents={false}>
        <div style={{ fontSize: 12, lineHeight: 1.5, maxWidth: 240 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <b>관심 지점</b>
            <button
              type="button"
              onClick={(e) => {                 // 👈 전파/기본동작 차단
                e.stopPropagation();
                e.preventDefault();
                onClose();
              }}
              style={{ border: 'none', background: 'transparent', cursor: 'pointer', fontWeight: 700 }}
              aria-label="닫기"
              title="닫기"
            >
              ×
            </button>
          </div>

          <div style={{ marginTop: 4 }}>
            <div><b>최근접역</b>: {pinned.nearName}</div>
            {originStationName ? (
              <div><b>{originStationName}</b> ↔ <b>{pinned.nearName}</b> : {pinned.timeMin}분</div>
            ) : (
              <div>소요시간: {pinned.timeMin}분</div>
            )}
            <div style={{ color: '#666' }}>(지점↔역: {pinned.distanceKm.toFixed(2)} km)</div>
          </div>

          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();            // 👈 전파 차단
                e.preventDefault();
                openNaverRoomsAt(pos.lat, pos.lng);
              }}
              style={{
                padding: '4px 8px', fontSize: 12, backgroundColor: '#00C73C',
                color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer'
              }}
            >
              🏠 매물 보기
            </button>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();            // 👈 전파 차단
                e.preventDefault();
                const startLat = originCoords ? parseFloat(originCoords.lat) : pos.lat;
                const startLng = originCoords ? parseFloat(originCoords.lng) : pos.lng;
                const startName = originStationName ?? '출발지';
                openKakaoTransitRoute(
                  { lat: startLat, lng: startLng, name: startName },
                  { lat: pinned.nearLatLng.lat, lng: pinned.nearLatLng.lng, name: pinned.nearName },
                  true
                );
              }}
              style={{
                padding: '4px 8px', fontSize: 12, backgroundColor: '#4B89DC',
                color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer'
              }}
            >
              🚇 지하철 경로
            </button>
          </div>
        </div>
      </Tooltip>
    </Marker>
  );
}

// ─────────────────────────────────────────────────────
/** 11) 앱 유틸 */
// ─────────────────────────────────────────────────────
function openNaverRoomsAt(lat: number, lng: number): void {
  const zoom = 15;
  const url = `https://new.land.naver.com/rooms?ms=${lat},${lng},${zoom}&a=APT:OPST:ABYG:OBYG:GM:OR:DDDGG:JWJT:SGJT:HOJT:VL&e=RETAIL&aa=SMALLSPCRENT`;
  window.open(url, "_blank", "noopener,noreferrer");
}

// ─────────────────────────────────────────────────────
/** 12) 메인 앱 */
// ─────────────────────────────────────────────────────
function App() {
  const [address, setAddress] = useState('');
  const [coords, setCoords] = useState<Coords | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [nearestStation, setNearestStation] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [contourData, setContourData] = useState<ContourData | null>(null);
  const [mapKey, setMapKey] = useState(0);

  const handleReset = () => {
  setAddress('');
  setCoords(null);
  setErrorMessage(null);
  setNearestStation(null);
  setContourData(null);
  setLoading(false);
  setHasOrigin(false);
  setPinned(null);
  // 지도도 초기 중심/줌으로 돌아가도록 전체 리마운트
  setMapKey((k) => k + 1);
};

  // 기준(설정) 위치를 한 번이라도 정했는지
  const [hasOrigin, setHasOrigin] = useState(false);
  // 클릭으로 고정한 툴팁
  const [pinned, setPinned] = useState<PinnedTip | null>(null);

  const reverseGeocode = async (lat: string, lng: string): Promise<string> => {
    try {
      const response = await axios.post('http://localhost:5000/api/reverse-geocode', {
        lat: parseFloat(lat), lng: parseFloat(lng),
      });
      const addr = response?.data?.address;
      if (addr && typeof addr === 'string' && addr.trim() && !addr.includes('위도') && !addr.includes('경도')) {
        setAddress(addr);
        setErrorMessage(null);
        return addr;
      }
      throw new Error('유효한 주소를 찾을 수 없습니다');
    } catch {
      const fallbackAddress = `위도: ${parseFloat(lat).toFixed(6)}, 경도: ${parseFloat(lng).toFixed(6)}`;
      setAddress(fallbackAddress);
      return fallbackAddress;
    }
  };

  const findNearestStation = async (lat: number, lng: number) => {
    try {
      const response = await axios.post('http://localhost:5000/api/nearest-station', { lat, lng });
      setNearestStation(response.data);
      if (response.data?.name) {
        try {
          const contourResponse = await axios.post('http://localhost:5000/api/contour-data', {
            station_name: response.data.name
          });
          setContourData(contourResponse.data);
        } catch {
          setContourData(null);
        }
      }
    } catch {
      setNearestStation(null);
      setContourData(null);
    }
  };

  const handleSearch = async () => {
    if (!address.trim()) return;
    setLoading(true);
    try {
      const response = await axios.post('http://localhost:5000/api/geocode', { address });
      const newCoords = { lat: response.data.lat, lng: response.data.lng };
      setCoords(newCoords);
      setHasOrigin(true); // ★ 기준 위치 확정
      setPinned(null);    // ★ 기존 핀 제거
      setErrorMessage(null);
      await findNearestStation(parseFloat(response.data.lat), parseFloat(response.data.lng));
    } catch {
      setCoords(null);
      setNearestStation(null);
      setErrorMessage('주소 또는 장소를 찾을 수 없습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleSearch();
  };

  // ★ 클릭 분기: 첫 클릭은 기준 위치 설정, 이후 클릭은 핀 고정(툴팁 고정)
  const handleMapClick = async (lat: number, lng: number) => {
    if (!hasOrigin) {
      const newCoords = { lat: lat.toString(), lng: lng.toString() };
      setCoords(newCoords);
      setHasOrigin(true);
      setPinned(null);
      try { await reverseGeocode(String(lat), String(lng)); } catch {}
      await findNearestStation(lat, lng);
      return;
    }

    // 이후 클릭: 핀 고정
    const stations = collectAllStations(contourData);
    const detail = getNearestStationDetail(lat, lng, stations);
    if (!detail) return;
    setPinned({
      pos: { lat, lng },
      nearName: detail.station.name,
      nearLatLng: { lat: detail.station.lat, lng: detail.station.lng },
      timeMin: Math.round(detail.station.time ?? 0),
      distanceKm: detail.distanceKm,
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* 헤더 */}
      <div style={{ padding: '15px', backgroundColor: '#f5f5f5', borderBottom: '1px solid #ddd', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ margin: 0 }}>서울 지하철 역간 접근성 지도</h1>
        </div>

        {/* 검색/버튼 줄 */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="📍 주소 입력 또는 지도 클릭"
            style={{ width: '300px', padding: '8px', fontSize: '14px' }}
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

          <button
              onClick={handleReset}
              style={{ padding: '8px 16px', fontSize: '14px', backgroundColor: '#6c757d', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
            >
              초기화
            </button>

          <button
            onClick={() => {
              if (!coords) return;
              const lat = parseFloat(coords.lat);
              const lng = parseFloat(coords.lng);
              openNaverRoomsAt(lat, lng);
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

        {/* 선택된 위치 */}
        {coords && (
          <div style={{ padding: '10px', backgroundColor: '#fff3cd', borderRadius: '5px', fontSize: '14px', border: '1px solid #ffeaa7' }}>
            <strong>📍 선택된 위치:</strong>{' '}
            {address && !address.includes('위도') && !address.includes('경도')
              ? address
              : `위도: ${parseFloat(coords.lat).toFixed(4)}, 경도: ${parseFloat(coords.lng).toFixed(4)}`}
            {address && address.includes('위도') && (
              <div style={{ fontSize: '12px', color: '#666', marginTop: '5px' }}>
                💡 정확한 주소를 가져오는 중입니다...
              </div>
            )}
          </div>
        )}

        {/* 가장 가까운 역 정보 */}
        {nearestStation && (
          <div style={{ padding: '10px', backgroundColor: '#e8f4f8', borderRadius: '5px', fontSize: '14px' }}>
            <strong>🚇 가장 가까운 지하철역:</strong> {nearestStation.name}
            <span style={{ color: '#666' }}>
              {' '}(거리:{' '}
              {((nearestStation as any).distance_km ?? (nearestStation as any).distance) ?? '—'} km)
            </span>
            {contourData && (
              <div style={{ marginTop: '5px', fontSize: '12px', color: '#28a745' }}>
                ✅ 등고선 데이터 로드 완료: {Object.entries(contourData).map(([k, v]) => `${k}(${(v as any).count}개)`).join(', ')}
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

      {/* 지도 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        <MapContainer
          center={coords ? [parseFloat(coords.lat), parseFloat(coords.lng)] : [37.5665, 126.978]}
          zoom={13}
          style={{ flex: 1, width: '100%', border: '1px solid #ddd', borderRadius: '8px' }}
        >
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {coords && <MapCenterUpdater coords={coords} />}

          {/* 선택 위치 마커 (기준 위치) */}
          {coords && (
            <Marker position={[parseFloat(coords.lat), parseFloat(coords.lng)]} icon={getSelectedLocationIcon()}>
              <Popup>
                <strong>📍 선택한 위치</strong>
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

          {/* 가장 가까운 역 마커 */}
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
                {((nearestStation as any).distance_km ?? (nearestStation as any).distance) ?? '—'} km
              </Popup>
            </Marker>
          )}

          {/* 색상 레이어 */}
          {nearestStation && (
            <UnifiedColorContours contourData={contourData} nearestStation={nearestStation} />
          )}

          {/* 커서 툴팁: 핀이 있을 땐 비활성화 */}
          {nearestStation && (
            <CursorFollowerTooltip
              contourData={contourData}
              originStationName={nearestStation?.name}
              disabled={!!pinned}
            />
          )}

          {/* 핀 고정 툴팁 */}
          {pinned && (
            <PinnedTooltip
              pinned={pinned}
              originCoords={coords}
              originStationName={nearestStation?.name}
              onClose={() => setPinned(null)}
            />
          )}

          {/* 범례 */}
          <Legend />

          {/* 클릭 처리 */}
          <ClickableMap onClickMap={handleMapClick} />
        </MapContainer>
      </div>
    </div>
  );
}

export default App;
