import { useCallback, useEffect, useState } from 'react'
import { fetchDLQItems, fetchDLQStats, removeDLQItem, clearDLQ, type DLQItem, type DLQStats } from '@/lib/api'

export function useDLQ() {
  const [items, setItems] = useState<DLQItem[]>([])
  const [stats, setStats] = useState<DLQStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [fetchedItems, fetchedStats] = await Promise.all([
        fetchDLQItems(),
        fetchDLQStats(),
      ])
      setItems(fetchedItems)
      setStats(fetchedStats)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load DLQ')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const remove = useCallback(async (url: string) => {
    await removeDLQItem(url)
    setItems((prev) => prev.filter((i) => i.url !== url))
    setStats((prev) => prev ? { ...prev, total: prev.total - 1 } : prev)
  }, [])

  const clear = useCallback(async () => {
    await clearDLQ()
    setItems([])
    setStats((prev) => prev ? { ...prev, total: 0, by_phase: {}, by_error_type: {} } : prev)
  }, [])

  return { items, stats, loading, error, refresh, remove, clear }
}
