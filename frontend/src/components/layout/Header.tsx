import { Sun, Moon, Monitor, Menu, BarChart3, BookOpen, Network, Settings, GitCompareArrows, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { AppView } from '@/App'

type Theme = 'dark' | 'light' | 'system'

interface HeaderProps {
  onRunClick?: () => void
  isRunning?: boolean
  theme?: Theme
  onThemeChange?: (theme: Theme) => void
  isMobile?: boolean
  onToggleSidebar?: () => void
  activeView?: AppView
  onViewChange?: (view: AppView) => void
  children?: React.ReactNode
}

const themeOptions: { value: Theme; icon: typeof Sun; label: string }[] = [
  { value: 'dark', icon: Moon, label: 'Dark' },
  { value: 'light', icon: Sun, label: 'Light' },
  { value: 'system', icon: Monitor, label: 'System' },
]

const navItems: { view: AppView; icon: typeof BarChart3; label: string }[] = [
  { view: 'briefings', icon: BookOpen, label: 'Briefings' },
  { view: 'stats', icon: BarChart3, label: 'Stats' },
  { view: 'graph', icon: Network, label: 'Graph' },
  { view: 'settings', icon: Settings, label: 'Settings' },
  { view: 'compare', icon: GitCompareArrows, label: 'Compare' },
  { view: 'dlq', icon: AlertTriangle, label: 'DLQ' },
]

export default function Header({
  onRunClick,
  isRunning,
  theme = 'dark',
  onThemeChange,
  isMobile,
  onToggleSidebar,
  activeView = 'briefings',
  onViewChange,
  children,
}: HeaderProps) {
  const cycleTheme = () => {
    const order: Theme[] = ['dark', 'light', 'system']
    const next = order[(order.indexOf(theme) + 1) % order.length]
    onThemeChange?.(next)
  }

  const current = themeOptions.find((o) => o.value === theme) ?? themeOptions[0]
  const ThemeIcon = current.icon

  return (
    <header className="flex h-14 shrink-0 items-center justify-between bg-bg-secondary/80 px-3 shadow-sm backdrop-blur-xl sm:px-5">
      <div className="flex items-center gap-2">
        {isMobile && activeView === 'briefings' && (
          <button
            onClick={onToggleSidebar}
            className="rounded-xl p-2 text-text-muted transition-all duration-200 hover:bg-bg-hover hover:text-text-primary"
          >
            <Menu className="h-5 w-5" />
          </button>
        )}
        <img
          src="/curiopilot-icon-512.png"
          alt=""
          aria-hidden="true"
          className="h-7 w-7 rounded-md object-cover"
        />
        <h1 className="text-lg font-semibold tracking-tight text-accent">
          CurioPilot
        </h1>
        {/* Nav items */}
        <nav className="ml-4 hidden items-center gap-1 sm:flex">
          {navItems.map(({ view, icon: Icon, label }) => (
            <button
              key={view}
              onClick={() => onViewChange?.(view)}
              title={label}
              className={cn(
                'rounded-xl px-3 py-1.5 text-xs font-medium transition-all duration-200',
                activeView === view
                  ? 'bg-accent/15 text-accent'
                  : 'text-text-muted hover:bg-bg-hover hover:text-text-primary',
              )}
            >
              <span className="flex items-center gap-1.5">
                <Icon className="h-3.5 w-3.5" />
                {label}
              </span>
            </button>
          ))}
        </nav>
      </div>
      {children}
      <div className="flex items-center gap-2">
        {/* Mobile nav */}
        {isMobile && (
          <nav className="flex items-center gap-1">
            {navItems.map(({ view, icon: Icon, label }) => (
              <button
                key={view}
                onClick={() => onViewChange?.(view)}
                title={label}
                className={cn(
                  'rounded-xl p-2 transition-all duration-200',
                  activeView === view
                    ? 'text-accent'
                    : 'text-text-muted hover:bg-bg-hover hover:text-text-primary',
                )}
              >
                <Icon className="h-4 w-4" />
              </button>
            ))}
          </nav>
        )}
        <button
          onClick={cycleTheme}
          title={`Theme: ${current.label}`}
          className={cn(
            'rounded-xl p-2 text-text-muted transition-all duration-200',
            'hover:bg-bg-hover hover:text-text-primary',
          )}
        >
          <ThemeIcon className="h-4 w-4" />
        </button>
        <button
          onClick={onRunClick}
          disabled={!onRunClick || isRunning}
          className="rounded-xl bg-accent/15 px-4 py-1.5 text-sm font-medium text-accent transition-all duration-200 hover:bg-accent/25 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isRunning ? 'Running\u2026' : 'Run Now'}
        </button>
      </div>
    </header>
  )
}
