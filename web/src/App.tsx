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

      {/* Main content — offset for fixed sidebar */}
      <div className="flex-1 flex flex-col ml-56 min-h-screen">
        <Header
          date={date}
          onDateChange={setDate}
          apiOk={apiOk}
          lastUpdate={lastUpdate}
          anomalyCount={anomalyCount}
          onNavigate={setPage}
        />

        <main className="flex-1 overflow-y-auto px-6 py-6 flex flex-col gap-6">
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
    </div>
  )
}
