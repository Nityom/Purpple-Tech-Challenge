import type { FC } from 'react'

interface Props {
  date: string
  onDateChange: (d: string) => void
  apiOk: boolean
  lastUpdate: string
}

const Header: FC<Props> = ({ date, onDateChange, apiOk, lastUpdate }) => (
  <header className="flex items-center justify-between px-4 md:px-6 py-3 bg-white border-b border-gray-100 sticky top-0 z-10">
    <div />

    {/* Right controls */}
    <div className="flex items-center gap-2 md:gap-3">
      {lastUpdate && (
        <span className="text-xs text-gray-400 hidden md:block">Updated {lastUpdate}</span>
      )}

      <label className="flex items-center gap-2">
        <input
          type="date"
          value={date}
          onChange={e => onDateChange(e.target.value)}
          className="text-sm text-gray-700 border border-gray-200 rounded-xl px-2 md:px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500 bg-white w-36 md:w-auto"
        />
      </label>

      {/* API status */}
      <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium ${
        apiOk ? 'bg-green-50 text-green-700 border border-green-100' : 'bg-red-50 text-red-600 border border-red-100'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${apiOk ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`} />
        {apiOk ? 'API Live' : 'Offline'}
      </div>

      {/* Avatar */}
      <div className="flex items-center gap-2.5 pl-2 border-l border-gray-100">
        <div className="w-9 h-9 rounded-xl bg-green-100 flex items-center justify-center text-sm font-bold text-green-700 shrink-0">S</div>
        <div className="hidden sm:block">
          <p className="text-sm font-semibold text-gray-800 leading-tight">Store Manager</p>
          <p className="text-[10px] text-gray-400 leading-tight">Purplle Road</p>
        </div>
      </div>
    </div>
  </header>
)

export default Header
