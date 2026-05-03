import { Hash } from 'lucide-react'
import type { ArticleListItem } from '@/types'

interface TopicDistributionProps {
  articles: ArticleListItem[]
}

export default function TopicDistribution({ articles }: TopicDistributionProps) {
  const counts = new Map<string, number>()
  for (const a of articles) {
    for (const c of a.key_concepts) {
      const key = c.trim()
      if (!key) continue
      counts.set(key, (counts.get(key) ?? 0) + 1)
    }
  }
  if (counts.size === 0) return null

  const top = [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
  const max = top[0][1]

  return (
    <section>
      <h3 className="mb-2 flex items-center gap-2 text-[13px] font-medium text-text-secondary">
        <Hash className="h-3.5 w-3.5 text-text-muted" />
        Topics
      </h3>
      <div className="flex flex-wrap gap-1.5">
        {top.map(([name, n]) => {
          const intensity = n / max
          const opacity = 0.45 + intensity * 0.55
          const sizeClass = intensity > 0.7 ? 'text-sm' : intensity > 0.4 ? 'text-xs' : 'text-[11px]'
          return (
            <span
              key={name}
              className={`inline-flex items-center gap-1 rounded-full border border-border-subtle/60 bg-bg-card px-2.5 py-0.5 text-text-primary ${sizeClass}`}
              style={{ opacity }}
            >
              {name}
              <span className="text-text-muted tabular-nums">{n}</span>
            </span>
          )
        })}
      </div>
    </section>
  )
}
