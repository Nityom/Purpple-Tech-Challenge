import { useState, useEffect, useCallback } from 'react'
import {
  fetchMetrics, fetchFunnel, fetchHeatmap,
  fetchAnomalies, fetchCameras, fetchPOS, fetchHealth,
  type MetricsResponse, type FunnelResponse, type HeatmapResponse,
  type AnomaliesResponse, type CameraStatsResponse, type POSAnalyticsResponse,
} from './api'
import Sidebar, { type NavPage } from './components/Sidebar'
import Header      from './components/Header'
import KPIGrid     from './components/KPIGrid'
import CameraGrid  from './components/CameraGrid'
import FunnelChart from './components/FunnelChart'
import HeatmapGrid from './components/HeatmapGrid'
import AnomalyList from './components/AnomalyList'
import POSPanel    from './components/POSPanel'

const STORE_ID     = 'STORE_BLR_001'
const DEFAULT_DATE = '2026-04-10'
const POLL_MS      = 10_000

const PAGE_TITLES: Record<NavPage, string> = {
  dashboard: 'Dashboard',
  cameras:   'Camera Breakdown',
  analytics: 'Store Analytics',
  pos:       'POS Sales',
  anomalies: 'Anomalies',
}
const PAGE_SUB: Record<NavPage, string> = {
  dashboard: 'Plan, monitor, and act on your store data.',
  cameras:   'Live feed summary for all 5 cameras.',
  analytics: 'Funnel and zone heatmap analysis.',
  pos:       'Point of Sale data from CSV.',
  anomalies: 'Operational alerts detected by the system.',
}

const MOBILE_NAV: { id: NavPage; label: string; d: string }[] = [
  { id: 'dashboard', label: 'Home',      d: 'M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z' },
  { id: 'cameras',   label: 'Cameras',   d: 'M15 10l4.553-2.277A1 1 0 0121 8.723v6.554a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z' },
  { id: 'analytics', label: 'Analytics', d: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { id: 'pos',       label: 'POS',       d: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
  { id: 'anomalies', label: 'Alerts',    d: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z' },
]

export default function App() {
  const [page, setPage]           = useState<NavPage>('dashboard')
  const [date, setDate]           = useState(DEFAULT_DATE)
  const [apiOk, setApiOk]         = useState(false)
  const [metrics,   setMetrics]   = useState<MetricsResponse    | null>(null)
  const [funnel,    setFunnel]    = useState<FunnelResponse      | null>(null)
  const [heatmap,   setHeatmap]   = useState<HeatmapResponse     | null>(null)
  const [anomalies, setAnomalies] = useState<AnomaliesResponse   | null>(null)
  const [cameras,   setCameras]   = useState<CameraStatsResponse | null>(null)
  const [pos,       setPOS]       = useState<POSAnalyticsResponse | null>(null)
  const [lastUpdate, setLastUpdate] = useState<string>('')

  const loadAll = useCallback(async () => {
    try { const h = await fetchHealth(); setApiOk(h.status === 'ok') } catch { setApiOk(false) }
    const results = await Promise.allSettled([
      fetchMetrics(STORE_ID, date),
      fetchFunnel(STORE_ID, date),
      fetchHeatmap(STORE_ID, date),
      fetchAnomalies(STORE_ID),
      fetchCameras(STORE_ID, date),
      fetchPOS(STORE_ID, date),
    ])
    if (results[0].status === 'fulfilled') setMetrics(results[0].value)
    if (results[1].status === 'fulfilled') setFunnel(results[1].value)
    if (results[2].status === 'fulfilled') setHeatmap(results[2].value)
    if (results[3].status === 'fulfilled') setAnomalies(results[3].value)
    if (results[4].status === 'fulfilled') setCameras(results[4].value)
    if (results[5].status === 'fulfilled') setPOS(results[5].value)
    setLastUpdate(new Date().toLocaleTimeString())
  }, [date])

  useEffect(() => { loadAll() }, [loadAll])
  useEffect(() => {
    const id = setInterval(loadAll, POLL_MS)
    return () => clearInterval(id)
  }, [loadAll])

  const anomalyCount = anomalies?.anomalies.length ?? 0

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar activePage={page} onNavigate={setPage} anomalyCount={anomalyCount} />

      {/* Main content — offset for fixed sidebar (desktop only) */}
      <div className="flex-1 flex flex-col md:ml-56 min-h-screen">
        <Header
          date={date}
          onDateChange={setDate}
          apiOk={apiOk}
          lastUpdate={lastUpdate}
          anomalyCount={anomalyCount}
          onNavigate={setPage}
        />

        <main className="flex-1 overflow-y-auto px-4 md:px-6 py-4 md:py-6 pb-20 md:pb-6 flex flex-col gap-6">
          {/* Page heading */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{PAGE_TITLES[page]}</h1>
              <p className="text-sm text-gray-400 mt-0.5">{PAGE_SUB[page]}</p>
            </div>

          </div>

          {/* Dashboard page */}
          {page === 'dashboard' && (
            <>
              <KPIGrid metrics={metrics} pos={pos} onNavigate={setPage} />
              <section>
                <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Camera Feeds</p>
                <CameraGrid data={cameras} />
              </section>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <FunnelChart data={funnel} />
                <HeatmapGrid data={heatmap} />
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <POSPanel data={pos} />
                <AnomalyList data={anomalies} />
              </div>
            </>
          )}

          {/* Cameras page */}
          {page === 'cameras' && (
            <>
              <KPIGrid metrics={metrics} pos={pos} onNavigate={setPage} />
              <CameraGrid data={cameras} />
            </>
          )}

          {/* Analytics page */}
          {page === 'analytics' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <FunnelChart data={funnel} />
              <HeatmapGrid data={heatmap} />
            </div>
          )}

          {/* POS page */}
          {page === 'pos' && (
            <div className="max-w-3xl">
              <POSPanel data={pos} />
            </div>
          )}

          {/* Anomalies page */}
          {page === 'anomalies' && (
            <div className="max-w-2xl">
              <AnomalyList data={anomalies} />
            </div>
          )}
        </main>
      </div>

      {/* Mobile bottom navigation — hidden on md+ */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 bg-white border-t border-gray-100 flex md:hidden">
        {MOBILE_NAV.map(item => (
          <button
            key={item.id}
            onClick={() => setPage(item.id)}
            className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 relative transition-colors ${
              page === item.id ? 'text-green-700' : 'text-gray-400'
            }`}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d={item.d} />
            </svg>
            <span className="text-[10px] font-medium">{item.label}</span>
            {item.id === 'anomalies' && anomalyCount > 0 && (
              <span className="absolute top-1 right-[calc(50%-14px)] w-3.5 h-3.5 bg-red-500 text-white text-[8px] font-bold rounded-full flex items-center justify-center">
                {anomalyCount > 9 ? '9+' : anomalyCount}
              </span>
            )}
          </button>
        ))}
      </nav>
    </div>
  )
}
