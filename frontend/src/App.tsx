import { useEffect, useState } from 'react'
import Header from '@/components/layout/Header'
import Sidebar from '@/components/layout/Sidebar'
import ContentPanel from '@/components/layout/ContentPanel'
import BriefingList from '@/components/briefings/BriefingList'
import ArticleList from '@/components/articles/ArticleList'
import BriefingOverview from '@/components/briefings/BriefingOverview'
import ArticleView from '@/components/articles/ArticleView'
import AnalysisSection from '@/components/articles/AnalysisSection'
import FeedbackControls from '@/components/feedback/FeedbackControls'
import PipelineProgress from '@/components/pipeline/PipelineProgress'
import { useBriefings } from '@/hooks/useBriefings'
import { useArticles } from '@/hooks/useArticles'
import { useArticle } from '@/hooks/useArticle'
import { useFeedback } from '@/hooks/useFeedback'
import { usePipelineRun } from '@/hooks/usePipelineRun'

export default function App() {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedArticle, setSelectedArticle] = useState<number | null>(null)

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

        <ContentPanel>
          {!selectedDate && (
            <p className="text-text-muted">Select a briefing date to get started.</p>
          )}
          {selectedDate && !selectedArticle && detail && (
            <BriefingOverview detail={detail} />
          )}
          {selectedDate && selectedArticle && (
            <>
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
            </>
          )}
        </ContentPanel>
      </div>
    </div>
  )
}
