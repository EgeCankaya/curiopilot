import { useEffect, useState } from 'react'
import { AppWindow, ExternalLink, Globe, Loader2, RotateCw } from 'lucide-react'
import { openReaderWindow } from '@/lib/api'

type ViewState = 'opening' | 'reader_ok' | 'failed' | 'inline'

const KNOWN_DIFFICULT_HOSTS = [
  'medium.com',
  'reddit.com',
  'twitter.com',
  'x.com',
  'facebook.com',
  'instagram.com',
  'linkedin.com',
]

function domainFromUrl(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}

function isDifficultHost(url: string): boolean {
  const hostname = domainFromUrl(url)
  return KNOWN_DIFFICULT_HOSTS.some(
    (h) => hostname === h || hostname.endsWith(`.${h}`),
  )
}

interface ArticleWebViewProps {
  url: string
  title: string
}

export default function ArticleWebView({ url, title }: ArticleWebViewProps) {
  const [state, setState] = useState<ViewState>('opening')
  const [failReason, setFailReason] = useState('')
  const [iframeLoading, setIframeLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setState('opening')
    setFailReason('')
    setIframeLoading(true)

    const tryOpen = async () => {
      const res = await openReaderWindow(url, title)
      if (cancelled) return
      if (res.opened) {
        setState('reader_ok')
      } else {
        setFailReason(res.reason)
        setState('failed')
      }
    }

    void tryOpen()
    return () => { cancelled = true }
  }, [url, title])

  const handleRetryReader = async () => {
    setState('opening')
    const res = await openReaderWindow(url, title)
    if (res.opened) {
      setState('reader_ok')
    } else {
      setFailReason(res.reason)
      setState('failed')
    }
  }

  const domain = domainFromUrl(url)
  const difficult = isDifficultHost(url)

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Toolbar */}
      <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-border bg-bg-elevated/60 px-4 py-2.5 text-sm">
        <span className="font-medium text-text-secondary" title={title}>
          {domain}
        </span>
        <span className="flex items-center gap-3 text-text-muted">
          <button
            type="button"
            onClick={handleRetryReader}
            className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
          >
            <AppWindow className="h-3.5 w-3.5" />
            Open in app window
          </button>
          <span className="text-border">|</span>
          <button
            type="button"
            onClick={() => setState('inline')}
            className="inline-flex items-center gap-1 font-medium text-text-muted underline-offset-2 hover:text-text-secondary hover:underline"
          >
            <Globe className="h-3.5 w-3.5" />
            Try inline
          </button>
          <span className="text-border">|</span>
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

      {/* Content area */}
      <div className="relative min-h-0 flex-1 bg-bg-primary">
        {state === 'opening' && (
          <div className="flex h-full items-center justify-center gap-2 text-text-muted">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span>Opening in reader window…</span>
          </div>
        )}

        {state === 'reader_ok' && (
          <div className="flex h-full items-center justify-center p-8 text-center">
            <div className="max-w-xl space-y-3 rounded-2xl border border-border bg-bg-elevated/60 p-6">
              <p className="text-sm text-text-secondary">
                Article opened in the reader window for full-site rendering.
              </p>
              <div className="flex items-center justify-center gap-3 text-sm">
                <button
                  type="button"
                  onClick={handleRetryReader}
                  className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
                >
                  <RotateCw className="h-3.5 w-3.5" />
                  Reopen reader
                </button>
                <span className="text-border">|</span>
                <button
                  type="button"
                  onClick={() => setState('inline')}
                  className="font-medium text-text-muted underline-offset-2 hover:text-text-secondary hover:underline"
                >
                  Try inline view
                </button>
              </div>
            </div>
          </div>
        )}

        {state === 'failed' && (
          <div className="flex h-full items-center justify-center p-8 text-center">
            <div className="max-w-xl space-y-4 rounded-2xl border border-warning/20 bg-warning/5 p-6">
              <div className="space-y-1">
                <p className="text-sm font-medium text-warning">
                  Could not open in app reader window
                </p>
                <p className="text-sm text-text-muted">
                  {failReason === 'bridge_unavailable'
                    ? 'Reader window is only available when running the desktop app.'
                    : `The reader window could not open this page (${failReason}).`}
                  {difficult && (
                    <>
                      {' '}
                      Note: <strong>{domain}</strong> is known to restrict
                      embedded/webview access — opening externally is
                      recommended.
                    </>
                  )}
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
                <button
                  type="button"
                  onClick={() =>
                    window.open(url, '_blank', 'noopener,noreferrer')
                  }
                  className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 font-medium text-white transition-all duration-200 hover:bg-accent-hover active:scale-[0.98]"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open externally
                </button>
                <button
                  type="button"
                  onClick={handleRetryReader}
                  className="inline-flex items-center gap-1 font-medium text-accent underline-offset-2 hover:underline"
                >
                  <RotateCw className="h-3.5 w-3.5" />
                  Retry in app window
                </button>
                <button
                  type="button"
                  onClick={() => setState('inline')}
                  className="font-medium text-text-muted underline-offset-2 hover:text-text-secondary hover:underline"
                >
                  Try inline iframe
                </button>
              </div>
            </div>
          </div>
        )}

        {state === 'inline' && (
          <>
            {iframeLoading && (
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
              onLoad={() => setIframeLoading(false)}
            />
          </>
        )}
      </div>
    </div>
  )
}
