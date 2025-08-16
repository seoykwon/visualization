// frontend/src/api.ts
import axios from "axios";

const BASE = "http://localhost:5000";

export async function fetchIsochrone(lat: number, lng: number, thresholds = [15,30,45,60]) {
  const { data } = await axios.post(`${BASE}/api/isochrone`, { lat, lng, thresholds });
  return data; // GeoJSON FeatureCollection
}
