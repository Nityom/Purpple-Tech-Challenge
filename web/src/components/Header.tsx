import type { FC } from 'react'
import type { NavPage } from './Sidebar'

interface Props {
  date: string
  onDateChange: (d: string) => void
  apiOk: boolean
  lastUpdate: string
  anomalyCount: number
  onNavigate: (page: NavPage) => void
}

const Header: FC<Props> = ({ date, onDateChange, apiOk, lastUpdate, anomalyCount, onNavigate }) => (
  <header className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-100 sticky top-0 z-10">
    <div />

    {/* Right controls */}
    <div className="flex items-center gap-3">
      {lastUpdate && (
        <span className="text-xs text-gray-400 hidden md:block">Updated {lastUpdate}</span>
      )}

      <label className="flex items-center gap-2">
        <input
          type="date"
          value={date}
          onChange={e => onDateChange(e.target.value)}
          className="text-sm text-gray-700 border border-gray-200 rounded-xl px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500 bg-white"
        />
      </label>

      {/* API status */}
      <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium ${
        apiOk ? 'bg-green-50 text-green-700 border border-green-100' : 'bg-red-50 text-red-600 border border-red-100'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${apiOk ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`} />
        {apiOk ? 'API Live' : 'Offline'}
      </div>

      {/* Bell - navigates to anomalies */}
      <button
        onClick={() => onNavigate('anomalies')}
        className="relative w-9 h-9 border border-gray-200 rounded-xl flex items-center justify-center text-gray-500 hover:bg-gray-50 transition-colors"
        title="View anomalies"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {anomalyCount > 0 && (
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">
            {anomalyCount > 9 ? '9+' : anomalyCount}
          </span>
        )}
      </button>

      {/* Avatar */}
      <div className="flex items-center gap-2.5 pl-2 border-l border-gray-100">
        <div className="w-9 h-9 rounded-xl bg-green-100 flex items-center justify-center text-sm font-bold text-green-700 shrink-0">S</div>
        <div className="hidden sm:block">
          <p className="text-sm font-semibold text-gray-800 leading-tight">Store Manager</p>
          <p className="text-[10px] text-gray-400 leading-tight">Brigade Road</p>
        </div>
      </div>
    </div>
  </header>
)

export default Header
