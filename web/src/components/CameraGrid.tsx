import type { FC } from 'react'
import type { CameraStatsResponse, CameraStat } from '../api'

const CAMERA_LABELS: Record<string, string> = {
  CAM_ENTRY_01:   'Entry Gate',
  CAM_FLOOR_01:   'Floor — Zone 1',
  CAM_FLOOR_02:   'Floor — Zone 2',
  CAM_FLOOR_03:   'Floor — Zone 3',
  CAM_BILLING_01: 'Billing Counter',
}

const CAMERA_ICONS: Record<string, string> = {
  CAM_ENTRY_01:   'M3 10h18M3 10V6a2 2 0 012-2h14a2 2 0 012 2v4M3 10v8a2 2 0 002 2h14a2 2 0 002-2v-8',
  CAM_FLOOR_01:   'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  CAM_FLOOR_02:   'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  CAM_FLOOR_03:   'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  CAM_BILLING_01: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
}

const ACCENT_COLORS: Record<string, string> = {
  CAM_ENTRY_01:   'bg-blue-500',
  CAM_FLOOR_01:   'bg-green-500',
  CAM_FLOOR_02:   'bg-teal-500',
  CAM_FLOOR_03:   'bg-cyan-500',
  CAM_BILLING_01: 'bg-amber-500',
}

const CameraCard: FC<{ cam: CameraStat; maxEvents: number }> = ({ cam, maxEvents }) => {
  const label  = CAMERA_LABELS[cam.camera_id] || cam.camera_id
  const iconD  = CAMERA_ICONS[cam.camera_id] || 'M15 10l4.553-2.277A1 1 0 0121 8.723v6.554a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z'
  const accent = ACCENT_COLORS[cam.camera_id] || 'bg-gray-400'
  const pct    = maxEvents > 0 ? (cam.total_events / maxEvents) * 100 : 0
  const hasData = cam.total_events > 0

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4 flex flex-col gap-3">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 bg-gray-50 rounded-xl flex items-center justify-center border border-gray-100">
            <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d={iconD} />
            </svg>
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-800 leading-tight">{label}</p>
            <p className="text-[10px] text-gray-400 font-mono leading-tight mt-0.5">{cam.camera_id}</p>
          </div>
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
          hasData ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-400'
        }`}>
          {hasData ? 'Active' : 'No data'}
        </span>
      </div>

      {/* Event bar */}
      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-gray-500">Events processed</span>
          <span className="font-bold text-gray-900">{cam.total_events.toLocaleString()}</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
          <div className={`h-full rounded-full ${accent} transition-all duration-500`} style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-3 gap-2">
        {[
          { val: cam.entries,         label: 'Entries',  color: 'text-blue-600'  },
          { val: cam.exits,           label: 'Exits',    color: 'text-gray-600'  },
          { val: cam.unique_visitors, label: 'Visitors', color: 'text-green-700' },
        ].map(({ val, label: lbl, color }) => (
          <div key={lbl} className="bg-gray-50 rounded-xl p-2 text-center border border-gray-100">
            <p className={`text-lg font-bold ${color}`}>{val}</p>
            <p className="text-[10px] text-gray-400">{lbl}</p>
          </div>
        ))}
      </div>

      {/* Bottom row */}
      <div className="flex gap-3 text-xs text-gray-500 pt-1 border-t border-gray-50">
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-teal-400"/>
          {cam.zone_events} zone
        </span>
        <span className="flex items-center gap-1">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400"/>
          {cam.reentries} re-entry
        </span>
        <span className="flex items-center gap-1 ml-auto">
          <span className="w-1.5 h-1.5 rounded-full bg-orange-300"/>
          {cam.staff_events} staff
        </span>
      </div>
    </div>
  )
}

interface Props { data: CameraStatsResponse | null; searchQuery?: string }

const CameraGrid: FC<Props> = ({ data, searchQuery = '' }) => {
  if (!data) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="rounded-2xl bg-white border border-gray-100 shadow-sm h-52 animate-pulse" />
        ))}
      </div>
    )
  }

  const ALL_CAMS = ['CAM_ENTRY_01', 'CAM_FLOOR_01', 'CAM_FLOOR_02', 'CAM_FLOOR_03', 'CAM_BILLING_01']
  const byId = Object.fromEntries(data.cameras.map(c => [c.camera_id, c]))
  const maxEvents = Math.max(...data.cameras.map(c => c.total_events), 1)
  const cameras: CameraStat[] = ALL_CAMS.map(id =>
    byId[id] ?? {
      camera_id: id, total_events: 0, unique_visitors: 0,
      entries: 0, exits: 0, reentries: 0, zone_events: 0,
      staff_events: 0, first_event_at: null, last_event_at: null,
    }
  )

  const q = searchQuery.toLowerCase()
  const filtered = cameras.filter(cam =>
    !q ||
    cam.camera_id.toLowerCase().includes(q) ||
    (CAMERA_LABELS[cam.camera_id] || '').toLowerCase().includes(q)
  )

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
      {filtered.length === 0
        ? <p className="col-span-full text-sm text-gray-400 text-center py-8">No cameras match "{searchQuery}"</p>
        : filtered.map(cam => <CameraCard key={cam.camera_id} cam={cam} maxEvents={maxEvents} />)
      }
    </div>
  )
}

export default CameraGrid
