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
import SearchBar from '@/components/search/SearchBar'
import StatsDashboard from '@/components/stats/StatsDashboard'
import ObsidianBridgePage from '@/components/graph/ObsidianBridgePage'
import SettingsPage from '@/components/settings/SettingsPage'
import ComparisonPage from '@/components/compare/ComparisonPage'
import DLQPanel from '@/components/dlq/DLQPanel'
import KeyboardShortcutsModal from '@/components/layout/KeyboardShortcutsModal'
import { useBookmarks } from '@/hooks/useBookmarks'
import { useBriefings } from '@/hooks/useBriefings'
import { useArticles } from '@/hooks/useArticles'
import { useArticle } from '@/hooks/useArticle'
import { useFeedback } from '@/hooks/useFeedback'
import { usePipelineRun } from '@/hooks/usePipelineRun'
import { useTheme } from '@/hooks/useTheme'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { useKeyboardNav } from '@/hooks/useKeyboardNav'
import { cn } from '@/lib/utils'
import { Loader2 } from 'lucide-react'

type ArticleViewMode = 'web' | 'analysis'
export type AppView = 'briefings' | 'stats' | 'graph' | 'settings' | 'compare' | 'dlq'

export default function App() {
  const [activeView, setActiveView] = useState<AppView>('briefings')
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [selectedArticle, setSelectedArticle] = useState<number | null>(null)
  const [viewMode, setViewMode] = useState<ArticleViewMode>('analysis')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)
  const { theme, setTheme } = useTheme()
  const isMobile = useMediaQuery('(max-width: 767px)')

  const { briefings, loading: briefingsLoading, refresh: refreshBriefings } = useBriefings()
  const { articles, detail, loading: articlesLoading } = useArticles(selectedDate)
  const { article, loading: articleLoading, error: articleError } = useArticle(selectedDate, selectedArticle)
  const { feedback, updateLocal: updateFeedbackLocal } = useFeedback(selectedDate)
  const pipeline = usePipelineRun(() => {
    refreshBriefings()
  })
  const bookmarksHook = useBookmarks()

  useKeyboardNav({
    articles,
    selectedArticle,
    onSelectArticle: setSelectedArticle,
    selectedDate,
    viewMode,
    onSetViewMode: setViewMode,
    feedback,
    onUpdateFeedback: updateFeedbackLocal,
    onTriggerRun: pipeline.start,
  })

  // '?' key opens keyboard shortcuts modal
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const el = document.activeElement
      const isInput = el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT')
      if (isInput) return
      if (e.key === '?') {
        e.preventDefault()
        setShortcutsOpen((o) => !o)
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  // Auto-select latest briefing date on first load
  useEffect(() => {
    if (!selectedDate && briefings.length > 0) {
      setSelectedDate(briefings[0].briefing_date)
    }
  }, [briefings, selectedDate])

  useEffect(() => {
    setViewMode('analysis')
  }, [selectedArticle])

  // Close sidebar on mobile when not needed
  useEffect(() => {
    if (isMobile) setSidebarOpen(false)
    else setSidebarOpen(true)
  }, [isMobile])

  const handleSelectDate = (date: string) => {
    setSelectedDate(date)
    setSelectedArticle(null)
    if (isMobile) setSidebarOpen(false)
  }

  const handleSelectArticle = (num: number) => {
    setSelectedArticle(num)
    if (isMobile) setSidebarOpen(false)
  }

  const handleSearchNavigate = (date: string, articleNumber: number) => {
    setActiveView('briefings')
    setSelectedDate(date)
    setSelectedArticle(articleNumber)
  }

  const renderMainContent = () => {
    // Full-page views (no sidebar)
    if (activeView === 'stats') {
      return (
        <ContentPanel className="overflow-y-auto">
          <StatsDashboard />
        </ContentPanel>
      )
    }

    if (activeView === 'graph') {
      return <ObsidianBridgePage />
    }

    if (activeView === 'settings') {
      return (
        <ContentPanel className="overflow-y-auto">
          <SettingsPage />
        </ContentPanel>
      )
    }

    if (activeView === 'compare') {
      return (
        <ContentPanel className="overflow-y-auto">
          <ComparisonPage />
        </ContentPanel>
      )
    }

    if (activeView === 'dlq') {
      return (
        <ContentPanel className="overflow-y-auto">
          <DLQPanel />
        </ContentPanel>
      )
    }

    // Default: briefings view with sidebar
    return (
      <>
        <Sidebar
          open={sidebarOpen}
          isMobile={isMobile}
          onClose={() => setSidebarOpen(false)}
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
              onSelectArticle={handleSelectArticle}
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
            <BriefingOverview
              detail={detail}
              onRerun={pipeline.rerun}
              isRunning={pipeline.isRunning}
            />
          </ContentPanel>
        )}
        {selectedDate && selectedArticle && (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex shrink-0 gap-1 border-b border-border bg-bg-primary px-6 pt-3 md:px-8">
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
                  bookmarked={selectedDate && selectedArticle ? bookmarksHook.isBookmarked(selectedDate, selectedArticle) : false}
                  onToggleBookmark={selectedDate && selectedArticle ? () => bookmarksHook.toggle(selectedDate, selectedArticle) : undefined}
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
      </>
    )
  }

  return (
    <div className="flex h-screen flex-col bg-bg-primary text-text-primary">
      <Header
        onRunClick={pipeline.start}
        isRunning={pipeline.isRunning}
        theme={theme}
        onThemeChange={setTheme}
        isMobile={isMobile}
        onToggleSidebar={() => setSidebarOpen((o) => !o)}
        activeView={activeView}
        onViewChange={setActiveView}
      >
        <SearchBar onNavigate={handleSearchNavigate} />
      </Header>
      <PipelineProgress state={pipeline} onDismiss={pipeline.dismiss} />
      <KeyboardShortcutsModal open={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />

      <div className="flex min-h-0 flex-1">
        {renderMainContent()}
      </div>
    </div>
  )
}
