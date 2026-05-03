import { Layers } from 'lucide-react'
import type { ArticleListItem } from '@/types'

interface SourceBreakdownProps {
  articles: ArticleListItem[]
}

const PALETTE = [
  '#0A84FF', // accent blue
  '#30D158', // success green
  '#FF9F0A', // orange
  '#BF5AF2', // purple
  '#FF453A', // red
  '#64D2FF', // cyan
  '#FFD60A', // yellow
  '#5E5CE6', // indigo
]

export default function SourceBreakdown({ articles }: SourceBreakdownProps) {
  if (articles.length === 0) return null

  const counts = new Map<string, number>()
  for (const a of articles) {
    counts.set(a.source_name, (counts.get(a.source_name) ?? 0) + 1)
  }
  const entries = [...counts.entries()].sort((a, b) => b[1] - a[1])
  const total = articles.length

  return (
    <section>
      <h3 className="mb-2 flex items-center gap-2 text-[13px] font-medium text-text-secondary">
        <Layers className="h-3.5 w-3.5 text-text-muted" />
        Sources
      </h3>
      <div className="rounded-2xl border border-border-subtle/60 bg-bg-card px-4 py-3">
        <div className="flex h-2 w-full overflow-hidden rounded-full bg-bg-tertiary">
          {entries.map(([name, n], i) => (
            <div
              key={name}
              title={`${name}: ${n}`}
              style={{ width: `${(n / total) * 100}%`, backgroundColor: PALETTE[i % PALETTE.length] }}
            />
          ))}
        </div>
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1.5">
          {entries.map(([name, n], i) => (
            <div key={name} className="flex items-center gap-1.5 text-xs text-text-secondary">
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
              />
              <span>{name}</span>
              <span className="tabular-nums text-text-muted">{n}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
