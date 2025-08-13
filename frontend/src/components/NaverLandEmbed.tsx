import React from 'react';

interface NaverLandEmbedProps {
  lat: number;
  lng: number;
  zoom?: number;
}

export default function NaverLandEmbed({ lat, lng, zoom = 16 }: NaverLandEmbedProps) {
  const openNaverLand = () => {
    const url = `https://new.land.naver.com/complexes?ms=${lat},${lng},${zoom}&a=APT:ABYG:JGC:PRE&e=RETAIL`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <button
      onClick={openNaverLand}
      style={{
        padding: '12px 24px',
        backgroundColor: '#03c75a',
        color: 'white',
        border: 'none',
        borderRadius: '8px',
        fontSize: '16px',
        cursor: 'pointer',
      }}
    >
      네이버 부동산 새 탭으로 열기
    </button>
  );
}
