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
  60: '#FF0000',
  70: '#8B0000',
  80: '#4B0082',
  90: '#2F4F4F',
  100: '#000000',
};
const overTimeColor = '#808080'; // 100분 초과
const thresholdsAsc = Object.keys(timeColors).map(Number).sort((a, b) => a - b);

function getTimeColor(time: number, isSumMode: boolean = false): string {
  if (isSumMode) {
    // 다중모드: 20, 40, 60, 80분 기준
    if (time <= 20) return timeColors[20];
    if (time <= 40) return timeColors[40];
    if (time <= 60) return timeColors[60];
    if (time <= 80) return timeColors[80];
    return overTimeColor; // 80분 초과
  } else {
    // 단일모드: 기존 50분까지
    if (time > 50) return overTimeColor;
    for (const t of [10, 20, 30, 40, 50]) {
      if (time <= t) return timeColors[t];
    }
    return overTimeColor;
  }
}

const legendItems = [
  { label: '0~10분', color: timeColors[10] },
  { label: '11~20분', color: timeColors[20] },
  { label: '21~30분', color: timeColors[30] },
  { label: '31~40분', color: timeColors[40] },
  { label: '41~50분', color: timeColors[50] },
  { label: '50분 초과', color: overTimeColor },
];

const legendItemsSum = [
  { label: '0~20분', color: timeColors[20] },
  { label: '21~40분', color: timeColors[40] },
  { label: '41~60분', color: timeColors[60] },
  { label: '61~80분', color: timeColors[80] },
  { label: '80분 초과', color: overTimeColor },
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
  // 자기자신이 목적지일 때는 0분 반환 (거리가 매우 가까울 때)
  if (minD < 0.1) { // 100m 이내
    return 0;
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
      const time = Number(s.time); // 시간도 숫자로 변환
      if (Number.isFinite(lat) && Number.isFinite(lng) && Number.isFinite(time)) {
        out.push({ ...s, lat, lng, time });
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
// 유틸: 스테이션 목록/타임맵/최근접 계산(2원점 합계용)
// ─────────────────────────────────────────────────────
function collectStationsOnlyGeometry(contourData: ContourData | null): Station[] {
  if (!contourData) return [];
  const seen = new Set<string>();
  const out: Station[] = [];
  Object.values(contourData).forEach((t) => {
    (t.stations || []).forEach((s) => {
      if (!seen.has(s.name)) {
        const lat = Number(s.lat);
        const lng = Number(s.lng);
        const time = Number(s.time); // 시간도 숫자로 변환
        if (Number.isFinite(lat) && Number.isFinite(lng) && Number.isFinite(time)) {
          out.push({ ...s, lat, lng, time });
          seen.add(s.name);
        }
      }
    });
  });
  return out;
}

function buildTimeMapByName(contourData: ContourData | null): Map<string, number> {
  const m = new Map<string, number>();
  if (!contourData) return m;
  
  // 역명 정규화 함수 (백엔드에서 이미 정규화된 역명을 반환하므로 단순화)
  const normalizeStationName = (name: string): string => {
    // 백엔드에서 이미 정규화된 역명을 반환하므로 추가 정규화 없이 그대로 사용
    return name.trim();
  };
  
  // 모든 시간대의 스테이션을 순회하면서 시간 정보 수집
  Object.values(contourData).forEach((timeData) => {
    (timeData.stations || []).forEach((station) => {
      const time = Number(station.time);
      if (Number.isFinite(time)) {
        const normalizedName = normalizeStationName(station.name);
        // 같은 역이 여러 시간대에 있을 수 있으므로, 더 작은 시간을 우선 선택
        const existingTime = m.get(normalizedName);
        if (existingTime === undefined || time < existingTime) {
          m.set(normalizedName, time);
        }
      }
    });
  });
  
  console.log(`Built time map with ${m.size} stations:`, Array.from(m.entries()).slice(0, 5));
  // 무악재와 관악산 관련 역들 확인
  const relevantStations = Array.from(m.entries()).filter(([name, time]) => 
    name.includes('무악재') || name.includes('관악산')
  );
  if (relevantStations.length > 0) {
    console.log('Relevant stations in time map:', relevantStations);
    console.log('Relevant stations details:', relevantStations.map(([name, time]) => `${name}: ${time}분`));
  }
  return m;
}

function getNearestByGeometry(
  lat: number, lng: number, stations: Station[]
): { station: Station; distanceKm: number } | null {
  if (!stations.length) return null;
  let best = stations[0];
  let bestD = haversine(lat, lng, best.lat, best.lng);
  for (let i = 1; i < stations.length; i++) {
    const d = haversine(lat, lng, stations[i].lat, stations[i].lng);
    if (d < bestD) { best = stations[i]; bestD = d; }
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
      const time = Number(s.time);
      if (Number.isFinite(lat) && Number.isFinite(lng) && Number.isFinite(time)) {
        allStations.push({ ...s, lat, lng, time });
      }
    });
  });
  if (!allStations.length) return [];

  // 역들의 위치를 기반으로 동적으로 경계 계산
  const lats = allStations.map(s => s.lat);
  const lngs = allStations.map(s => s.lng);
  
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  
  // 경계에 여백 추가 (0.02도 = 약 2km)
  const padding = 0.02;
  const area = bounds || {
    north: maxLat + padding,
    south: minLat - padding,
    east: maxLng + padding,
    west: minLng - padding
  };

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

function FitBoundsToOrigins({ coords1, coords2 }: { coords1: Coords | null; coords2: Coords | null }) {
  const map = useMap();
  useEffect(() => {
    if (coords1 && coords2) {
      const b = L.latLngBounds(
        [parseFloat(coords1.lat), parseFloat(coords1.lng)],
        [parseFloat(coords2.lat), parseFloat(coords2.lng)]
      );
      map.fitBounds(b, { padding: [50, 50] });
    }
  }, [coords1, coords2, map]);
  return null;
}

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
// 아이콘(라벨/색상 파라미터화, btoa 대신 utf8 data URL)
// ─────────────────────────────────────────────────────
function makeMarkerIcon(label: string, fill: string) {
  const svg = `
    <svg width="30" height="46" viewBox="0 0 30 46" xmlns="http://www.w3.org/2000/svg">
      <path d="M15 0C6.7 0 0 6.7 0 15c0 15 15 31 15 31s15-16 15-31C30 6.7 23.3 0 15 0z" fill="${fill}"/>
      <circle cx="15" cy="15" r="8" fill="white"/>
      <text x="15" y="20" text-anchor="middle" fill="${fill}" font-size="12" font-weight="bold">${label}</text>
    </svg>
  `;
  const iconUrl = `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
  return new L.Icon({
    iconUrl,
    iconSize: [30, 46],
    iconAnchor: [15, 46],
    popupAnchor: [1, -38],
  });
}

const getSelectedLocationIcon1 = () => makeMarkerIcon('A', '#FF6B35'); // 주소1
const getSelectedLocationIcon2 = () => makeMarkerIcon('B', '#9C27B0'); // 주소2
const getNearestStationIcon1 = () => makeMarkerIcon('N1', '#0066FF');  // 역1
const getNearestStationIcon2 = () => makeMarkerIcon('N2', '#00B8D9');  // 역2

// ─────────────────────────────────────────────────────
/** 7) 범례 (legendItems만 사용 → 지도와 100% 일치) */
// ─────────────────────────────────────────────────────
function Legend({ isSumMode = false }: { isSumMode?: boolean }) {
  const items = isSumMode ? legendItemsSum : legendItems;
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
      minWidth: '200px',
      maxHeight: '80vh',
      overflowY: 'auto'
    }}>
      <h4 style={{ margin: '0 0 10px 0', fontSize: '14px' }}>
        {isSumMode ? '합계 소요 시간' : '소요 시간'}
      </h4>
      {items.map((item) => (
        <div key={item.label} style={{ display: 'flex', alignItems: 'center', marginBottom: '3px', fontSize: '12px' }}>
          <div style={{
            width: '14px', height: '14px', backgroundColor: item.color,
            borderRadius: '2px', marginRight: '6px', border: '1px solid rgba(0,0,0,0.1)'
          }} />
          <span>{item.label}</span>
        </div>
      ))}
      <div style={{ fontSize: '11px', color: '#888', marginTop: '6px' }}>
        {isSumMode}
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
// 2원점 합계시간 컬러 레이어
// 해당 위치의 최근접역 s를 잡고, t_sum = t1(s) + t2(s)
// ─────────────────────────────────────────────────────
function UnifiedColorContoursSum({
  contour1, contour2,
}: {
  contour1: ContourData | null;
  contour2: ContourData | null;
}) {
  // 훅은 무조건 최상단에서
  const regions = React.useMemo(() => {
    if (!contour1 || !contour2) return [];

    const geom1 = collectStationsOnlyGeometry(contour1);
    const geom2 = collectStationsOnlyGeometry(contour2);
    const geoIndexByName = new Map<string, Station>();
    [...geom1, ...geom2].forEach((s) => { if (!geoIndexByName.has(s.name)) geoIndexByName.set(s.name, s); });
    const geometry = Array.from(geoIndexByName.values());

    const tmap1 = buildTimeMapByName(contour1);
    const tmap2 = buildTimeMapByName(contour2);

    console.log('Address1 time map size:', tmap1.size);
    console.log('Address2 time map size:', tmap2.size);
    console.log('Sample from tmap2:', Array.from(tmap2.entries()).slice(0, 3));

    const gridSizeDeg = 0.003;
    
    // 역들의 위치를 기반으로 동적으로 경계 계산
    const lats = geometry.map(s => s.lat);
    const lngs = geometry.map(s => s.lng);
    
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const minLng = Math.min(...lngs);
    const maxLng = Math.max(...lngs);
    
    // 경계에 여백 추가 (0.02도 = 약 2km)
    const padding = 0.02;
    const area = {
      north: maxLat + padding,
      south: minLat - padding,
      east: maxLng + padding,
      west: minLng - padding
    };

    const cells: { bounds: [number, number][], color: string, sum: number }[] = [];
    for (let lat = area.south; lat < area.north; lat += gridSizeDeg) {
      for (let lng = area.west; lng < area.east; lng += gridSizeDeg) {
        const cLat = lat + gridSizeDeg / 2;
        const cLng = lng + gridSizeDeg / 2;

        const nearest = getNearestByGeometry(cLat, cLng, geometry);
        if (!nearest) continue;
        const name = nearest.station.name;
        
        // 역명 정규화 (백엔드에서 이미 정규화된 역명을 반환하므로 단순화)
        const normalizeStationName = (name: string): string => {
          // 백엔드에서 이미 정규화된 역명을 반환하므로 추가 정규화 없이 그대로 사용
          return name.trim();
        };
        const normalizedName = normalizeStationName(name);

        // 시간 맵에서 역 이름으로 조회 (없으면 보수적으로 60분)
        const t1 = tmap1.get(normalizedName) ?? 60;
        const t2 = tmap2.get(normalizedName) ?? 60;
        const sum = Math.round(t1 + t2);
        


        const color = getTimeColor(sum, true); // ★ 합계 모드용 색상 팔레트 사용

        const poly: [number, number][] = [
          [lat, lng],
          [lat + gridSizeDeg, lng],
          [lat + gridSizeDeg, lng + gridSizeDeg],
          [lat, lng + gridSizeDeg],
        ];
        cells.push({ bounds: poly, color, sum });
      }
    }
    return cells;
  }, [contour1, contour2]);

  if (!regions.length) return null;

  return (
    <>
      {regions.map((region, i) => (
        <Polygon
          key={`sum-region-${i}`}
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
          <div><b>역명</b>: {info.nearName}</div>
          {originStationName ? (
            <div><b>{originStationName}</b> ↔ <b>{info.nearName}</b> : {info.timeMin}분</div>
          ) : (
            <div>소요시간: {info.timeMin}분</div>
          )}
          <div style={{ color: '#666' }}>(현위치↔역: {info.distanceKm.toFixed(2)} km)</div>
        </div>
      </Tooltip>
    </Marker>
  );
}

// ─────────────────────────────────────────────────────
// 커서 툴팁(합계 시간)
// ─────────────────────────────────────────────────────
function CursorFollowerTooltipSum({
  contour1,
  contour2,
  origin1Name,
  origin2Name,
  disabled,
}: {
  contour1: ContourData | null;
  contour2: ContourData | null;
  origin1Name?: string;
  origin2Name?: string;
  disabled?: boolean;
}) {
  const map = useMap();

  // 훅은 최상단
  const geometry = React.useMemo(() => {
    const geom1 = collectStationsOnlyGeometry(contour1);
    const geom2 = collectStationsOnlyGeometry(contour2);
    const byName = new Map<string, Station>();
    [...geom1, ...geom2].forEach((s) => { if (!byName.has(s.name)) byName.set(s.name, s); });
    return Array.from(byName.values());
  }, [contour1, contour2]);

  const tmap1 = React.useMemo(() => buildTimeMapByName(contour1), [contour1]);
  const tmap2 = React.useMemo(() => buildTimeMapByName(contour2), [contour2]);

  const [pos, setPos] = React.useState<{ lat: number; lng: number } | null>(null);
  const [info, setInfo] = React.useState<{ nearName: string; t1: number; t2: number; sum: number; distanceKm: number } | null>(null);

  React.useEffect(() => {
    if (!map || disabled) return;
    const onMove = (e: any) => {
      const { lat, lng } = e.latlng || {};
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;
      setPos({ lat, lng });

                   const nearest = getNearestByGeometry(lat, lng, geometry);
      if (!nearest) { setInfo(null); return; }
      const name = nearest.station.name;
      
             // 역명 정규화 (백엔드에서 이미 정규화된 역명을 반환하므로 단순화)
       const normalizeStationName = (name: string): string => {
         // 백엔드에서 이미 정규화된 역명을 반환하므로 추가 정규화 없이 그대로 사용
         return name.trim();
       };
      const normalizedName = normalizeStationName(name);
      const t1 = tmap1.get(normalizedName) ?? 60;
      const t2 = tmap2.get(normalizedName) ?? 60;
      setInfo({ nearName: name, t1, t2, sum: Math.round(t1 + t2), distanceKm: nearest.distanceKm });
    };
    const onOut = () => { setPos(null); setInfo(null); };

    map.on('mousemove', onMove);
    map.on('mouseout', onOut);
    return () => {
      map.off('mousemove', onMove);
      map.off('mouseout', onOut);
    };
  }, [map, geometry, tmap1, tmap2, disabled]);

  if (disabled || !pos || !info) return null;
    return (
    <Marker position={[pos.lat, pos.lng]} opacity={0} interactive={false} keyboard={false}>
      <Tooltip permanent direction="top" offset={[0, -10]} interactive>
        <div style={{ fontSize: 12, lineHeight: 1.4 }}>
          <div><b>커서 최근접역</b>: {info.nearName}</div>
          <div>{origin1Name ?? '주소1'} → {info.nearName}: {Math.round(info.t1)}분</div>
          <div>{origin2Name ?? '주소2'} → {info.nearName}: {Math.round(info.t2)}분</div>
          <div><b>합계</b>: {info.sum}분</div>
          <div style={{ color: '#666' }}>(커서↔역: {info.distanceKm.toFixed(2)} km)</div>
        </div>
      </Tooltip>
    </Marker>
  );
}

// ─────────────────────────────────────────────────────
/** 11) 핀 고정 툴팁 & 유틸 */
// ─────────────────────────────────────────────────────
function PinnedTooltip({
  pinned,
  originCoords,
  originStationName,
  onClose,
}: {
  pinned: PinnedTip | null;
  originCoords?: { lat: string; lng: string } | null;
  originStationName?: string;
  onClose: () => void;
}) {
  if (!pinned) return null;
  const pos = pinned.pos;
  return (
    <Marker position={[pos.lat, pos.lng]} opacity={0} interactive={false} keyboard={false}>
      <Tooltip permanent direction="top" offset={[0, -10]} interactive bubblingMouseEvents={false}>
        <div style={{ fontSize: 12, lineHeight: 1.5, maxWidth: 260 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <b>관심 지점</b>
            <button
              type="button"
              onClick={(e) => {
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
            <div><b>역명</b>: {pinned.nearName}</div>
            {originStationName ? (
              <div><b>{originStationName}</b> ↔ <b>{pinned.nearName}</b> : {pinned.timeMin}분</div>
            ) : (
              <div>소요시간(합계): {pinned.timeMin}분</div>
            )}
            <div style={{ color: '#666' }}>(지점↔역: {pinned.distanceKm.toFixed(2)} km)</div>
          </div>

          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                e.preventDefault();
                openNaverRoomsAt(pos.lat, pos.lng);
              }}
              style={{
                padding: '4px 8px', fontSize: 12, backgroundColor: '#00C73C',
                color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer'
              }}
            >
              매물 보기
            </button>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
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
              지하철 경로
            </button>
          </div>
        </div>
      </Tooltip>
    </Marker>
  );
}

function openNaverRoomsAt(lat: number, lng: number): void {
  const zoom = 15;
  const url = `https://new.land.naver.com/rooms?ms=${lat},${lng},${zoom}&a=APT:OPST:ABYG:OBYG:GM:OR:DDDGG:JWJT:SGJT:HOJT:VL&e=RETAIL&aa=SMALLSPCRENT`;
  window.open(url, "_blank", "noopener,noreferrer");
}

// contour API가 역 표기 때문에 실패할 수 있어 후보 이름을 생성
function normalizeStationNameCandidates(baseName: string): string[] {
  const s = String(baseName || '').trim();
  if (!s) return [];
  const noSpaces = s.replace(/\s+/g, '');
  const withoutStationWord = s.replace(/역$/u, '').trim();
  const withStationSuffix = /역$/u.test(s) ? s : `${s}역`;

  const tokens = s.split(/\s+/);
  const withParen: string[] = [];
  if (tokens.length >= 2) {
    const last = tokens[tokens.length - 1];
    const head = tokens.slice(0, -1).join('').replace(/역$/u, '');
    withParen.push(`${head}(${last})`, `${head} (${last})`, `${head}역(${last})`, `${head} 역(${last})`);
  }

  return Array.from(new Set([
    s, noSpaces, withoutStationWord, withStationSuffix, `${withoutStationWord}역`,
    ...withParen, ...withParen.map(x => x.replace(/\s+/g, '')),
  ])).filter(Boolean);
}

function isValidContourData(d: any): d is ContourData {
  if (!d || typeof d !== 'object' || 'error' in d) return false;
  const keys = Object.keys(d);
  if (!keys.length) return false;
  return keys.some(k => Array.isArray((d as any)[k]?.stations));
}

// ─────────────────────────────────────────────────────
/** 12) 메인 앱 */
// ─────────────────────────────────────────────────────
function App() {
  const [address1, setAddress1] = useState('');
  const [address2, setAddress2] = useState('');
  const [coords1, setCoords1] = useState<Coords | null>(null);
  const [coords2, setCoords2] = useState<Coords | null>(null);
  const [nearest1, setNearest1] = useState<any>(null);
  const [nearest2, setNearest2] = useState<any>(null);
  const [contour1, setContour1] = useState<ContourData | null>(null);
  const [contour2, setContour2] = useState<ContourData | null>(null);

  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [pinned, setPinned] = useState<PinnedTip | null>(null);
  const [mapKey, setMapKey] = useState(0);

  const geocodeAddress = async (address: string) => {
    const res = await axios.post('http://localhost:5000/api/geocode', { address });
    return { lat: String(res.data.lat), lng: String(res.data.lng) } as Coords;
  };

  const fetchNearestAndContour = async (lat: number, lng: number) => {
    const nRes = await axios.post('http://localhost:5000/api/nearest-station', { lat, lng });
    const nearest = nRes.data;
    const baseName = String(nearest?.name ?? '').trim();

    let contour: ContourData | null = null;
    for (const cand of normalizeStationNameCandidates(baseName)) {
      try {
        const cr = await axios.post('http://localhost:5000/api/contour-data', { station_name: cand });
        if (isValidContourData(cr?.data)) { contour = cr.data; break; }
      } catch {/* 다른 후보 시도 */}
    }
    return { nearest, contour };
  };

  const handleSearch = async () => {
    const a1 = address1.trim();
    const a2 = address2.trim();
    if (!a1 && !a2) return;

    setLoading(true);
    setErrorMessage(null);
    setPinned(null);

    try {
      if (a1 && a2) {
        // 다중 모드
        const [c1, c2] = await Promise.all([geocodeAddress(a1), geocodeAddress(a2)]);
        setCoords1(c1); setCoords2(c2);

        const [r1, r2] = await Promise.allSettled([
          fetchNearestAndContour(parseFloat(c1.lat), parseFloat(c1.lng)),
          fetchNearestAndContour(parseFloat(c2.lat), parseFloat(c2.lng)),
        ]);

        if (r1.status === 'fulfilled') {
          setNearest1(r1.value.nearest);
          setContour1(r1.value.contour ?? null);
        } else {
          setNearest1(null); setContour1(null);
        }

        if (r2.status === 'fulfilled') {
          setNearest2(r2.value.nearest);
          setContour2(r2.value.contour ?? null);
        } else {
          setNearest2(null); setContour2(null);
        }
      } else {
        // 단일 모드 (어느 입력이든 하나만 있으면 됨)
        const only = a1 || a2;
        const c = await geocodeAddress(only);
        const { nearest, contour } = await fetchNearestAndContour(parseFloat(c.lat), parseFloat(c.lng));

        // 단일 모드에선 1번 슬롯을 사용
        setCoords1(c); setCoords2(null);
        setNearest1(nearest); setNearest2(null);
        setContour1(contour ?? null); setContour2(null);
      }
    } catch {
      setErrorMessage('검색 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setAddress1(''); setAddress2('');
    setCoords1(null); setCoords2(null);
    setNearest1(null); setNearest2(null);
    setContour1(null); setContour2(null);
    setPinned(null);
    setErrorMessage(null);
    setMapKey(k => k + 1); // 맵 리마운트로 센터 초기화
  };

  // 클릭 시 핀 고정(단일/합계 분기)
  const handleMapClick = (lat: number, lng: number) => {
    const currentIsSumMode = Boolean(nearest1 && nearest2 && contour1 && contour2);

    if (currentIsSumMode) {
      const byName = new Map<string, Station>();
      [...collectStationsOnlyGeometry(contour1), ...collectStationsOnlyGeometry(contour2)]
        .forEach((s) => { if (!byName.has(s.name)) byName.set(s.name, s); });
      const geometry = Array.from(byName.values());
      const nearest = getNearestByGeometry(lat, lng, geometry);
      if (!nearest) return;

             const tmap1 = buildTimeMapByName(contour1);
       const tmap2 = buildTimeMapByName(contour2);
       const name = nearest.station.name;
       
       // 역명 정규화 (백엔드에서 이미 정규화된 역명을 반환하므로 단순화)
       const normalizeStationName = (name: string): string => {
         // 백엔드에서 이미 정규화된 역명을 반환하므로 추가 정규화 없이 그대로 사용
         return name.trim();
       };
       const normalizedName = normalizeStationName(name);
       const t1 = tmap1.get(normalizedName) ?? 60;
       const t2 = tmap2.get(normalizedName) ?? 60;
      const sum = Math.round(t1 + t2);

      setPinned({
        pos: { lat, lng },
        nearName: name,
        nearLatLng: { lat: nearest.station.lat, lng: nearest.station.lng },
        timeMin: sum,
        distanceKm: nearest.distanceKm,
      });
      return;
    }

    // 단일 모드
    const singleContour = contour1 ?? contour2;
    if (!singleContour) return;
    const stations = collectAllStations(singleContour);
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

  // 렌더 분기용 플래그/프록시
  const isSumMode = Boolean(nearest1 && nearest2 && contour1 && contour2);
  const singleCoords = coords1 ?? coords2;
  const singleNearest = nearest1 ?? nearest2;
  const singleContour = contour1 ?? contour2;
  
  // 디버깅: 합계 모드 상태 확인
  console.log('Sum mode debug:', {
    isSumMode,
    hasNearest1: !!nearest1,
    hasNearest2: !!nearest2,
    hasContour1: !!contour1,
    hasContour2: !!contour2,
    address1: address1.trim(),
    address2: address2.trim()
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* 헤더 */}
      <div style={{ padding: '15px', backgroundColor: '#f5f5f5', borderBottom: '1px solid #ddd', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ margin: 0 }}>서울 지하철 역간 접근성 지도</h1>
        </div>

        {/* 검색 UI */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            type="text"
            value={address1}
            onChange={(e) => setAddress1(e.target.value)}
            placeholder="첫 번째 주소를 입력해주세요(필수)"
            style={{ width: '280px', padding: '8px', fontSize: '14px' }}
          />
          <input
            type="text"
            value={address2}
            onChange={(e) => setAddress2(e.target.value)}
            placeholder="두 번째 주소를 입력해주세요(선택)"
            style={{ width: '280px', padding: '8px', fontSize: '14px' }}
          />
          <button
            onClick={handleSearch}
            disabled={loading || (!address1.trim() && !address2.trim())}
            style={{ padding: '8px 12px', fontSize: '14px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: loading ? 'not-allowed' : 'pointer' }}
          >
            {loading ? '검색 중…' : '검색하기'}
          </button>
          <button
            onClick={handleReset}
            style={{ padding: '8px 12px', fontSize: '14px', backgroundColor: '#6c757d', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            초기화
          </button>
        </div>

        {/* 검색 결과 정보 */}
        {(coords1 || coords2) && (
          <div style={{ padding: '10px', backgroundColor: '#e8f4f8', borderRadius: '5px', fontSize: '14px' }}>
            {coords1 && (
              <div style={{ marginBottom: coords2 ? '10px' : '0' }}>
                <strong>📍 주소1:</strong> {address1}
                {nearest1 && (
                  <div style={{ marginTop: '5px', fontSize: '12px', color: '#28a745' }}>
                    🚇 인근 지하철역: {nearest1.name} (거리: {((nearest1 as any).distance_km ?? (nearest1 as any).distance) ?? '—'} km)
                  </div>
                )}
              </div>
            )}
            {coords2 && (
              <div>
                <strong>📍 주소2:</strong> {address2}
                {nearest2 && (
                  <div style={{ marginTop: '5px', fontSize: '12px', color: '#28a745' }}>
                    🚇 인근 지하철역: {nearest2.name} (거리: {((nearest2 as any).distance_km ?? (nearest2 as any).distance) ?? '—'} km)
                  </div>
                )}
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
          key={mapKey}
          center={singleCoords ? [parseFloat(singleCoords.lat), parseFloat(singleCoords.lng)] : [37.5665, 126.978]}
          zoom={13}
          style={{ flex: 1, width: '100%', border: '1px solid #ddd', borderRadius: '8px' }}
        >
          <TileLayer
            attribution="&copy; OpenStreetMap"
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {/* 센터/뷰 업데이트 */}
          {coords1 && coords2
            ? <FitBoundsToOrigins coords1={coords1} coords2={coords2} />
            : (singleCoords && <MapCenterUpdater coords={singleCoords} />)
          }

          {/* 주소 마커 */}
          {coords1 && (
            <Marker position={[parseFloat(coords1.lat), parseFloat(coords1.lng)]} icon={getSelectedLocationIcon1()}>
              <Popup><strong>📍 주소1</strong><br />{address1}</Popup>
            </Marker>
          )}
          {coords2 && (
            <Marker position={[parseFloat(coords2.lat), parseFloat(coords2.lng)]} icon={getSelectedLocationIcon2()}>
              <Popup><strong>📍 주소2</strong><br />{address2}</Popup>
            </Marker>
          )}

          {/* 최근접역 마커 */}
          {nearest1 && (
            <Marker position={[Number(nearest1.lat), Number(nearest1.lng)]} icon={getNearestStationIcon1()}>
              <Popup><strong>🚇 최근접역(주소1)</strong><br />{nearest1.name}</Popup>
            </Marker>
          )}
          {nearest2 && (
            <Marker position={[Number(nearest2.lat), Number(nearest2.lng)]} icon={getNearestStationIcon2()}>
              <Popup><strong>🚇 최근접역(주소2)</strong><br />{nearest2.name}</Popup>
            </Marker>
          )}

          {/* 컬러 레이어 & 커서 툴팁 */}
          {isSumMode ? (
            <>
              <UnifiedColorContoursSum contour1={contour1} contour2={contour2} />
              <CursorFollowerTooltipSum
                contour1={contour1}
                contour2={contour2}
                origin1Name={nearest1?.name}
                origin2Name={nearest2?.name}
                disabled={!!pinned}
              />
            </>
          ) : (
            singleNearest && singleContour && (
              <>
                <UnifiedColorContours contourData={singleContour} nearestStation={singleNearest} />
                <CursorFollowerTooltip
                  contourData={singleContour}
                  originStationName={singleNearest?.name}
                  disabled={!!pinned}
                />
              </>
            )
          )}

          {/* 핀 고정 툴팁 */}
          {pinned && (
            <PinnedTooltip
              pinned={pinned}
              originCoords={isSumMode ? null : singleCoords}
              originStationName={isSumMode ? undefined : singleNearest?.name}
              onClose={() => setPinned(null)}
            />
          )}

          {/* 범례 */}
          <Legend isSumMode={isSumMode} />

          {/* 클릭 처리 */}
          <ClickableMap onClickMap={handleMapClick} />
        </MapContainer>
      </div>
    </div>
  );
}

export default App;
