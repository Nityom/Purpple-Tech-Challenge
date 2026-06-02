// api.ts — typed fetch wrapper for the Store Intelligence API

const BASE = '/api'

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`)
  return res.json() as Promise<T>
}

// ── Types ─────────────────────────────────────────────────────────────────

export interface ZoneDwellMetric {
  zone_id: string
  avg_dwell_ms: number
  visit_count: number
}

export interface MetricsResponse {
  store_id: string
  date: string
  unique_visitors: number
  conversion_rate: number
  avg_dwell_ms_by_zone: ZoneDwellMetric[]
  current_queue_depth: number
  abandonment_rate: number
  data_confidence: boolean
}

export interface FunnelStage {
  stage: string
  count: number
  drop_off_pct: number
}

export interface FunnelResponse {
  store_id: string
  date: string
  stages: FunnelStage[]
  total_sessions: number
}

export interface HeatmapZone {
  zone_id: string
  visit_frequency: number
  avg_dwell_ms: number
  normalised_score: number
}

export interface HeatmapResponse {
  store_id: string
  date: string
  zones: HeatmapZone[]
  data_confidence: boolean
}

export interface Anomaly {
  anomaly_id: string
  anomaly_type: string
  severity: 'INFO' | 'WARN' | 'CRITICAL'
  description: string
  suggested_action: string
  detected_at: string
  store_id: string
  metadata: Record<string, unknown>
}

export interface AnomaliesResponse {
  store_id: string
  checked_at: string
  anomalies: Anomaly[]
}

export interface CameraStat {
  camera_id: string
  total_events: number
  unique_visitors: number
  entries: number
  exits: number
  reentries: number
  zone_events: number
  staff_events: number
  first_event_at: string | null
  last_event_at: string | null
}

export interface CameraStatsResponse {
  store_id: string
  date: string
  cameras: CameraStat[]
}

export interface POSHourly {
  hour: number
  transactions: number
  revenue: number
}

export interface POSProduct {
  product_name: string
  brand: string
  qty_sold: number
  revenue: number
}

export interface POSCategory {
  category: string
  sub_category: string
  qty_sold: number
  revenue: number
}

export interface POSAnalyticsResponse {
  store_id: string
  date: string
  total_transactions: number
  total_revenue: number
  avg_basket_inr: number
  hourly: POSHourly[]
  top_products: POSProduct[]
  top_categories: POSCategory[]
}

export interface StoreCameraConfig {
  description: string
  type: string
  zones_covered: string[]
}

export interface StoreConfig {
  store_id: string
  store_name: string
  address: string
  cameras: Record<string, StoreCameraConfig>
  zones: Record<string, string>
}

export interface HealthResponse {
  status: string
  checked_at: string
  database: string
  stores: { store_id: string; last_event_at: string | null; events_last_hour: number; stale_feed: boolean }[]
}

// ── Fetchers ──────────────────────────────────────────────────────────────

export const fetchMetrics     = (id: string, date: string) => apiFetch<MetricsResponse>(`/stores/${id}/metrics?date=${date}`)
export const fetchFunnel      = (id: string, date: string) => apiFetch<FunnelResponse>(`/stores/${id}/funnel?date=${date}`)
export const fetchHeatmap     = (id: string, date: string) => apiFetch<HeatmapResponse>(`/stores/${id}/heatmap?date=${date}`)
export const fetchAnomalies   = (id: string)               => apiFetch<AnomaliesResponse>(`/stores/${id}/anomalies`)
export const fetchCameras     = (id: string, date: string) => apiFetch<CameraStatsResponse>(`/stores/${id}/cameras?date=${date}`)
export const fetchPOS         = (id: string, date: string) => apiFetch<POSAnalyticsResponse>(`/stores/${id}/pos?date=${date}`)
export const fetchHealth      = ()                          => apiFetch<HealthResponse>('/health')
export const fetchStoreConfig = (id: string)               => apiFetch<StoreConfig>(`/stores/${id}/config`)
