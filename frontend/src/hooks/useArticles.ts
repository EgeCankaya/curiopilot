import { useEffect, useState } from 'react'
import type { ArticleListItem, BriefingDetail } from '@/types'
import { fetchBriefing } from '@/lib/api'

export function useArticles(date: string | null) {
  const [articles, setArticles] = useState<ArticleListItem[]>([])
  const [detail, setDetail] = useState<BriefingDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date) {
      setArticles([])
      setDetail(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

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
