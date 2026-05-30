import type { FC } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import type { FunnelResponse } from '../api'

interface Props { data: FunnelResponse | null }

const STAGE_COLORS: Record<string, string> = {
  Entry:        '#166534',
  ZoneVisit:    '#16a34a',
  BillingQueue: '#4ade80',
  Purchase:     '#bbf7d0',
}

const FunnelChart: FC<Props> = ({ data }) => {
  if (!data) {
    return <div className="rounded-2xl bg-white border border-gray-100 shadow-sm h-64 animate-pulse" />
  }

  const chartData = data.stages.map(s => ({ name: s.stage, count: s.count, drop: s.drop_off_pct }))

  return (
    <div className="rounded-2xl bg-white border border-gray-100 shadow-sm p-5">
      <div className="flex items-center justify-between mb-1">
        <div>
          <h3 className="font-semibold text-gray-900">Conversion Funnel</h3>
          <p className="text-xs text-gray-400 mt-0.5">{data.total_sessions} total sessions</p>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} barCategoryGap="35%" margin={{ top: 10, right: 0, left: -10, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" vertical={false} />
          <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} axisLine={false} tickLine={false} width={30} />
          <Tooltip
            contentStyle={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, fontSize: 12, boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
            labelStyle={{ color: '#111827', fontWeight: 600 }}
            formatter={(value: number, _name: string, props) => [
              `${value} visitors (↓${props.payload.drop.toFixed(1)}%)`, '',
            ]}
          />
          <Bar dataKey="count" radius={[8, 8, 0, 0]}>
            {chartData.map(entry => (
              <Cell key={entry.name} fill={STAGE_COLORS[entry.name] ?? '#22c55e'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="flex flex-wrap gap-3 pt-2 border-t border-gray-50">
        {data.stages.map(s => (
          <div key={s.stage} className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: STAGE_COLORS[s.stage] ?? '#22c55e' }} />
            <span className="text-xs text-gray-600">{s.stage}</span>
            <span className="text-xs font-semibold text-gray-900">{s.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default FunnelChart
