import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import DOMPurify from 'dompurify'

interface ArticleBodyProps {
  content: string
  contentType: string
}

function PlaintextBody({ content }: { content: string }) {
  const paragraphs = content.split(/\n{2,}/)
  return (
    <div className="space-y-4">
      {paragraphs.map((p, i) => {
        const trimmed = p.trim()
        if (!trimmed) return null
        const lines = trimmed.split('\n')
        return (
          <p key={i} className="leading-relaxed">
            {lines.map((line, j) => (
              <span key={j}>
                {j > 0 && <br />}
                {line}
              </span>
            ))}
          </p>
        )
      })}
    </div>
  )
}

function MarkdownBody({ content }: { content: string }) {
  return (
    <Markdown remarkPlugins={[remarkGfm]}>
      {content}
    </Markdown>
  )
}

function HtmlBody({ content }: { content: string }) {
  const clean = DOMPurify.sanitize(content, {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['target'],
  })
  return <div dangerouslySetInnerHTML={{ __html: clean }} />
}

export default function ArticleBody({ content, contentType }: ArticleBodyProps) {
  if (!content) return null

  return (
    <div className="prose prose-invert prose-slate max-w-none prose-headings:text-text-primary prose-p:text-text-secondary prose-a:text-accent prose-strong:text-text-primary prose-code:text-accent prose-pre:bg-bg-tertiary text-base leading-[1.7]">
      {contentType === 'markdown' && <MarkdownBody content={content} />}
      {contentType === 'html' && <HtmlBody content={content} />}
      {(contentType === 'plaintext' || (contentType !== 'markdown' && contentType !== 'html')) && (
        <PlaintextBody content={content} />
      )}
    </div>
  )
}
