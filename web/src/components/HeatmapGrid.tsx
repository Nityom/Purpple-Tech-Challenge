import type { FC } from 'react'
import type { HeatmapResponse } from '../api'

const ZONE_BG: Record<string, string> = {
  ENTRY:         'bg-blue-500',
  MAKEUP:        'bg-pink-500',
  SKINCARE:      'bg-purple-500',
  BATH_BODY:     'bg-teal-500',
  BILLING:       'bg-amber-500',
  BILLING_QUEUE: 'bg-orange-500',
}

const ZONE_LIGHT: Record<string, string> = {
  ENTRY:         'bg-blue-50 text-blue-700',
  MAKEUP:        'bg-pink-50 text-pink-700',
  SKINCARE:      'bg-purple-50 text-purple-700',
  BATH_BODY:     'bg-teal-50 text-teal-700',
  BILLING:       'bg-amber-50 text-amber-700',
  BILLING_QUEUE: 'bg-orange-50 text-orange-700',
}

const defaultBg    = 'bg-gray-400'
const defaultLight = 'bg-gray-50 text-gray-700'

interface Props { data: HeatmapResponse | null }

const HeatmapGrid: FC<Props> = ({ data }) => {
  if (!data) {
    return (
      <div className="rounded-2xl bg-white border border-gray-100 shadow-sm p-5">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-xl bg-gray-50 border border-gray-100 h-20 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-sm p-5">
      <div className="mb-4">
        <h3 className="font-semibold text-gray-900">Zone Heatmap</h3>
        <p className="text-xs text-gray-400 mt-0.5">{data.zones.length} zones · traffic intensity</p>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {data.zones.map(z => {
          const barColor   = ZONE_BG[z.zone_id]    ?? defaultBg
          const badgeClass = ZONE_LIGHT[z.zone_id] ?? defaultLight
          return (
            <div key={z.zone_id} className="bg-gray-50 rounded-xl border border-gray-100 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${badgeClass}`}>
                  {z.zone_id.replace(/_/g, ' ')}
                </span>
                <span className="text-xs font-bold text-gray-900">{z.normalised_score.toFixed(0)}</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden mb-2">
                <div
                  className={`h-full rounded-full ${barColor} transition-all duration-500`}
                  style={{ width: `${z.normalised_score}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-gray-400">
                <span>{z.visit_frequency} visits</span>
                <span>{(z.avg_dwell_ms / 1000).toFixed(0)}s avg dwell</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default HeatmapGrid
