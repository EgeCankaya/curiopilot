import { useEffect, useState } from 'react'
import type { FeedbackItem } from '@/types'
import { fetchFeedback } from '@/lib/api'

export function useFeedback(date: string | null) {
  const [feedback, setFeedback] = useState<Map<number, FeedbackItem>>(new Map())
  const [loading, setLoading] = useState(false)
  const [prevDate, setPrevDate] = useState<string | null>(date)

  if (date !== prevDate) {
    setPrevDate(date)
    setFeedback(new Map())
    setLoading(date !== null)
  }

  useEffect(() => {
    if (!date) return

    let cancelled = false

    fetchFeedback(date)
      .then((items) => {
        if (cancelled) return
        const map = new Map<number, FeedbackItem>()
        for (const item of items) {
          map.set(item.article_number, item)
        }
        setFeedback(map)
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [date])

  const updateLocal = (articleNumber: number, patch: Partial<FeedbackItem>) => {
    setFeedback((prev) => {
      const next = new Map(prev)
      const existing = next.get(articleNumber)
      next.set(articleNumber, { ...existing, article_number: articleNumber, briefing_date: '', ...patch } as FeedbackItem)
      return next
    })
  }

  return { feedback, loading, updateLocal }
}
