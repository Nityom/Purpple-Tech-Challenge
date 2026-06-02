import { useState, type FC } from 'react'
import type { HeatmapResponse } from '../api'

const STORE_LAYOUTS: Record<string, { image: string; name: string; address: string }> = {
  STORE_BLR_001: {
    image:   '/layouts/store1_layout.png',
    name:    'Brigade Bangalore',
    address: 'Brigade Road, Bangalore',
  },
  STORE_BLR_002: {
    image:   '/layouts/store2_layout.png',
    name:    'Purplle Store 2',
    address: 'Store 2 · Bangalore',
  },
}

const SCORE_COLOR = (score: number) => {
  if (score >= 80) return 'bg-red-500'
  if (score >= 60) return 'bg-orange-400'
  if (score >= 40) return 'bg-yellow-400'
  if (score >= 20) return 'bg-green-400'
  return 'bg-green-200'
}

interface Props {
  storeId: string
  heatmap: HeatmapResponse | null
}

const StoreLayoutMap: FC<Props> = ({ storeId, heatmap }) => {
  const layout = STORE_LAYOUTS[storeId] ?? STORE_LAYOUTS['STORE_BLR_001']
  const [imgLoaded, setImgLoaded] = useState(false)
  const [imgError, setImgError]   = useState(false)

  const zones = heatmap?.zones
    ? [...heatmap.zones].sort((a, b) => b.normalised_score - a.normalised_score)
    : []

  return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-sm overflow-hidden col-span-1 lg:col-span-2">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 flex items-center justify-between border-b border-gray-50">
        <div>
          <h3 className="font-semibold text-gray-900">Store Floor Plan</h3>
          <p className="text-xs text-gray-400 mt-0.5">{layout.name} · {layout.address}</p>
        </div>
        <span className="text-[11px] font-medium px-2.5 py-1 rounded-full bg-gray-50 text-gray-500 border border-gray-100">
          Layout
        </span>
      </div>

      <div className="flex flex-col lg:flex-row gap-0">
        {/* Floor plan image */}
        <div className="relative flex-1 bg-gray-50 flex items-center justify-center min-h-[220px]">
          {!imgLoaded && !imgError && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-8 h-8 border-2 border-green-200 border-t-green-600 rounded-full animate-spin" />
            </div>
          )}
          {imgError ? (
            <div className="flex flex-col items-center gap-2 text-gray-400 py-12">
              <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
              </svg>
              <p className="text-xs">Layout image not available</p>
            </div>
          ) : (
            <img
              src={layout.image}
              alt={`${layout.name} floor plan`}
              className={`w-full h-auto object-contain transition-opacity duration-300 ${imgLoaded ? 'opacity-100' : 'opacity-0'}`}
              style={{ maxHeight: '340px' }}
              onLoad={() => setImgLoaded(true)}
              onError={() => { setImgLoaded(true); setImgError(true) }}
            />
          )}
        </div>

        {/* Zone traffic legend */}
        {zones.length > 0 && (
          <div className="w-full lg:w-52 border-t lg:border-t-0 lg:border-l border-gray-100 flex flex-col">
            <div className="px-4 pt-3 pb-2 border-b border-gray-50">
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-widest">Zone Traffic</p>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 flex flex-col gap-1.5">
              {zones.map((z) => (
                <div key={z.zone_id} className="flex items-center gap-2.5">
                  <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${SCORE_COLOR(z.normalised_score)}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] font-medium text-gray-700 truncate">
                      {z.zone_id.replace(/_/g, ' ')}
                    </p>
                    <p className="text-[10px] text-gray-400">
                      {z.visit_frequency} visits · score {z.normalised_score.toFixed(0)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default StoreLayoutMap
