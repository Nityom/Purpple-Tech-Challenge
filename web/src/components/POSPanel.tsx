import type { FC } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import type { POSAnalyticsResponse } from '../api'

interface Props { data: POSAnalyticsResponse | null; storeName?: string }

const fmtCur = (n: number) => `₹${n.toLocaleString('en-IN')}`

const POSPanel: FC<Props> = ({ data, storeName }) => {
  if (!data) {
    return <div className="rounded-2xl bg-white border border-gray-100 shadow-sm h-64 animate-pulse" />
  }

  return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-sm p-5 flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">POS Analytics</h3>
          <p className="text-xs text-gray-400 mt-0.5">POS Sales · {storeName ?? 'All Stores'}</p>
        </div>
        <span className="text-xs px-2.5 py-1 bg-green-50 text-green-700 rounded-full font-semibold border border-green-100">
          {data.total_transactions} txns
        </span>
      </div>

      {/* Hourly revenue */}
      {data.hourly.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Revenue by Hour</p>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={data.hourly} barCategoryGap="25%" margin={{ top: 4, right: 0, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
              <XAxis dataKey="hour" tickFormatter={h => `${h}h`} tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} width={45} tickFormatter={v => `₹${v}`} />
              <Tooltip
                contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                formatter={(v: number) => [fmtCur(v), 'Revenue']}
                labelFormatter={h => `${h}:00`}
              />
              <Bar dataKey="revenue" fill="#166534" radius={[5, 5, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Top products */}
      {data.top_products.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Top Products</p>
          <div className="flex flex-col gap-2">
            {data.top_products.slice(0, 5).map((p, i) => (
              <div key={p.product_name} className="flex items-center gap-2">
                <span className="w-5 h-5 rounded-full bg-green-50 text-green-700 text-[10px] font-bold flex items-center justify-center shrink-0">{i + 1}</span>
                <span className="text-xs text-gray-700 flex-1 truncate">{p.product_name}</span>
                <span className="text-[10px] text-gray-400">{p.qty_sold} qty</span>
                <span className="text-xs font-semibold text-gray-900">{fmtCur(p.revenue)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Top categories */}
      {data.top_categories.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">By Category</p>
          <div className="flex flex-wrap gap-2">
            {data.top_categories.map(c => (
              <div key={c.category} className="flex items-center gap-1.5 bg-gray-50 rounded-xl px-3 py-1.5 border border-gray-100">
                <span className="text-xs font-medium text-gray-700">{c.category}</span>
                <span className="text-xs font-semibold text-green-700">{fmtCur(c.revenue)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.top_products.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-4">No POS data for this date</p>
      )}
    </div>
  )
}

export default POSPanel
