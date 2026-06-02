import { useState, useEffect, useCallback } from 'react'
import {
  fetchMetrics, fetchFunnel, fetchHeatmap,
  fetchCameras, fetchPOS, fetchHealth, fetchStoreConfig,
  type MetricsResponse, type FunnelResponse, type HeatmapResponse,
  type CameraStatsResponse, type POSAnalyticsResponse,
  type StoreConfig,
} from './api'
import Sidebar, { type NavPage, STORES } from './components/Sidebar'
import Header          from './components/Header'
import KPIGrid         from './components/KPIGrid'
import CameraGrid      from './components/CameraGrid'
import FunnelChart     from './components/FunnelChart'
import HeatmapGrid     from './components/HeatmapGrid'
import POSPanel        from './components/POSPanel'
import StoreLayoutMap  from './components/StoreLayoutMap'

const DEFAULT_DATE = '2026-04-10'
const POLL_MS      = 10_000

const PAGE_TITLES: Record<NavPage, string> = {
  dashboard: 'Dashboard',
  cameras:   'Camera Breakdown',
  analytics: 'Store Analytics',
  pos:       'POS Sales',
}
const PAGE_SUB: Record<NavPage, string> = {
  dashboard: 'Plan, monitor, and act on your store data.',
  cameras:   'Live feed summary across all cameras.',
  analytics: 'Funnel, zone heatmap and floor plan.',
  pos:       'Point of Sale data from CSV.',
}

const MOBILE_NAV: { id: NavPage; label: string; d: string }[] = [
  { id: 'dashboard', label: 'Home',      d: 'M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z' },
  { id: 'cameras',   label: 'Cameras',   d: 'M15 10l4.553-2.277A1 1 0 0121 8.723v6.554a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z' },
  { id: 'analytics', label: 'Analytics', d: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
  { id: 'pos',       label: 'POS',       d: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01' },
]

export default function App() {
  const [page, setPage]           = useState<NavPage>('dashboard')
  const [date, setDate]           = useState(DEFAULT_DATE)
  const [storeId, setStoreId]       = useState(STORES[0].id)
  const [storeConfig, setStoreConfig] = useState<StoreConfig | null>(null)
  const [apiOk, setApiOk]           = useState(false)
  const [metrics,   setMetrics]   = useState<MetricsResponse    | null>(null)
  const [funnel,    setFunnel]    = useState<FunnelResponse      | null>(null)
  const [heatmap,   setHeatmap]   = useState<HeatmapResponse     | null>(null)
  const [cameras,   setCameras]   = useState<CameraStatsResponse | null>(null)
  const [pos,       setPOS]       = useState<POSAnalyticsResponse | null>(null)
  const [lastUpdate, setLastUpdate] = useState<string>('')

  const loadAll = useCallback(async () => {
    try { const h = await fetchHealth(); setApiOk(h.status === 'ok') } catch { setApiOk(false) }
    const results = await Promise.allSettled([
      fetchMetrics(storeId, date),
      fetchFunnel(storeId, date),
      fetchHeatmap(storeId, date),
      fetchCameras(storeId, date),
      fetchPOS(storeId, date),
    ])
    if (results[0].status === 'fulfilled') setMetrics(results[0].value)
    if (results[1].status === 'fulfilled') setFunnel(results[1].value)
    if (results[2].status === 'fulfilled') setHeatmap(results[2].value)
    if (results[3].status === 'fulfilled') setCameras(results[3].value)
    if (results[4].status === 'fulfilled') setPOS(results[4].value)
    setLastUpdate(new Date().toLocaleTimeString())
  }, [date, storeId])

  // Load store config whenever store changes
  useEffect(() => {
    fetchStoreConfig(storeId).then(setStoreConfig).catch(() => setStoreConfig(null))
  }, [storeId])

  useEffect(() => { loadAll() }, [loadAll])
  useEffect(() => {
    const id = setInterval(loadAll, POLL_MS)
    return () => clearInterval(id)
  }, [loadAll])

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        activePage={page}
        onNavigate={setPage}
        storeId={storeId}
        onStoreChange={(id) => { setStoreId(id); setMetrics(null); setFunnel(null); setHeatmap(null); setCameras(null); setPOS(null) }}
      />

      {/* Main content — offset for fixed sidebar (desktop only) */}
      <div className="flex-1 flex flex-col md:ml-56 min-h-screen">
        <Header
          date={date}
          onDateChange={setDate}
          apiOk={apiOk}
          lastUpdate={lastUpdate}
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
                <CameraGrid data={cameras} storeConfig={storeConfig} />
              </section>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <FunnelChart data={funnel} />
                <HeatmapGrid data={heatmap} storeConfig={storeConfig} />
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <POSPanel data={pos} storeName={STORES.find(s => s.id === storeId)?.name} />
              </div>
            </>
          )}

          {/* Cameras page */}
          {page === 'cameras' && (
            <>
              <KPIGrid metrics={metrics} pos={pos} onNavigate={setPage} />
              <CameraGrid data={cameras} storeConfig={storeConfig} />
            </>
          )}

          {/* Analytics page */}
          {page === 'analytics' && (
            <div className="flex flex-col gap-4">
              <StoreLayoutMap storeId={storeId} heatmap={heatmap} />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <FunnelChart data={funnel} />
                <HeatmapGrid data={heatmap} storeConfig={storeConfig} />
              </div>
            </div>
          )}

          {/* POS page */}
          {page === 'pos' && (
            <div className="max-w-3xl">
              <POSPanel data={pos} storeName={STORES.find(s => s.id === storeId)?.name} />
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
          </button>
        ))}
      </nav>
    </div>
  )
}
