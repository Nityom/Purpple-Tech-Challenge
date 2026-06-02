import type { FC } from 'react'

export type NavPage = 'dashboard' | 'cameras' | 'analytics' | 'pos'

export const STORES: { id: string; name: string; sub: string }[] = [
  { id: 'STORE_BLR_001', name: 'Purplle Store 1', sub: 'Store 1 · BLR' },
  { id: 'STORE_BLR_002', name: 'Purplle Store 2', sub: 'Store 2 · BLR' },
]

interface Props {
  activePage:    NavPage
  onNavigate:    (page: NavPage) => void
  storeId:       string
  onStoreChange: (id: string) => void
}

const ICONS: Record<NavPage, string> = {
  dashboard: 'M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zm10 0a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z',
  cameras:   'M15 10l4.553-2.277A1 1 0 0121 8.723v6.554a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z',
  analytics: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  pos:       'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01',
}

const NAV: { id: NavPage; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'cameras',   label: 'Cameras'   },
  { id: 'analytics', label: 'Analytics' },
  { id: 'pos',       label: 'POS Sales' },
]

const NavIcon: FC<{ d: string }> = ({ d }) => (
  <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d={d} />
  </svg>
)

const Sidebar: FC<Props> = ({ activePage, onNavigate, storeId, onStoreChange }) => (
  <aside className="fixed left-0 top-0 h-screen w-56 bg-white border-r border-gray-100 hidden md:flex flex-col z-20">

    {/* Logo */}
    <div className="px-5 py-5 border-b border-gray-100 shrink-0">
      <div className="flex items-center gap-2.5">
        <div className="w-9 h-9 bg-green-100 rounded-xl flex items-center justify-center border border-green-200">
          <span className="text-green-700 text-base font-black">P</span>
        </div>
        <div>
          <p className="text-base font-bold text-gray-900 leading-tight">Purpple</p>
          <p className="text-[10px] text-gray-400 leading-tight">Store Intelligence</p>
        </div>
      </div>
    </div>

    {/* Menu */}
    <nav className="flex-1 px-3 pt-4 overflow-y-auto min-h-0">
      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest px-2 mb-2">Menu</p>
      <div className="flex flex-col gap-0.5">
        {NAV.map(item => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium w-full text-left transition-all duration-150 ${
              activePage === item.id
                ? 'bg-green-50 text-green-700 font-semibold border-l-2 border-green-600'
                : 'text-gray-500 hover:bg-gray-50 hover:text-gray-800'
            }`}
          >
            <NavIcon d={ICONS[item.id]} />
            <span className="flex-1">{item.label}</span>
          </button>
        ))}
      </div>
    </nav>

    {/* Store selector */}
    <div className="mx-3 mb-4 shrink-0">
      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest px-1 mb-1.5">Active Store</p>
      <div className="flex flex-col gap-1">
        {STORES.map(s => (
          <button
            key={s.id}
            onClick={() => onStoreChange(s.id)}
            className={`w-full text-left px-3 py-2 rounded-xl border transition-all text-xs font-medium ${
              storeId === s.id
                ? 'bg-green-50 border-green-200 text-green-800'
                : 'bg-gray-50 border-gray-100 text-gray-500 hover:bg-gray-100'
            }`}
          >
            <p className="font-semibold leading-tight">{s.name}</p>
            <p className="text-[10px] opacity-70 leading-tight mt-0.5">{s.sub}</p>
          </button>
        ))}
      </div>
    </div>
  </aside>
)

export default Sidebar
