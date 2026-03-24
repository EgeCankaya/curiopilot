import { useCallback, useEffect, useState } from 'react'
import { fetchObsidianStatus, exportObsidianVault, type ObsidianStatus } from '@/lib/api'

export function useObsidian() {
  const [status, setStatus] = useState<ObsidianStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setStatus(await fetchObsidianStatus())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load Obsidian status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const reExport = useCallback(async (vaultPath?: string) => {
    setExporting(true)
    setError(null)
    try {
      await exportObsidianVault(vaultPath)
      // Refresh status after export
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }, [load])

  return { status, loading, error, reExport, exporting, refresh: load }
}
