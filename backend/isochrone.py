# backend/isochrone.py
from shapely.geometry import Point, Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely import speedups
import math

if speedups.available:
    speedups.enable()

def polygons_from_station_times(
    station_times: dict,
    station_pos: dict,
    thresholds=(20, 40, 60, 80, 100),
    buffer_m_per_station=300
):
    """
    station_times: {역명: 분}
    station_pos  : {역명: (lat,lng)}
    thresholds   : 20분 단위 등고선
    buffer_m_per_station: 역 주변 '역세권' 반경(m). 네트워크 도달 가능역들을
                          합집합으로 부드럽게 만드는 용도(기본 300m).
    """
    # 위경도 → 근사 평면 좌표(서울 중심 근사)
    lat0, lng0 = 37.5665, 126.9780
    def to_xy(lat, lng):
        mx = (lng - lng0) * 111_000 * abs(math.cos(math.radians(lat0)))
        my = (lat - lat0) * 111_000
        return mx, my

    def to_lonlat(mx, my):
        lng = lng0 + mx / (111_000 * abs(math.cos(math.radians(lat0))))
        lat = lat0 + my / 111_000
        return lng, lat

    result = {}
    for T in thresholds:
        polys = []
        for name, minutes in station_times.items():
            if minutes <= T and name in station_pos:
                lat, lng = station_pos[name]
                mx, my = to_xy(lat, lng)
                polys.append(Point(mx, my).buffer(buffer_m_per_station))
        if not polys:
            result[T] = None
            continue
        merged = unary_union(polys)

        def poly_to_geojson(p):
            if p.is_empty:
                return None
            if isinstance(p, Polygon):
                ring = [[*to_lonlat(x, y)] for x, y in p.exterior.coords]
                return {"type": "Polygon", "coordinates": [ring]}
            if isinstance(p, MultiPolygon):
                mp = []
                for geom in p.geoms:
                    ring = [[*to_lonlat(x, y)] for x, y in geom.exterior.coords]
                    mp.append([ring])
                return {"type": "MultiPolygon", "coordinates": mp}
            return None

        result[T] = poly_to_geojson(merged)
    return result

def build_featurecollection(bands_geojson: dict):
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"minutes": T}, "geometry": geom}
            for T, geom in bands_geojson.items() if geom
        ],
    }
