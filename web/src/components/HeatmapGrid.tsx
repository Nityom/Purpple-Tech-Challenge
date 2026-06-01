import type { FC } from 'react'
import type { HeatmapResponse } from '../api'

// Green shades: rank 1 = darkest, rank N = lightest
const GREEN_SHADES = [
  { bar: 'bg-green-700', text: 'text-green-800', bg: 'bg-green-700', track: 'bg-green-100' },
  { bar: 'bg-green-600', text: 'text-green-700', bg: 'bg-green-600', track: 'bg-green-100' },
  { bar: 'bg-green-500', text: 'text-green-600', bg: 'bg-green-500', track: 'bg-green-50'  },
  { bar: 'bg-green-400', text: 'text-green-600', bg: 'bg-green-400', track: 'bg-green-50'  },
  { bar: 'bg-green-300', text: 'text-green-500', bg: 'bg-green-300', track: 'bg-gray-100'  },
  { bar: 'bg-green-200', text: 'text-green-400', bg: 'bg-green-200', track: 'bg-gray-100'  },
]

const ZONE_LABELS: Record<string, string> = {
  ENTRY:         'Entry',
  MAKEUP:        'Makeup',
  SKINCARE:      'Skincare',
  BATH_BODY:     'Bath & Body',
  BILLING:       'Billing',
  BILLING_QUEUE: 'Queue',
}

interface Props { data: HeatmapResponse | null }

const HeatmapGrid: FC<Props> = ({ data }) => {
  if (!data) {
    return (
      <div className="rounded-2xl bg-white border border-gray-100 shadow-sm p-5">
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="rounded-xl bg-gray-50 border border-gray-100 h-12 animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  const sorted = [...data.zones].sort((a, b) => b.normalised_score - a.normalised_score)
  const topLabel = ZONE_LABELS[sorted[0]?.zone_id] ?? sorted[0]?.zone_id ?? ''

  return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-sm p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-900">Zone Heatmap</h3>
          <p className="text-xs text-gray-400 mt-0.5">{data.zones.length} zones · traffic intensity</p>
        </div>
        {topLabel && (
          <span className="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-green-50 text-green-700 border border-green-100">
            Top: {topLabel}
          </span>
        )}
      </div>

      {/* Zone rows */}
      <div className="flex flex-col gap-2.5">
        {sorted.map((z, i) => {
          const shade = GREEN_SHADES[i] ?? GREEN_SHADES[GREEN_SHADES.length - 1]
          const dwell = z.avg_dwell_ms >= 1000
            ? `${(z.avg_dwell_ms / 1000).toFixed(0)}s dwell`
            : z.avg_dwell_ms > 0 ? '<1s dwell' : null
          const label = ZONE_LABELS[z.zone_id] ?? z.zone_id.replace(/_/g, ' ')
          return (
            <div key={z.zone_id} className="flex items-center gap-3">
              {/* Score pill */}
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${shade.bg}`}>
                <span className="text-sm font-black text-white leading-none">{z.normalised_score.toFixed(0)}</span>
              </div>

              {/* Bar + labels */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs font-semibold ${shade.text}`}>{label}</span>
                  <span className="text-[10px] text-gray-400">
                    {z.visit_frequency} visits{dwell ? ` · ${dwell}` : ''}
                  </span>
                </div>
                <div className={`w-full ${shade.track} rounded-full h-2 overflow-hidden`}>
                  <div
                    className={`h-full rounded-full ${shade.bar} transition-all duration-700`}
                    style={{ width: `${z.normalised_score}%` }}
                  />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default HeatmapGrid
