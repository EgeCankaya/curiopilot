export interface BriefingListItem {
  briefing_date: string
  article_count: number
  has_feedback: boolean
}

export interface ArticleListItem {
  id: number
  article_number: number
  title: string
  source_name: string
  url: string
  summary: string
  novel_insights: string
  key_concepts: string[]
  related_topics: string[]
  relevance_score: number
  novelty_score: number
  graph_novelty: number
  vector_novelty: number
  novelty_explanation: string
  technical_depth: number
  is_deepening: boolean
  body_content_type: string
  created_at: string | null
}

export interface BriefingDetail {
  briefing_date: string
  articles: ArticleListItem[]
  articles_scanned: number | null
  articles_relevant: number | null
  articles_briefed: number | null
  pipeline_runtime: string | null
  new_concepts: string[]
  graph_stats: Record<string, unknown> | null
  explorations: string[]
}

export interface ArticleFull extends ArticleListItem {
  body_content: string
}

export interface FeedbackItem {
  briefing_date: string
  article_number: number
  title: string | null
  read: boolean | null
  interest: number | null
  quality: string | null
  processed_at: string | null
}

export interface FeedbackRequest {
  read?: boolean
  interest?: number
  quality?: string
}

export interface RunResponse {
  run_id: string
  status: string
}

export interface RunStatus {
  status: string
  run_id: string | null
  error: string | null
}

export interface StatsResponse {
  urls_visited: number
  urls_passed_relevance: number
  sources_seen: number
  article_embeddings: number
  graph_nodes: number
  graph_edges: number
  most_connected_topic: string | null
  most_connected_edges: number | null
}

export interface SearchResult {
  briefing_date: string
  article_number: number
  title: string
  source_name: string
  summary: string
  relevance_score: number
  novelty_score: number
}

export interface RunStreamEvent {
  event: 'started' | 'progress' | 'complete' | 'error'
  data: Record<string, unknown>
}
