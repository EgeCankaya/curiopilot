import { useState } from 'react'
import type { ArticleFull } from '@/types'
import { ChevronDown, ChevronRight, Lightbulb, Sparkles, Tag, Link2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface AnalysisSectionProps {
  article: ArticleFull
  defaultExpanded?: boolean
}

export default function AnalysisSection({ article, defaultExpanded = true }: AnalysisSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  return (
    <section className="mt-6 rounded-2xl border border-border bg-bg-elevated shadow-md shadow-border-subtle/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-5 py-3.5 text-left text-sm font-medium text-text-secondary transition-all duration-200 hover:text-text-primary"
      >
        <div className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent" />
          <span>AI Analysis</span>
        </div>
        {expanded
          ? <ChevronDown className="h-4 w-4" />
          : <ChevronRight className="h-4 w-4" />
        }
      </button>

      {expanded && (
        <div className="space-y-4 border-t border-border px-5 pb-5 pt-4">
          {/* Summary */}
          <div>
            <h4 className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
              <Lightbulb className="h-3.5 w-3.5" />
              Summary
            </h4>
            <p className="text-sm leading-relaxed text-text-secondary">{article.summary}</p>
          </div>

          {/* Novel Insights */}
          {article.novel_insights && (
            <div>
              <h4 className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
                <Sparkles className="h-3.5 w-3.5" />
                Novel Insights
              </h4>
              <p className="text-sm leading-relaxed text-text-secondary">{article.novel_insights}</p>
            </div>
          )}

          {/* Key Concepts */}
          {article.key_concepts.length > 0 && (
            <div>
              <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
                <Tag className="h-3.5 w-3.5" />
                Key Concepts
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {article.key_concepts.map((concept) => (
                  <span
                    key={concept}
                    className="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent"
                  >
                    {concept}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Related Topics */}
          {article.related_topics.length > 0 && (
            <div>
              <h4 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
                <Link2 className="h-3.5 w-3.5" />
                Related Topics
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {article.related_topics.map((topic) => (
                  <span
                    key={topic}
                    className={cn(
                      'rounded-full bg-bg-tertiary px-2.5 py-0.5 text-xs text-text-muted',
                    )}
                  >
                    {topic}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
