import type { FC } from 'react'
import type { MetricsResponse, POSAnalyticsResponse } from '../api'
import type { NavPage } from './Sidebar'

interface Props {
  metrics: MetricsResponse | null
  pos: POSAnalyticsResponse | null
  onNavigate: (page: NavPage) => void
}

const fmt    = (n: number) => n.toLocaleString('en-IN')
const fmtCur = (n: number) => `\u20b9${fmt(Math.round(n))}`
const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`

const Arrow = ({ onClick, title }: { onClick: () => void; title: string }) => (
  <button
    onClick={onClick}
    title={title}
    className="w-7 h-7 rounded-full border border-gray-200 flex items-center justify-center text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-all shrink-0"
  >
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 17L17 7M17 7H7M17 7v10" />
    </svg>
  </button>
)

const KPIGrid: FC<Props> = ({ metrics, pos, onNavigate }) => {
  if (!metrics && !pos) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-2xl bg-white border border-gray-100 shadow-sm h-32 animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">

      {/* Accent card */}
      <div className="rounded-2xl p-5 bg-green-50 border border-green-200 relative overflow-hidden">
        <div className="absolute -bottom-4 -right-4 w-24 h-24 bg-green-100 rounded-full" />
        <div className="flex justify-between items-start mb-4 relative">
          <p className="text-sm font-medium text-green-700">Unique Visitors</p>
          <Arrow onClick={() => onNavigate('cameras')} title="View camera breakdown" />
        </div>
        <p className="text-3xl sm:text-4xl font-bold mb-1 relative text-green-900">{metrics ? fmt(metrics.unique_visitors) : '—'}</p>
        <div className="flex items-center gap-1.5 text-xs text-green-600 relative">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M15 10l4.553-2.277A1 1 0 0121 8.723v6.554a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
          <span>CCTV tracking · 5 cameras</span>
        </div>
      </div>

      {/* White cards */}
      {([
        {
          label: 'Conversion Rate',
          value: metrics ? fmtPct(metrics.conversion_rate) : '—',
          sub: 'visitors → purchase',
          page: 'analytics' as NavPage,
          title: 'View analytics',
        },
        {
          label: 'Queue Depth',
          value: metrics ? fmt(metrics.current_queue_depth) : '—',
          sub: metrics ? `abandonment ${fmtPct(metrics.abandonment_rate)}` : '—',
          page: 'analytics' as NavPage,
          title: 'View analytics',
        },
        {
          label: 'Revenue (POS)',
          value: pos ? fmtCur(pos.total_revenue) : '—',
          sub: pos ? `${pos.total_transactions} txns · avg ${fmtCur(pos.avg_basket_inr)}` : 'from CSV',
          page: 'pos' as NavPage,
          title: 'View POS details',
        },
      ] as { label: string; value: string; sub: string; page: NavPage; title: string }[]).map(card => (
        <div key={card.label} className="rounded-2xl p-5 bg-white border border-gray-100 shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <p className="text-sm font-medium text-gray-500">{card.label}</p>
            <Arrow onClick={() => onNavigate(card.page)} title={card.title} />
          </div>
          <p className="text-3xl sm:text-4xl font-bold text-gray-900 mb-1">{card.value}</p>
          <p className="text-xs text-gray-400">{card.sub}</p>
        </div>
      ))}
    </div>
  )
}

export default KPIGrid
