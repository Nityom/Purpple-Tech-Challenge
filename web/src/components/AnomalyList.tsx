import type { FC } from 'react'
import type { AnomaliesResponse, Anomaly } from '../api'

const SEV_CARD: Record<Anomaly['severity'], string> = {
  INFO:     'bg-blue-50 border-blue-100',
  WARN:     'bg-amber-50 border-amber-100',
  CRITICAL: 'bg-red-50 border-red-100',
}
const SEV_BADGE: Record<Anomaly['severity'], string> = {
  INFO:     'bg-blue-100 text-blue-700',
  WARN:     'bg-amber-100 text-amber-700',
  CRITICAL: 'bg-red-100 text-red-700',
}
const SEV_DOT: Record<Anomaly['severity'], string> = {
  INFO:     'bg-blue-400',
  WARN:     'bg-amber-400',
  CRITICAL: 'bg-red-500 animate-pulse',
}
const SEV_TEXT: Record<Anomaly['severity'], string> = {
  INFO:     'text-blue-800',
  WARN:     'text-amber-800',
  CRITICAL: 'text-red-800',
}

interface Props { data: AnomaliesResponse | null; searchQuery?: string }

const AnomalyList: FC<Props> = ({ data, searchQuery = '' }) => {
  if (!data) {
    return <div className="rounded-2xl bg-white border border-gray-100 shadow-sm h-40 animate-pulse" />
  }

  const q = searchQuery.toLowerCase()
  const items = data.anomalies.filter(a =>
    !q ||
    a.description.toLowerCase().includes(q) ||
    a.anomaly_type.toLowerCase().includes(q) ||
    a.severity.toLowerCase().includes(q)
  )

  return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-sm p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-900">Active Anomalies</h3>
          <p className="text-xs text-gray-400 mt-0.5">Real-time detection</p>
        </div>
        {data.anomalies.length > 0 && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-red-100 text-red-700 font-semibold">
            {items.length}{q ? ` of ${data.anomalies.length}` : ''} active
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="text-center py-8">
          <div className="w-12 h-12 bg-green-50 rounded-2xl flex items-center justify-center mx-auto mb-3">
            <svg className="w-6 h-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-sm font-medium text-gray-700">{q ? `No results for "${searchQuery}"` : 'All systems normal'}</p>
          <p className="text-xs text-gray-400 mt-1">{q ? 'Try a different search term' : 'No anomalies detected'}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {items.map(a => (
            <div key={a.anomaly_id} className={`rounded-xl border p-3 ${SEV_CARD[a.severity]}`}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${SEV_DOT[a.severity]}`} />
                <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full ${SEV_BADGE[a.severity]}`}>
                  {a.severity}
                </span>
                <span className="text-[10px] text-gray-400 font-mono ml-auto truncate">
                  {a.anomaly_type.replace(/_/g, ' ')}
                </span>
              </div>
              <p className={`text-sm font-medium ${SEV_TEXT[a.severity]}`}>{a.description}</p>
              <p className="text-xs text-gray-500 mt-0.5">→ {a.suggested_action}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default AnomalyList
