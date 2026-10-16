import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import type { Bin } from '../api/client'

const TOKENS = ['--color-mark', '--color-rule', '--color-ink', '--color-ink-3', '--color-sheet'] as const

// SVG attributes can't read CSS variables, so resolve the theme colours once and on scheme changes
function useTokens() {
  const read = () =>
    Object.fromEntries(TOKENS.map((t) => [t, getComputedStyle(document.documentElement).getPropertyValue(t).trim()]))
  const [tokens, setTokens] = useState(read)
  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => setTokens(read())
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return tokens
}

type Props = {
  bins: Bin[]
  marker: number | null
  markerLabel: string
  format: (x: number) => string
  label: string
}

function nearest(bins: Bin[], x: number) {
  return bins.reduce((best, b) => (Math.abs(b.x - x) < Math.abs(best.x - x) ? b : best), bins[0]).x
}

export default function Histogram({ bins, marker, markerLabel, format, label }: Props) {
  const t = useTokens()
  const total = bins.reduce((s, b) => s + b.count, 0) || 1
  const font = { fontFamily: 'IBM Plex Mono, monospace', fontSize: 11 }
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={bins} barCategoryGap={2} margin={{ top: 22, right: 4, left: 4, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke={t['--color-rule']} />
        <XAxis dataKey="x" tickFormatter={format} stroke={t['--color-rule']} tick={{ fill: t['--color-ink-3'], ...font }} tickLine={false} minTickGap={28} />
        <Tooltip
          cursor={{ fill: t['--color-rule'] }}
          contentStyle={{ background: t['--color-sheet'], border: `1px solid ${t['--color-rule']}`, borderRadius: 3, ...font }}
          labelStyle={{ color: t['--color-ink'] }}
          itemStyle={{ color: t['--color-ink'] }}
          labelFormatter={(x) => `${label} ~${format(Number(x))}`}
          formatter={(count) => [`${((Number(count) / total) * 100).toFixed(1)}% of simulations`, '']}
          separator=""
        />
        <Bar dataKey="count" fill={t['--color-mark']} radius={[2, 2, 0, 0]} maxBarSize={22} isAnimationActive={false} />
        {marker !== null && bins.length > 0 && (
          <ReferenceLine
            x={nearest(bins, marker)}
            stroke={t['--color-ink']}
            strokeWidth={1.5}
            label={{ value: markerLabel, position: 'top', fill: t['--color-ink'], ...font }}
          />
        )}
      </BarChart>
    </ResponsiveContainer>
  )
}
