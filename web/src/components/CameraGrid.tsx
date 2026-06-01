import type { FC } from 'react'
import type { CameraStatsResponse, CameraStat } from '../api'

const CAMERA_META: Record<string, { label: string; sub: string; icon: string }> = {
  CAM_ENTRY_01: {
    label: 'Entry Gate',
    sub:   'Main entrance',
    icon:  'M3 10h18M3 10V6a2 2 0 012-2h14a2 2 0 012 2v4M3 10v8a2 2 0 002 2h14a2 2 0 002-2v-8',
  },
  CAM_FLOOR_01: {
    label: 'Floor Zone 1',
    sub:   'Shopping floor',
    icon:  'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  },
  CAM_FLOOR_02: {
    label: 'Floor Zone 2',
    sub:   'Shopping floor',
    icon:  'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  },
  CAM_FLOOR_03: {
    label: 'Floor Zone 3',
    sub:   'Shopping floor',
    icon:  'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  },
  CAM_BILLING_01: {
    label: 'Billing',
    sub:   'POS counter',
    icon:  'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
  },
}

// All green palette — each camera gets a distinct green shade
const ACCENT: Record<string, { bar: string; text: string; iconBg: string; iconText: string }> = {
  CAM_ENTRY_01:   { bar: 'bg-green-700', text: 'text-green-700', iconBg: 'bg-green-700', iconText: 'text-white'       },
  CAM_FLOOR_01:   { bar: 'bg-green-600', text: 'text-green-600', iconBg: 'bg-green-100', iconText: 'text-green-700'  },
  CAM_FLOOR_02:   { bar: 'bg-green-500', text: 'text-green-500', iconBg: 'bg-green-100', iconText: 'text-green-600'  },
  CAM_FLOOR_03:   { bar: 'bg-green-400', text: 'text-green-400', iconBg: 'bg-green-50',  iconText: 'text-green-500'  },
  CAM_BILLING_01: { bar: 'bg-emerald-600', text: 'text-emerald-600', iconBg: 'bg-emerald-100', iconText: 'text-emerald-700' },
}
const DEFAULT_ACCENT = { bar: 'bg-gray-300', text: 'text-gray-400', iconBg: 'bg-gray-100', iconText: 'text-gray-500' }

const isFloor = (id: string) => id.startsWith('CAM_FLOOR')

const CameraCard: FC<{ cam: CameraStat; maxEvents: number }> = ({ cam, maxEvents }) => {
  const meta    = CAMERA_META[cam.camera_id] ?? { label: cam.camera_id, sub: '', icon: '' }
  const accent  = ACCENT[cam.camera_id] ?? DEFAULT_ACCENT
  const pct     = maxEvents > 0 ? Math.round((cam.total_events / maxEvents) * 100) : 0
  const hasData = cam.total_events > 0
  const floor   = isFloor(cam.camera_id)

  const stats = floor
    ? [
        { val: cam.unique_visitors, label: 'Visitors' },
        { val: cam.zone_events,     label: 'Zone events' },
        { val: cam.staff_events,    label: 'Staff' },
      ]
    : [
        { val: cam.entries,         label: 'Entries' },
        { val: cam.exits,           label: 'Exits' },
        { val: cam.unique_visitors, label: 'Visitors' },
      ]

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">

      {/* Header with colored icon */}
      <div className="p-4 pb-3 flex items-center gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${accent.iconBg}`}>
          {meta.icon && (
            <svg className={`w-4.5 h-4.5 ${accent.iconText}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} style={{ width: 18, height: 18 }}>
              <path strokeLinecap="round" strokeLinejoin="round" d={meta.icon} />
            </svg>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-bold text-gray-900 leading-tight truncate">{meta.label}</p>
            <span className={`shrink-0 w-1.5 h-1.5 rounded-full ${hasData ? 'bg-green-500' : 'bg-gray-300'}`} />
          </div>
          <p className="text-[10px] text-gray-400 leading-tight mt-0.5">{meta.sub}</p>
        </div>
      </div>

      {/* Big event count + progress */}
      <div className="px-4 pb-3">
        <div className="flex items-end justify-between mb-1.5">
          <span className={`text-2xl font-black leading-none ${hasData ? accent.text : 'text-gray-300'}`}>
            {cam.total_events.toLocaleString()}
          </span>
          <span className="text-[10px] text-gray-400 mb-0.5">{pct}% of max</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${accent.bar}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-px bg-gray-100 border-t border-gray-100">
        {stats.map(({ val, label }) => (
          <div key={label} className="bg-white py-3 flex flex-col items-center">
            <span className={`text-base font-bold ${hasData ? 'text-gray-800' : 'text-gray-300'}`}>{val}</span>
            <span className="text-[9px] text-gray-400 mt-0.5 text-center leading-tight">{label}</span>
          </div>
        ))}
      </div>

      {/* Footer */}
      {(cam.reentries > 0 || (!floor && cam.zone_events > 0)) && (
        <div className="px-4 py-2 flex gap-3 text-[10px] text-gray-400 bg-gray-50 border-t border-gray-100">
          {cam.reentries > 0 && <span>{cam.reentries} re-entry</span>}
          {!floor && cam.zone_events > 0 && <span>{cam.zone_events} zone</span>}
          <span className="ml-auto font-mono">{cam.camera_id.split('_').pop()}</span>
        </div>
      )}
    </div>
  )
}

interface Props { data: CameraStatsResponse | null }

const CameraGrid: FC<Props> = ({ data }) => {
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

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
      {cameras.map(cam => <CameraCard key={cam.camera_id} cam={cam} maxEvents={maxEvents} />)}
    </div>
  )
}

export default CameraGrid
