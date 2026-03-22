import { useEffect, useState } from 'react'
import Header from '@/components/layout/Header'
import Sidebar from '@/components/layout/Sidebar'
import ContentPanel from '@/components/layout/ContentPanel'
import BriefingList from '@/components/briefings/BriefingList'
import ArticleList from '@/components/articles/ArticleList'
import BriefingOverview from '@/components/briefings/BriefingOverview'
import ArticleView from '@/components/articles/ArticleView'
import ArticleWebView from '@/components/articles/ArticleWebView'
import AnalysisSection from '@/components/articles/AnalysisSection'
import FeedbackControls from '@/components/feedback/FeedbackControls'
import PipelineProgress from '@/components/pipeline/PipelineProgress'
import { useBriefings } from '@/hooks/useBriefings'
import { useArticles } from '@/hooks/useArticles'
import { useArticle } from '@/hooks/useArticle'
import { useFeedback } from '@/hooks/useFeedback'
import { usePipelineRun } from '@/hooks/usePipelineRun'
import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

type ArticleViewMode = 'web' | 'analysis'

export default function App() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedArticle, setSelectedArticle] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<ArticleViewMode>('web')

  const { briefings, loading: briefingsLoading, refresh: refreshBriefings } = useBriefings()
  const { articles, detail, loading: articlesLoading } = useArticles(selectedDate)
  const { article, loading: articleLoading, error: articleError } = useArticle(selectedDate, selectedArticle)
  const { feedback, updateLocal: updateFeedbackLocal } = useFeedback(selectedDate)
  const pipeline = usePipelineRun(() => {
    refreshBriefings()
  })

  // Auto-select latest briefing date on first load
  useEffect(() => {
    if (!selectedDate && briefings.length > 0) {
      setSelectedDate(briefings[0].briefing_date)
    }
  }, [briefings, selectedDate])

  useEffect(() => {
    setViewMode('web')
  }, [selectedArticle])

  const handleSelectDate = (date: string) => {
    setSelectedDate(date)
    setSelectedArticle(null)
  }

  return (
    <div className="dark flex h-screen flex-col bg-bg-primary text-text-primary">
      <Header onRunClick={pipeline.start} isRunning={pipeline.isRunning} />
      <PipelineProgress state={pipeline} onDismiss={pipeline.dismiss} />

      <div className="flex min-h-0 flex-1">
        <Sidebar
          topSlot={
            <BriefingList
              briefings={briefings}
              selectedDate={selectedDate}
              onSelectDate={handleSelectDate}
              loading={briefingsLoading}
            />
          }
          bottomSlot={
            <ArticleList
              articles={articles}
              selectedArticle={selectedArticle}
              onSelectArticle={setSelectedArticle}
              feedback={feedback}
              loading={articlesLoading}
            />
          }
        />

        {!selectedDate && (
          <ContentPanel>
            <p className="text-text-muted">Select a briefing date to get started.</p>
          </ContentPanel>
        )}
        {selectedDate && !selectedArticle && detail && (
          <ContentPanel>
            <BriefingOverview detail={detail} />
          </ContentPanel>
        )}
        {selectedDate && selectedArticle && (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex shrink-0 gap-1 border-b border-white/[0.06] bg-bg-primary px-6 pt-3 md:px-8">
              <button
                type="button"
                onClick={() => setViewMode('web')}
                className={cn(
                  'rounded-t-lg px-4 py-2 text-sm font-medium transition-colors',
                  viewMode === 'web'
                    ? 'bg-bg-elevated text-text-primary shadow-sm'
                    : 'text-text-muted hover:bg-bg-hover hover:text-text-secondary',
                )}
              >
                Web
              </button>
              <button
                type="button"
                onClick={() => setViewMode('analysis')}
                className={cn(
                  'rounded-t-lg px-4 py-2 text-sm font-medium transition-colors',
                  viewMode === 'analysis'
                    ? 'bg-bg-elevated text-text-primary shadow-sm'
                    : 'text-text-muted hover:bg-bg-hover hover:text-text-secondary',
                )}
              >
                Analysis
              </button>
            </div>
            {viewMode === 'web' ? (
              <ContentPanel flush className="min-h-0">
                {articleLoading && (
                  <div className="flex flex-1 items-center justify-center gap-2 py-12 text-text-muted">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span>Loading article…</span>
                  </div>
                )}
                {articleError && (
                  <p className="p-8 text-danger">{articleError}</p>
                )}
                {article && !articleLoading && !articleError && (
                  <ArticleWebView url={article.url} title={article.title} />
                )}
              </ContentPanel>
            ) : (
              <ContentPanel className="min-h-0 overflow-y-auto">
                <ArticleView
                  article={article}
                  loading={articleLoading}
                  error={articleError}
                />
                {article && (
                  <>
                    <AnalysisSection
                      article={article}
                      defaultExpanded={!feedback.get(selectedArticle)?.read}
                    />
                    <FeedbackControls
                      date={selectedDate}
                      articleNumber={selectedArticle}
                      articleUrl={article.url}
                      feedback={feedback.get(selectedArticle)}
                      onUpdate={(patch) => updateFeedbackLocal(selectedArticle, patch)}
                    />
                  </>
                )}
              </ContentPanel>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
