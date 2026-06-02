import type { FC } from 'react'
import type { CameraStatsResponse, CameraStat, StoreConfig } from '../api'

// ── Icons by camera type ───────────────────────────────────────────────────
const TYPE_ICON: Record<string, string> = {
  entry_exit: 'M3 10h18M3 10V6a2 2 0 012-2h14a2 2 0 012 2v4M3 10v8a2 2 0 002 2h14a2 2 0 002-2v-8',
  floor:      'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  billing:    'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2',
}

// ── Accent palette cycles by index ────────────────────────────────────────
const ACCENTS = [
  { bar: 'bg-green-700',   text: 'text-green-700',   iconBg: 'bg-green-700',   iconText: 'text-white'        },
  { bar: 'bg-green-600',   text: 'text-green-600',   iconBg: 'bg-green-600',   iconText: 'text-white'        },
  { bar: 'bg-green-500',   text: 'text-green-500',   iconBg: 'bg-green-100',   iconText: 'text-green-600'    },
  { bar: 'bg-green-400',   text: 'text-green-500',   iconBg: 'bg-green-50',    iconText: 'text-green-500'    },
  { bar: 'bg-emerald-600', text: 'text-emerald-600', iconBg: 'bg-emerald-100', iconText: 'text-emerald-700'  },
]
const DEFAULT_ACCENT = { bar: 'bg-gray-300', text: 'text-gray-400', iconBg: 'bg-gray-100', iconText: 'text-gray-500' }

// ── Derive a short friendly label from the camera ID ──────────────────────
function camLabel(camId: string, type: string): string {
  // e.g. CAM_ENTRY_01 → suffix "01", CAM_FLOOR_02 → "02"
  const num = camId.match(/(\d+)$/)?.[1] ?? ''
  if (type === 'entry_exit') return num ? `Entry Gate ${parseInt(num, 10)}` : 'Entry Gate'
  if (type === 'billing')    return 'Billing Counter'
  if (type === 'floor')      return num ? `Zone Camera ${parseInt(num, 10)}` : 'Zone Camera'
  return camId.replace(/_/g, ' ')
}

// ── Single camera card ─────────────────────────────────────────────────────
interface CardProps {
  cam:       CameraStat
  maxEvents: number
  type:      string      // from storeConfig
  label:     string      // derived friendly name
  sub:       string      // description from storeConfig
  accent:    typeof ACCENTS[0]
}

const CameraCard: FC<CardProps> = ({ cam, maxEvents, type, label, sub, accent }) => {
  const pct     = maxEvents > 0 ? Math.round((cam.total_events / maxEvents) * 100) : 0
  const hasData = cam.total_events > 0
  const isFloor   = type === 'floor'
  const isBilling = type === 'billing'

  const stats = isFloor
    ? [
        { val: cam.unique_visitors, label: 'Visitors'    },
        { val: cam.zone_events,     label: 'Zone events' },
        { val: cam.staff_events,    label: 'Staff'       },
      ]
    : isBilling
    ? [
        { val: cam.entries,         label: 'Queue in'    },
        { val: cam.exits,           label: 'Queue out'   },
        { val: cam.unique_visitors, label: 'Visitors'    },
      ]
    : [
        { val: cam.entries,         label: 'Entries'     },
        { val: cam.exits,           label: 'Exits'       },
        { val: cam.unique_visitors, label: 'Visitors'    },
      ]

  const icon = TYPE_ICON[type] ?? TYPE_ICON.floor

  return (
    <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden flex flex-col">

      {/* Header */}
      <div className="p-4 pb-3 flex items-center gap-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${accent.iconBg}`}>
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8} style={{ width: 18, height: 18 }}
            className={accent.iconText}>
            <path strokeLinecap="round" strokeLinejoin="round" d={icon} />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-sm font-bold text-gray-900 leading-tight truncate">{label}</p>
            <span className={`shrink-0 w-1.5 h-1.5 rounded-full ${hasData ? 'bg-green-500' : 'bg-gray-300'}`} />
          </div>
          <p className="text-[10px] text-gray-400 leading-tight mt-0.5 truncate" title={sub}>{sub}</p>
        </div>
      </div>

      {/* Event count + bar */}
      <div className="px-4 pb-3">
        <div className="flex items-end justify-between mb-1.5">
          <span className={`text-2xl font-black leading-none ${hasData ? accent.text : 'text-gray-300'}`}>
            {cam.total_events.toLocaleString()}
          </span>
          <span className="text-[10px] text-gray-400 mb-0.5">{pct}% of max</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-700 ${accent.bar}`} style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 gap-px bg-gray-100 border-t border-gray-100 mt-auto">
        {stats.map(({ val, label: lbl }) => (
          <div key={lbl} className="bg-white py-3 flex flex-col items-center">
            <span className={`text-base font-bold ${hasData ? 'text-gray-800' : 'text-gray-300'}`}>{val}</span>
            <span className="text-[9px] text-gray-400 mt-0.5 text-center leading-tight">{lbl}</span>
          </div>
        ))}
      </div>

      {/* Footer — re-entries badge */}
      {cam.reentries > 0 && (
        <div className="px-4 py-2 flex gap-3 text-[10px] text-gray-400 bg-gray-50 border-t border-gray-100">
          <span>{cam.reentries} re-entr{cam.reentries === 1 ? 'y' : 'ies'}</span>
          <span className="ml-auto font-mono text-gray-300">{cam.camera_id}</span>
        </div>
      )}
    </div>
  )
}

// ── Grid ───────────────────────────────────────────────────────────────────
interface Props {
  data:        CameraStatsResponse | null
  storeConfig: StoreConfig | null
}

const CameraGrid: FC<Props> = ({ data, storeConfig }) => {
  // Build ordered camera list from config (preserves layout order), fall back to API data order
  const configCams = storeConfig
    ? Object.keys(storeConfig.cameras)
    : data?.cameras.map(c => c.camera_id) ?? []

  const colCount = Math.min(Math.max(configCams.length, 1), 5)

  if (!data) {
    return (
      <div className={`grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-${colCount} gap-4`}>
        {configCams.map((id) => (
          <div key={id} className="rounded-2xl bg-white border border-gray-100 shadow-sm h-52 animate-pulse" />
        ))}
      </div>
    )
  }

  const byId      = Object.fromEntries(data.cameras.map(c => [c.camera_id, c]))
  const maxEvents = Math.max(...data.cameras.map(c => c.total_events), 1)

  const cameras: CameraStat[] = configCams.map(id =>
    byId[id] ?? {
      camera_id: id, total_events: 0, unique_visitors: 0,
      entries: 0, exits: 0, reentries: 0, zone_events: 0,
      staff_events: 0, first_event_at: null, last_event_at: null,
    }
  )

  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-${colCount} gap-4`}>
      {cameras.map((cam, idx) => {
        const cfg    = storeConfig?.cameras[cam.camera_id]
        const type   = cfg?.type ?? (cam.camera_id.includes('BILLING') ? 'billing' : cam.camera_id.includes('ENTRY') ? 'entry_exit' : 'floor')
        const label  = camLabel(cam.camera_id, type)
        const sub    = cfg?.description ?? cam.camera_id.replace(/_/g, ' ')
        const accent = ACCENTS[idx] ?? DEFAULT_ACCENT
        return (
          <CameraCard key={cam.camera_id} cam={cam} maxEvents={maxEvents}
            type={type} label={label} sub={sub} accent={accent} />
        )
      })}
    </div>
  )
}

export default CameraGrid

