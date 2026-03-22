import { useEffect, useState } from 'react'
import { AppWindow, ExternalLink, Loader2 } from 'lucide-react'
import { openReaderWindow } from '@/lib/api'

function domainFromUrl(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

interface ArticleWebViewProps {
  url: string
  title: string
}

export default function ArticleWebView({ url, title }: ArticleWebViewProps) {
  const [loading, setLoading] = useState(true)
  const [openedInReader, setOpenedInReader] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setOpenedInReader(false)

    const tryOpenReaderWindow = async () => {
      const res = await openReaderWindow(url, title)
      if (cancelled) return
      if (res.opened) {
        setOpenedInReader(true)
        setLoading(false)
      }
    }

    void tryOpenReaderWindow()

    return () => {
      cancelled = true
    }
  }, [url, title])

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-white/[0.06] bg-bg-elevated/60 px-4 py-2.5 text-sm">
        <span className="font-medium text-text-secondary" title={title}>
          {domainFromUrl(url)}
        </span>
        <span className="flex items-center gap-3 text-text-muted">
          <button
            type="button"
            onClick={async () => {
              const res = await openReaderWindow(url, title)
              if (!res.opened) {
                window.open(url, '_blank', 'noopener,noreferrer')
                return
              }
              setOpenedInReader(true)
              setLoading(false)
            }}
            className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
          >
            <AppWindow className="h-3.5 w-3.5" />
            Open in app window
          </button>
          <span className="text-white/10">|</span>
          <button
            type="button"
            onClick={() => window.open(url, '_blank', 'noopener,noreferrer')}
            className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
          >
            Open externally
            <ExternalLink className="h-3.5 w-3.5" />
          </button>
        </span>
      </div>

      <div className="relative min-h-0 flex-1 bg-bg-primary">
        {openedInReader ? (
          <div className="flex h-full items-center justify-center p-8 text-center">
            <div className="max-w-xl space-y-3 rounded-2xl border border-white/[0.08] bg-bg-elevated/60 p-6">
              <p className="text-sm text-text-secondary">
                Opened this article in the app reader window for full-site rendering.
              </p>
              <div className="flex items-center justify-center gap-3 text-sm">
                <button
                  type="button"
                  onClick={async () => {
                    const res = await openReaderWindow(url, title)
                    if (!res.opened) {
                      window.open(url, '_blank', 'noopener,noreferrer')
                    }
                  }}
                  className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
                >
                  <AppWindow className="h-3.5 w-3.5" />
                  Reopen reader window
                </button>
                <span className="text-white/10">|</span>
                <button
                  type="button"
                  onClick={() => setOpenedInReader(false)}
                  className="font-medium text-text-muted underline-offset-2 hover:text-text-secondary hover:underline"
                >
                  Try inline view
                </button>
              </div>
            </div>
          </div>
        ) : (
          <>
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center gap-2 bg-bg-primary/80 text-text-muted backdrop-blur-sm">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Loading page…</span>
          </div>
        )}
        <iframe
          key={url}
          src={url}
          title={title}
          className="h-full min-h-[50vh] w-full border-0 bg-white"
          sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
          onLoad={() => setLoading(false)}
        />
          </>
        )}
      </div>
    </div>
  )
}
