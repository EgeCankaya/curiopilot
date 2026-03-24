import { useEffect, useRef } from 'react'
import { Search, X, Loader2 } from 'lucide-react'
import { useSearch } from '@/hooks/useSearch'
import { cn } from '@/lib/utils'

interface SearchBarProps {
  onNavigate: (date: string, articleNumber: number) => void
}

export default function SearchBar({ onNavigate }: SearchBarProps) {
  const { query, setQuery, results, loading, clear } = useSearch()
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const open = query.length >= 2

  // Close on click outside
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        clear()
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open, clear])

  const handleSelect = (date: string, articleNumber: number) => {
    clear()
    onNavigate(date, articleNumber)
  }

  return (
    <div ref={containerRef} className="relative hidden flex-1 sm:block sm:max-w-sm">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              clear()
              inputRef.current?.blur()
            }
          }}
          placeholder="Search articles\u2026"
          className="w-full rounded-xl bg-bg-tertiary py-1.5 pl-9 pr-8 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/40"
        />
        {query && (
          <button
            onClick={clear}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Results dropdown */}
      {open && (
        <div className="absolute left-0 right-0 top-full z-50 mt-1 max-h-[400px] overflow-y-auto rounded-xl border border-border bg-bg-elevated shadow-lg">
          {loading && results.length === 0 && (
            <div className="flex items-center gap-2 px-4 py-3 text-sm text-text-muted">
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching\u2026
            </div>
          )}
          {!loading && results.length === 0 && query.length >= 2 && (
            <div className="px-4 py-3 text-sm text-text-muted">
              No results found.
            </div>
          )}
          {results.map((r) => (
            <button
              key={`${r.briefing_date}-${r.article_number}`}
              onClick={() => handleSelect(r.briefing_date, r.article_number)}
              className={cn(
                'flex w-full flex-col gap-0.5 px-4 py-2.5 text-left transition-colors',
                'hover:bg-bg-hover',
              )}
            >
              <span className="line-clamp-1 text-sm font-medium text-text-primary">
                {r.title}
              </span>
              <span className="flex items-center gap-2 text-xs text-text-muted">
                <span className="rounded bg-bg-tertiary px-1.5 py-0.5">{r.source_name}</span>
                <span>{r.briefing_date}</span>
                <span>R:{r.relevance_score}</span>
                <span>N:{Math.round(r.novelty_score * 100)}%</span>
              </span>
              <span className="line-clamp-1 text-xs text-text-muted">
                {r.summary}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
