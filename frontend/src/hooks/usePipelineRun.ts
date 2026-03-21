import { useCallback, useRef, useState } from 'react'
import { triggerRun, connectRunStream } from '@/lib/api'
import type { RunStreamEvent } from '@/types'

const PHASE_LABELS: Record<string, string> = {
  scrape: 'Scraping sources',
  dedup: 'Deduplicating articles',
  filter: 'Filtering by relevance',
  swap: 'Swapping browser for reader',
  read: 'Reading & summarizing',
  novelty: 'Scoring novelty',
  briefing: 'Generating briefing',
  discover: 'Discovering new sources',
  feedback: 'Processing feedback',
  model_swap: 'Swapping models',
  model_swap_embed: 'Embedding with new model',
  graph_update: 'Updating knowledge graph',
}

export interface PipelineProgress {
  phase: string
  phaseLabel: string
  current: number
  total: number
}

export interface PipelineRunState {
  isRunning: boolean
  showModal: boolean
  progress: PipelineProgress | null
  result: { articles_scanned: number; articles_briefed: number; duration: number } | null
  error: string | null
}

export function usePipelineRun(onComplete?: () => void) {
  const [state, setState] = useState<PipelineRunState>({
    isRunning: false,
    showModal: false,
    progress: null,
    result: null,
    error: null,
  })
  const esRef = useRef<EventSource | null>(null)

  const start = useCallback(async () => {
    setState({
      isRunning: true,
      showModal: true,
      progress: null,
      result: null,
      error: null,
    })

    const es = connectRunStream(
      (event: RunStreamEvent) => {
        switch (event.event) {
          case 'progress': {
            const d = event.data as { phase: string; current: number; total: number }
            setState((s) => ({
              ...s,
              progress: {
                phase: d.phase,
                phaseLabel: PHASE_LABELS[d.phase] ?? d.phase,
                current: d.current,
                total: d.total,
              },
            }))
            break
          }
          case 'complete': {
            const d = event.data as { articles_scanned: number; articles_briefed: number; duration: number }
            setState((s) => ({
              ...s,
              isRunning: false,
              result: d,
            }))
            es.close()
            onComplete?.()
            break
          }
          case 'error': {
            const d = event.data as { error: string }
            setState((s) => ({
              ...s,
              isRunning: false,
              error: d.error,
            }))
            es.close()
            break
          }
        }
      },
      () => {
        setState((s) => ({
          ...s,
          isRunning: false,
          error: s.error ?? 'Connection to server lost',
        }))
      },
    )
    esRef.current = es

    try {
      await triggerRun()
    } catch (e) {
      es.close()
      const msg = e instanceof Error ? e.message : 'Failed to start pipeline'
      const isOllamaDown = msg.includes('503') || msg.toLowerCase().includes('ollama')
      setState((s) => ({
        ...s,
        isRunning: false,
        error: isOllamaDown
          ? 'Cannot connect to Ollama. Make sure Ollama is running and try again.'
          : msg,
      }))
    }
  }, [onComplete])

  const dismiss = useCallback(() => {
    setState((s) => ({ ...s, showModal: false }))
  }, [])

  return { ...state, start, dismiss }
}
