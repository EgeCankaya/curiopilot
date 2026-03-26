import { useState } from 'react'
import { useConfig } from '@/hooks/useConfig'
import { Loader2, AlertCircle, Check, X, Plus, Save, Mail } from 'lucide-react'
import { sendTestEmail } from '@/lib/api'
import { cn } from '@/lib/utils'

type Tab = 'interests' | 'sources' | 'scoring' | 'models' | 'email'

export default function SettingsPage() {
  const { config, loading, error, saving, saveError, save, models } = useConfig()
  const [tab, setTab] = useState<Tab>('interests')
  const [draft, setDraft] = useState<Record<string, unknown> | null>(null)

  // Initialize draft from config
  if (config && !draft) {
    setDraft(JSON.parse(JSON.stringify(config)))
    return null
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-text-muted">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading settings...
      </div>
    )
  }
  if (error || !draft) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-danger">
        <AlertCircle className="h-5 w-5" /> {error ?? 'No config available'}
      </div>
    )
  }

  const interests = draft.interests as { primary: string[]; secondary: string[]; excluded: string[] }
  const sources = draft.sources as { name: string; scraper: string; url?: string; max_articles: number }[]
  const scoring = draft.scoring as Record<string, number>
  const modelsCfg = draft.models as { filter_model: string; reader_model: string; embedding_model: string }
  const emailCfg = (draft.email as { enabled: boolean; smtp_host: string; smtp_port: number; sender_email: string; recipient_email: string } | undefined)
    ?? { enabled: false, smtp_host: 'smtp.gmail.com', smtp_port: 587, sender_email: '', recipient_email: 'egemencankaya14@gmail.com' }

  const handleSave = () => {
    const patch: Record<string, unknown> = {}
    if (tab === 'interests') patch.interests = interests
    else if (tab === 'sources') patch.sources = sources
    else if (tab === 'scoring') patch.scoring = scoring
    else if (tab === 'models') patch.models = modelsCfg
    else if (tab === 'email') patch.email = emailCfg
    save(patch)
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'interests', label: 'Interests' },
    { id: 'sources', label: 'Sources' },
    { id: 'scoring', label: 'Scoring' },
    { id: 'models', label: 'Models' },
    { id: 'email', label: 'Email' },
  ]

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6 md:p-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Settings</h2>
          <p className="mt-1 text-sm text-text-secondary">Configure your CurioPilot instance</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition-all duration-200 hover:bg-accent-hover active:scale-[0.98] disabled:opacity-50"
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          Save
        </button>
      </div>

      {saveError && (
        <div className="rounded-xl bg-danger/10 px-4 py-2 text-sm text-danger">{saveError}</div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={cn(
              'rounded-t-lg px-4 py-2 text-sm font-medium transition-colors',
              tab === t.id
                ? 'bg-bg-elevated text-text-primary'
                : 'text-text-muted hover:text-text-secondary',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'interests' && (
        <InterestsTab interests={interests} onChange={(i) => setDraft({ ...draft, interests: i })} />
      )}
      {tab === 'sources' && (
        <SourcesTab sources={sources} onChange={(s) => setDraft({ ...draft, sources: s })} />
      )}
      {tab === 'scoring' && (
        <ScoringTab scoring={scoring} onChange={(s) => setDraft({ ...draft, scoring: s })} />
      )}
      {tab === 'models' && (
        <ModelsTab models={modelsCfg} available={models} onChange={(m) => setDraft({ ...draft, models: m })} />
      )}
      {tab === 'email' && (
        <EmailTab email={emailCfg} onChange={(e) => setDraft({ ...draft, email: e })} />
      )}
    </div>
  )
}

// ── Interest Settings ────────────────────────────────────────────────────────

function InterestsTab({
  interests,
  onChange,
}: {
  interests: { primary: string[]; secondary: string[]; excluded: string[] }
  onChange: (i: typeof interests) => void
}) {
  const [newItem, setNewItem] = useState({ primary: '', secondary: '', excluded: '' })

  const addItem = (key: 'primary' | 'secondary' | 'excluded') => {
    const val = newItem[key].trim()
    if (!val || interests[key].includes(val)) return
    onChange({ ...interests, [key]: [...interests[key], val] })
    setNewItem({ ...newItem, [key]: '' })
  }

  const removeItem = (key: 'primary' | 'secondary' | 'excluded', idx: number) => {
    onChange({ ...interests, [key]: interests[key].filter((_, i) => i !== idx) })
  }

  const sections: { key: 'primary' | 'secondary' | 'excluded'; label: string; color: string }[] = [
    { key: 'primary', label: 'Primary Interests', color: 'bg-accent/10 text-accent' },
    { key: 'secondary', label: 'Secondary Interests', color: 'bg-success/10 text-success' },
    { key: 'excluded', label: 'Excluded Topics', color: 'bg-danger/10 text-danger' },
  ]

  return (
    <div className="space-y-6">
      {sections.map(({ key, label, color }) => (
        <div key={key}>
          <h4 className="mb-2 text-sm font-semibold text-text-secondary">{label}</h4>
          <div className="flex flex-wrap gap-2">
            {interests[key].map((item, idx) => (
              <span key={item} className={cn('inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm', color)}>
                {item}
                <button onClick={() => removeItem(key, idx)} className="ml-1 opacity-60 hover:opacity-100">
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <input
              value={newItem[key]}
              onChange={(e) => setNewItem({ ...newItem, [key]: e.target.value })}
              onKeyDown={(e) => e.key === 'Enter' && addItem(key)}
              placeholder={`Add ${key} interest...`}
              className="rounded-xl bg-bg-tertiary px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
            <button onClick={() => addItem(key)} className="rounded-xl bg-bg-tertiary p-2 text-text-muted hover:text-text-primary">
              <Plus className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Sources Settings ─────────────────────────────────────────────────────────

function SourcesTab({
  sources,
  onChange,
}: {
  sources: { name: string; scraper: string; url?: string; max_articles: number }[]
  onChange: (s: typeof sources) => void
}) {
  const updateSource = (idx: number, field: string, value: unknown) => {
    const updated = [...sources]
    updated[idx] = { ...updated[idx], [field]: value }
    onChange(updated)
  }

  return (
    <div className="space-y-3">
      {sources.map((s, idx) => (
        <div key={s.name} className="rounded-2xl bg-bg-elevated p-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="font-medium text-text-primary">{s.name}</span>
              <span className="ml-2 rounded bg-bg-tertiary px-2 py-0.5 text-xs text-text-muted">{s.scraper}</span>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-text-muted">Max articles:</label>
              <input
                type="number"
                value={s.max_articles}
                onChange={(e) => updateSource(idx, 'max_articles', parseInt(e.target.value) || 1)}
                min={1}
                max={100}
                className="w-16 rounded-lg bg-bg-tertiary px-2 py-1 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/40"
              />
            </div>
          </div>
          {s.url && <p className="mt-1 truncate text-xs text-text-muted">{s.url}</p>}
        </div>
      ))}
    </div>
  )
}

// ── Scoring Settings ─────────────────────────────────────────────────────────

function ScoringTab({
  scoring,
  onChange,
}: {
  scoring: Record<string, number>
  onChange: (s: Record<string, number>) => void
}) {
  const sliders: { key: string; label: string; min: number; max: number; step: number }[] = [
    { key: 'relevance_threshold', label: 'Relevance Threshold', min: 0, max: 10, step: 1 },
    { key: 'min_briefing_items', label: 'Min Briefing Items', min: 0, max: 30, step: 1 },
    { key: 'max_briefing_items', label: 'Max Briefing Items', min: 1, max: 30, step: 1 },
    { key: 'near_duplicate_threshold', label: 'Near-Duplicate Threshold', min: 0, max: 1, step: 0.01 },
    { key: 'dedup_window_days', label: 'Dedup Window (days)', min: 1, max: 90, step: 1 },
    { key: 'briefed_dedup_window_days', label: 'Briefed Dedup Window (days)', min: 7, max: 365, step: 1 },
  ]

  // Linked weight slider
  const noveltyWeight = scoring.novelty_weight ?? 0.6
  const handleWeightChange = (nw: number) => {
    onChange({ ...scoring, novelty_weight: nw, relevance_weight: Math.round((1 - nw) * 100) / 100 })
  }
  const vecWeight = scoring.vector_novelty_weight ?? 0.5
  const handleVecWeightChange = (vw: number) => {
    onChange({ ...scoring, vector_novelty_weight: vw, graph_novelty_weight: Math.round((1 - vw) * 100) / 100 })
  }

  return (
    <div className="space-y-6">
      {/* Linked: Novelty vs Relevance weight */}
      <div>
        <div className="flex justify-between text-sm">
          <span className="text-text-secondary">Novelty Weight: {noveltyWeight.toFixed(2)}</span>
          <span className="text-text-muted">Relevance: {(1 - noveltyWeight).toFixed(2)}</span>
        </div>
        <input
          type="range"
          min={0} max={1} step={0.05}
          value={noveltyWeight}
          onChange={(e) => handleWeightChange(parseFloat(e.target.value))}
          className="mt-1 w-full accent-accent"
        />
      </div>
      {/* Linked: Vector vs Graph novelty */}
      <div>
        <div className="flex justify-between text-sm">
          <span className="text-text-secondary">Vector Novelty: {vecWeight.toFixed(2)}</span>
          <span className="text-text-muted">Graph Novelty: {(1 - vecWeight).toFixed(2)}</span>
        </div>
        <input
          type="range"
          min={0} max={1} step={0.05}
          value={vecWeight}
          onChange={(e) => handleVecWeightChange(parseFloat(e.target.value))}
          className="mt-1 w-full accent-accent"
        />
      </div>
      {/* Standard sliders */}
      {sliders.map(({ key, label, min, max, step }) => (
        <div key={key}>
          <div className="flex justify-between text-sm">
            <span className="text-text-secondary">{label}</span>
            <span className="text-text-muted">{scoring[key]}</span>
          </div>
          <input
            type="range"
            min={min} max={max} step={step}
            value={scoring[key] ?? 0}
            onChange={(e) => onChange({ ...scoring, [key]: parseFloat(e.target.value) })}
            className="mt-1 w-full accent-accent"
          />
        </div>
      ))}
    </div>
  )
}

// ── Model Settings ───────────────────────────────────────────────────────────

function ModelsTab({
  models,
  available,
  onChange,
}: {
  models: { filter_model: string; reader_model: string; embedding_model: string }
  available: { name: string; size: number }[]
  onChange: (m: typeof models) => void
}) {
  const fields: { key: keyof typeof models; label: string }[] = [
    { key: 'filter_model', label: 'Filter Model (7B recommended)' },
    { key: 'reader_model', label: 'Reader Model (14B recommended)' },
    { key: 'embedding_model', label: 'Embedding Model' },
  ]

  return (
    <div className="space-y-4">
      {available.length === 0 && (
        <div className="rounded-xl bg-warning/10 px-4 py-2 text-sm text-warning">
          Could not reach Ollama. Showing current model names only.
        </div>
      )}
      {fields.map(({ key, label }) => (
        <div key={key}>
          <label className="mb-1 block text-sm font-medium text-text-secondary">{label}</label>
          {available.length > 0 ? (
            <select
              value={models[key]}
              onChange={(e) => onChange({ ...models, [key]: e.target.value })}
              className="w-full rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/40"
            >
              {available.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name} ({(m.size / 1e9).toFixed(1)}GB)
                </option>
              ))}
            </select>
          ) : (
            <input
              value={models[key]}
              onChange={(e) => onChange({ ...models, [key]: e.target.value })}
              className="w-full rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          )}
        </div>
      ))}
    </div>
  )
}

// ── Email Settings ──────────────────────────────────────────────────────────

function EmailTab({
  email,
  onChange,
}: {
  email: { enabled: boolean; smtp_host: string; smtp_port: number; sender_email: string; recipient_email: string }
  onChange: (e: typeof email) => void
}) {
  const [testPassword, setTestPassword] = useState('')
  const [testStatus, setTestStatus] = useState<{ status: string; detail: string } | null>(null)
  const [testing, setTesting] = useState(false)

  const handleTest = async () => {
    if (!testPassword) return
    setTesting(true)
    setTestStatus(null)
    try {
      const result = await sendTestEmail({
        password: testPassword,
        recipient_email: email.recipient_email,
      })
      setTestStatus(result)
    } catch (e) {
      setTestStatus({ status: 'failed', detail: e instanceof Error ? e.message : 'Unknown error' })
    } finally {
      setTesting(false)
    }
  }

  const inputClass = 'w-full rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/40'

  return (
    <div className="space-y-6">
      {/* Enable toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={() => onChange({ ...email, enabled: !email.enabled })}
          className={cn(
            'relative h-6 w-11 rounded-full transition-colors',
            email.enabled ? 'bg-accent' : 'bg-bg-tertiary',
          )}
        >
          <span
            className={cn(
              'absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white transition-transform',
              email.enabled && 'translate-x-5',
            )}
          />
        </button>
        <span className="text-sm font-medium text-text-primary">
          Send email digest after pipeline runs
        </span>
      </div>

      {/* SMTP Host */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-secondary">SMTP Host</label>
        <input
          value={email.smtp_host}
          onChange={(e) => onChange({ ...email, smtp_host: e.target.value })}
          className={inputClass}
        />
      </div>

      {/* SMTP Port */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-secondary">SMTP Port</label>
        <input
          type="number"
          value={email.smtp_port}
          onChange={(e) => onChange({ ...email, smtp_port: parseInt(e.target.value) || 587 })}
          min={1}
          max={65535}
          className={inputClass}
        />
      </div>

      {/* Sender Email */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-secondary">Sender Email</label>
        <input
          type="email"
          value={email.sender_email}
          onChange={(e) => onChange({ ...email, sender_email: e.target.value })}
          placeholder="your-email@gmail.com"
          className={inputClass}
        />
      </div>

      {/* Recipient Email */}
      <div>
        <label className="mb-1 block text-sm font-medium text-text-secondary">Recipient Email</label>
        <input
          type="email"
          value={email.recipient_email}
          onChange={(e) => onChange({ ...email, recipient_email: e.target.value })}
          className={inputClass}
        />
      </div>

      {/* Test Email Section */}
      <div className="rounded-2xl bg-bg-elevated p-4 space-y-3">
        <p className="text-xs text-text-muted">
          The SMTP password is read from the <code className="rounded bg-bg-tertiary px-1.5 py-0.5 text-text-secondary">CURIOPILOT_SMTP_PASSWORD</code> environment
          variable at runtime. Enter your Gmail App Password below to send a test email.
        </p>
        <input
          type="password"
          placeholder="Gmail App Password"
          value={testPassword}
          onChange={(e) => setTestPassword(e.target.value)}
          className={inputClass}
        />
        <button
          type="button"
          onClick={handleTest}
          disabled={testing || !testPassword || !email.sender_email}
          className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition-all duration-200 hover:bg-accent-hover active:scale-[0.98] disabled:opacity-50"
        >
          {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
          Send Test Email
        </button>
        {testStatus && (
          <div
            className={cn(
              'rounded-xl px-4 py-2 text-sm',
              testStatus.status === 'sent' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger',
            )}
          >
            {testStatus.detail}
          </div>
        )}
      </div>
    </div>
  )
}
