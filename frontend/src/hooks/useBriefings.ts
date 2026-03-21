import { useCallback, useEffect, useState } from 'react'
import type { BriefingListItem } from '@/types'
import { fetchBriefings } from '@/lib/api'

export function useBriefings() {
  const [briefings, setBriefings] = useState<BriefingListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchBriefings()
      setBriefings(data.sort((a, b) => b.briefing_date.localeCompare(a.briefing_date)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load briefings')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return { briefings, loading, error, refresh }
}
