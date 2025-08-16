// frontend/src/components/IsochroneMap.tsx
import React, { useEffect, useState } from "react";
import {
  MapContainer, TileLayer, useMapEvents, Marker, Popup, GeoJSON
} from "react-leaflet";
import { fetchIsochrone } from "../api";
import L, { LeafletMouseEvent } from "leaflet";

type FC = GeoJSON.FeatureCollection;

function ClickCatcher({ onClick }: { onClick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e: LeafletMouseEvent) {
      onClick(e.latlng.lat, e.latlng.lng);
    }
  });
  return null;
}

export default function IsochroneMap() {
  const [center] = useState<[number,number]>([37.5665, 126.9780]);
  const [iso, setIso] = useState<FC | null>(null);
  const [clicked, setClicked] = useState<[number,number] | null>(null);

  // 밴드별 스타일 (15/30/45/60)
  const styleByMin = (min: number) => {
    if (min <= 15) return { fillOpacity: 0.25, weight: 1, color: "#2ecc71", fillColor: "#2ecc71" };
    if (min <= 30) return { fillOpacity: 0.20, weight: 1, color: "#f1c40f", fillColor: "#f1c40f" };
    if (min <= 45) return { fillOpacity: 0.18, weight: 1, color: "#e67e22", fillColor: "#e67e22" };
    return            { fillOpacity: 0.16, weight: 1, color: "#e74c3c", fillColor: "#e74c3c" };
  };

  return (
    <div style={{height: 520}}>
      <MapContainer center={center} zoom={11} style={{ height: "100%" }}>
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'
        />
        <ClickCatcher
          onClick={async (lat, lng) => {
            setClicked([lat, lng]);
            const fc = await fetchIsochrone(lat, lng);
            setIso(fc);
          }}
        />
        {clicked && (
          <Marker position={clicked}>
            <Popup>clicked: {clicked[0].toFixed(5)}, {clicked[1].toFixed(5)}</Popup>
          </Marker>
        )}
        {iso && (
          <GeoJSON
            key={JSON.stringify(iso)} // 클릭 때마다 새로 그리기
            data={iso as any}
            style={(feature) => {
              const m = feature?.properties?.minutes ?? 60;
              return styleByMin(m);
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}
