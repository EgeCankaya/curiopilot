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

export function triggerRun(rerunDate?: string): Promise<RunResponse> {
  return fetchJSON(`${BASE}/run`, {
    method: 'POST',
    headers: rerunDate ? { 'Content-Type': 'application/json' } : undefined,
    body: rerunDate ? JSON.stringify({ rerun_date: rerunDate }) : undefined,
  })
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

export interface GraphNode {
  id: string
  label: string
  familiarity: number
  encounter_count: number
  degree: number
}

export interface GraphEdge {
  source: string
  target: string
  relationship_type: string
}

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
}

export function fetchGraph(maxNodes = 200): Promise<GraphResponse> {
  return fetchJSON(`${BASE}/graph?max_nodes=${maxNodes}`)
}

// ── Obsidian Integration ─────────────────────────────────────────────────────

export interface ObsidianStatus {
  vault_path: string
  configured: boolean
  total_concepts: number
  total_briefings: number
  category_summary: Record<string, number>
  last_exported: string | null
}

export interface ObsidianExportResult {
  exported_concepts: number
  exported_briefings: number
  vault_path: string
}

export function fetchObsidianStatus(): Promise<ObsidianStatus> {
  return fetchJSON(`${BASE}/obsidian/status`)
}

export function exportObsidianVault(vaultPath?: string): Promise<ObsidianExportResult> {
  return fetchJSON(`${BASE}/obsidian/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(vaultPath ? { vault_path: vaultPath } : {}),
  })
}

export function fetchConfig(): Promise<Record<string, unknown>> {
  return fetchJSON(`${BASE}/config`)
}

export function updateConfig(body: Record<string, unknown>): Promise<{ status: string }> {
  return fetchJSON(`${BASE}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export function fetchAvailableModels(): Promise<{ models: { name: string; size: number; modified_at: string }[] }> {
  return fetchJSON(`${BASE}/config/models`)
}

// ── Bookmarks & Collections ─────────────────────────────────────────────────

export interface Bookmark {
  id: number
  briefing_date: string
  article_number: number
  collection_id: number | null
  created_at: string
}

export interface Collection {
  id: number
  name: string
  created_at: string
}

export function fetchBookmarks(collectionId?: number): Promise<Bookmark[]> {
  const qs = collectionId != null ? `?collection_id=${collectionId}` : ''
  return fetchJSON(`${BASE}/bookmarks${qs}`)
}

export function addBookmark(briefing_date: string, article_number: number, collection_id?: number): Promise<{ status: string; id: number }> {
  return fetchJSON(`${BASE}/bookmarks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ briefing_date, article_number, collection_id: collection_id ?? null }),
  })
}

export function removeBookmark(date: string, number: number): Promise<{ status: string }> {
  return fetchJSON(`${BASE}/bookmarks/${date}/${number}`, { method: 'DELETE' })
}

export function checkBookmark(date: string, number: number): Promise<{ bookmarked: boolean }> {
  return fetchJSON(`${BASE}/bookmarks/check/${date}/${number}`)
}

export function fetchCollections(): Promise<Collection[]> {
  return fetchJSON(`${BASE}/collections`)
}

export function createCollection(name: string): Promise<{ status: string; id: number }> {
  return fetchJSON(`${BASE}/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
}

export function deleteCollection(id: number): Promise<{ status: string }> {
  return fetchJSON(`${BASE}/collections/${id}`, { method: 'DELETE' })
}

export type ReaderResult = {
  ok: boolean
  opened: boolean
  reason: string
}

export async function openReaderWindow(
  url: string,
  title?: string,
): Promise<ReaderResult> {
  try {
    return await fetchJSON(`${BASE}/ui/open-reader`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, title: title ?? null }),
    })
  } catch {
    return { ok: false, opened: false, reason: 'network_error' }
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
