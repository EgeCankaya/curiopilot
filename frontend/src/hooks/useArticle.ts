import { useEffect, useState } from 'react'
import type { ArticleFull } from '@/types'
import { fetchArticle } from '@/lib/api'

export function useArticle(date: string | null, articleNumber: number | null) {
  const [article, setArticle] = useState<ArticleFull | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!date || !articleNumber) {
      setArticle(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    fetchArticle(date, articleNumber)
      .then((data) => {
        if (!cancelled) setArticle(data)
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load article')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [date, articleNumber])

  return { article, loading, error }
}
