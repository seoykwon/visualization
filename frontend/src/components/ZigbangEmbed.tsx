import React, { useEffect, useRef, useState } from "react";

interface ZigbangEmbedProps {
  stationName?: string;
}

export default function ZigbangEmbed({ stationName }: ZigbangEmbedProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentSearch, setCurrentSearch] = useState<string>('');
  const [selectedSite, setSelectedSite] = useState<string>('zigbang');

  // 🏠 iframe 가능한 부동산 사이트들
  const getSiteUrl = (site: string, searchTerm: string) => {
    const cleanedTerm = searchTerm.replace(/역$/, '');
    const encodedTerm = encodeURIComponent(cleanedTerm);
    
    switch(site) {
      case 'zigbang':
        return searchTerm ? 
          `https://www.zigbang.com/search?q=${encodedTerm}` : 
          'https://www.zigbang.com';
          
      case 'dabang':
        return searchTerm ? 
          `https://www.dabangapp.com/search?keyword=${encodedTerm}` : 
          'https://www.dabangapp.com';
          
      case 'hogangnono':
        return searchTerm ? 
          `https://hogangnono.com/map?keyword=${encodedTerm}` : 
          'https://hogangnono.com';
          
      case 'peterpan':
        return searchTerm ? 
          `https://www.peterpanz.com/search?keyword=${encodedTerm}` : 
          'https://www.peterpanz.com';
          
      case 'realtor':
        return searchTerm ? 
          `https://m.realtor.com/realestateandhomes-search/${encodedTerm}` :
          'https://m.realtor.com';

      case 'naver_proxy':
        // 프록시를 통한 네이버 접근 (실제 서비스 시 백엔드 필요)
        return searchTerm ?
          `http://localhost:5000/api/proxy/naver?search=${encodedTerm}` :
          `http://localhost:5000/api/proxy/naver`;
          
      default:
        return 'https://www.zigbang.com';
    }
  };

  // 🔍 검색어 업데이트
  useEffect(() => {
    if (stationName && stationName !== currentSearch) {
      console.log(`🏠 ${selectedSite}에서 "${stationName}" 검색 시작`);
      setCurrentSearch(stationName);
      updateIframe(selectedSite, stationName);
    }
  }, [stationName]);

  useEffect(() => {
    if (currentSearch) {
      updateIframe(selectedSite, currentSearch);
    } else {
      updateIframe(selectedSite, '');
    }
  }, [selectedSite]);

  const updateIframe = (site: string, searchTerm: string) => {
    if (iframeRef.current) {
      setIsLoading(true);
      const url = getSiteUrl(site, searchTerm);
      console.log(`📱 ${site} URL: ${url}`);
      
      // iframe src 변경
      iframeRef.current.src = url;
      
      // User-Agent 설정 시도 (제한적)
      try {
        // 모바일 User-Agent로 접근 시도
        const iframe = iframeRef.current;
        iframe.onload = () => {
          setIsLoading(false);
          console.log(`✅ ${site} 로드 완료`);
        };
        iframe.onerror = () => {
          setIsLoading(false);
          console.log(`❌ ${site} 로드 실패`);
        };
      } catch (error) {
        console.log('iframe 설정 중 오류:', error);
        setIsLoading(false);
      }
    }
  };

  const handleSiteChange = (site: string) => {
    console.log(`🔄 사이트 변경: ${site}`);
    setSelectedSite(site);
  };

  const handleManualSearch = () => {
    const searchTerm = prompt('검색할 지역을 입력하세요:', currentSearch || '');
    if (searchTerm) {
      setCurrentSearch(searchTerm);
      updateIframe(selectedSite, searchTerm);
    }
  };

  const handleRefresh = () => {
    console.log('🔄 새로고침');
    updateIframe(selectedSite, currentSearch);
  };

  const handleNewWindow = () => {
    const url = getSiteUrl(selectedSite, currentSearch);
    window.open(url, '_blank');
  };

  // iframe 직접 지원 사이트들
  const sites = [
    { id: 'zigbang', name: '직방', color: '#e74c3c' },
    { id: 'dabang', name: '다방', color: '#f39c12' },
    { id: 'hogangnono', name: '호갱노노', color: '#9b59b6' },
    { id: 'peterpan', name: '피터팬', color: '#1abc9c' },
    { id: 'realtor', name: 'Realtor.com', color: '#34495e' },
    { id: 'naver_proxy', name: '네이버(프록시)', color: '#27ae60' }
  ];

  return (
    <div style={{ width: "100%", height: "100%", display: 'flex', flexDirection: 'column' }}>
      {/* 🎛️ 컨트롤 패널 */}
      <div style={{
        padding: '10px',
        backgroundColor: '#f8f9fa',
        borderBottom: '1px solid #dee2e6',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px'
      }}>
        {/* 사이트 선택 버튼들 */}
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {sites.map(site => (
            <button
              key={site.id}
              onClick={() => handleSiteChange(site.id)}
              style={{
                padding: '5px 10px',
                fontSize: '10px',
                backgroundColor: selectedSite === site.id ? site.color : '#f8f9fa',
                color: selectedSite === site.id ? 'white' : '#495057',
                border: selectedSite === site.id ? 'none' : '1px solid #dee2e6',
                borderRadius: '3px',
                cursor: 'pointer',
                fontWeight: selectedSite === site.id ? 'bold' : 'normal'
              }}
            >
              {site.name}
            </button>
          ))}
        </div>

        {/* 상태 및 컨트롤 */}
        <div style={{ display: 'flex', alignItems: 'center', fontSize: '12px' }}>
          <div style={{ flex: 1, color: '#495057' }}>
            {currentSearch ? (
              <span>🏠 <strong>{currentSearch}</strong> 검색 중 ({sites.find(s => s.id === selectedSite)?.name})</span>
            ) : (
              <span>🏠 {sites.find(s => s.id === selectedSite)?.name} 홈페이지</span>
            )}
            {isLoading && <span style={{ marginLeft: '8px', color: '#6c757d' }}>🔄</span>}
          </div>
          
          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              onClick={handleManualSearch}
              style={{
                padding: '4px 8px',
                fontSize: '10px',
                backgroundColor: '#007bff',
                color: 'white',
                border: 'none',
                borderRadius: '3px',
                cursor: 'pointer'
              }}
            >
              🔍
            </button>
            
            <button
              onClick={handleRefresh}
              style={{
                padding: '4px 8px',
                fontSize: '10px',
                backgroundColor: '#28a745',
                color: 'white',
                border: 'none',
                borderRadius: '3px',
                cursor: 'pointer'
              }}
            >
              🔄
            </button>
            
            <button
              onClick={handleNewWindow}
              style={{
                padding: '4px 8px',
                fontSize: '10px',
                backgroundColor: '#17a2b8',
                color: 'white',
                border: 'none',
                borderRadius: '3px',
                cursor: 'pointer'
              }}
            >
              🔗
            </button>
          </div>
        </div>
      </div>

      {/* 📱 iframe */}
      <div style={{ flex: 1, position: 'relative', backgroundColor: '#fff' }}>
        {isLoading && (
          <div style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            zIndex: 10,
            padding: '8px 12px',
            backgroundColor: 'rgba(0, 123, 255, 0.9)',
            color: 'white',
            borderRadius: '4px',
            fontSize: '12px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
          }}>
            🔄 로딩중... {currentSearch && `"${currentSearch}"`}
          </div>
        )}
        
        <iframe
          ref={iframeRef}
          src="https://www.zigbang.com/"
          title="부동산 검색"
          style={{
            width: "100%",
            height: "100%",
            border: "none",
            backgroundColor: '#fff'
          }}
          // 추가적인 iframe 속성들
          sandbox="allow-same-origin allow-scripts allow-popups allow-forms allow-top-navigation"
          loading="lazy"
          referrerPolicy="no-referrer-when-downgrade"
          onLoad={() => {
            setIsLoading(false);
            console.log(`✅ ${selectedSite} 페이지 로드 완료`);
          }}
          onError={() => {
            setIsLoading(false);
            console.log(`❌ ${selectedSite} 페이지 로드 실패`);
          }}
        />
      </div>

      {/* 💡 도움말 */}
      {selectedSite === 'naver_proxy' && (
        <div style={{
          position: 'absolute',
          bottom: '10px',
          left: '10px',
          right: '10px',
          padding: '8px',
          backgroundColor: 'rgba(255, 235, 59, 0.9)',
          fontSize: '11px',
          borderRadius: '4px',
          color: '#333'
        }}>
          💡 네이버(프록시): 백엔드 프록시 서버가 필요합니다.
        </div>
      )}
    </div>
  );
}