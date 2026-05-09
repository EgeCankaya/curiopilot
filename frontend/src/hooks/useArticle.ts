import { useEffect, useState } from 'react'
import type { ArticleFull } from '@/types'
import { fetchArticle } from '@/lib/api'

export function useArticle(date: string | null, articleNumber: number | null) {
  const [article, setArticle] = useState<ArticleFull | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [prevKey, setPrevKey] = useState<string>(`${date ?? ''}:${articleNumber ?? ''}`)

  const key = `${date ?? ''}:${articleNumber ?? ''}`
  if (key !== prevKey) {
    setPrevKey(key)
    setArticle(null)
    setError(null)
    setLoading(Boolean(date && articleNumber))
  }

  useEffect(() => {
    if (!date || !articleNumber) return

    let cancelled = false

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
