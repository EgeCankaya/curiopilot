import { useCallback, useEffect, useState } from 'react'
import { fetchConfig, updateConfig, fetchAvailableModels } from '@/lib/api'

export function useConfig() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [models, setModels] = useState<{ name: string; size: number }[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [cfg, mdls] = await Promise.all([fetchConfig(), fetchAvailableModels()])
      setConfig(cfg)
      setModels(mdls.models ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load config')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const save = useCallback(async (patch: Record<string, unknown>) => {
    setSaving(true)
    setSaveError(null)
    try {
      await updateConfig(patch)
      await load() // reload to reflect changes
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : 'Failed to save config')
    } finally {
      setSaving(false)
    }
  }, [load])

  return { config, loading, error, saving, saveError, save, models, refresh: load }
}
