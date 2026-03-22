import type {
  ArticleFull,
  BriefingDetail,
  BriefingListItem,
  FeedbackItem,
  FeedbackRequest,
  RunResponse,
  RunStatus,
  RunStreamEvent,
  SearchResult,
  StatsResponse,
} from '@/types'

const BASE = '/api'

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export function fetchBriefings(): Promise<BriefingListItem[]> {
  return fetchJSON(`${BASE}/briefings`)
}

export function fetchBriefing(date: string): Promise<BriefingDetail> {
  return fetchJSON(`${BASE}/briefings/${date}`)
}

export function fetchArticle(date: string, number: number): Promise<ArticleFull> {
  return fetchJSON(`${BASE}/briefings/${date}/articles/${number}`)
}

export function fetchFeedback(date: string): Promise<FeedbackItem[]> {
  return fetchJSON(`${BASE}/briefings/${date}/feedback`)
}

export function submitFeedback(
  date: string,
  number: number,
  data: FeedbackRequest,
): Promise<{ status: string }> {
  return fetchJSON(`${BASE}/briefings/${date}/articles/${number}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export function triggerRun(): Promise<RunResponse> {
  return fetchJSON(`${BASE}/run`, { method: 'POST' })
}

export function fetchRunStatus(): Promise<RunStatus> {
  return fetchJSON(`${BASE}/run/status`)
}

export function fetchStats(): Promise<StatsResponse> {
  return fetchJSON(`${BASE}/stats`)
}

export function searchArticles(query: string): Promise<SearchResult[]> {
  return fetchJSON(`${BASE}/search?q=${encodeURIComponent(query)}`)
}

export async function openReaderWindow(
  url: string,
  title?: string,
): Promise<{ ok: boolean; opened: boolean }> {
  try {
    return await fetchJSON(`${BASE}/ui/open-reader`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, title: title ?? null }),
    })
  } catch {
    return { ok: false, opened: false }
  }
}

export function connectRunStream(
  onEvent: (event: RunStreamEvent) => void,
  onError?: (err: Event) => void,
): EventSource {
  const es = new EventSource(`${BASE}/run/stream`)

  const handleEvent = (type: RunStreamEvent['event']) => (e: MessageEvent) => {
    onEvent({ event: type, data: JSON.parse(e.data) })
  }

  es.addEventListener('started', handleEvent('started'))
  es.addEventListener('progress', handleEvent('progress'))
  es.addEventListener('complete', handleEvent('complete'))
  es.addEventListener('error', handleEvent('error'))

  es.onerror = (e) => {
    onError?.(e)
    es.close()
  }

  return es
}
