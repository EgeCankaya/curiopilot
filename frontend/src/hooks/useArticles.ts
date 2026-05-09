import { useEffect, useState } from 'react'
import type { ArticleListItem, BriefingDetail } from '@/types'
import { fetchBriefing } from '@/lib/api'

export function useArticles(date: string | null) {
  const [articles, setArticles] = useState<ArticleListItem[]>([])
  const [detail, setDetail] = useState<BriefingDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [prevDate, setPrevDate] = useState<string | null>(date)

  if (date !== prevDate) {
    setPrevDate(date)
    setArticles([])
    setDetail(null)
    setError(null)
    setLoading(date !== null)
  }

  useEffect(() => {
    if (!date) return

    let cancelled = false

    fetchBriefing(date)
      .then((data) => {
        if (cancelled) return
        setDetail(data)
        setArticles(data.articles)
      })
      .catch((e) => {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Failed to load articles')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [date])

  return { articles, detail, loading, error }
}
