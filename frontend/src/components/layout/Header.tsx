import { Compass } from 'lucide-react'

interface HeaderProps {
  onRunClick?: () => void
  isRunning?: boolean
}

export default function Header({ onRunClick, isRunning }: HeaderProps) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between bg-bg-secondary/80 px-5 shadow-sm backdrop-blur-xl">
      <div className="flex items-center gap-2.5">
        <Compass className="h-5 w-5 text-accent" />
        <h1 className="text-lg font-semibold tracking-tight text-accent">
          CurioPilot
        </h1>
      </div>
      <button
        onClick={onRunClick}
        disabled={!onRunClick || isRunning}
        className="rounded-xl bg-accent/15 px-4 py-1.5 text-sm font-medium text-accent transition-all duration-200 hover:bg-accent/25 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isRunning ? 'Running…' : 'Run Now'}
      </button>
    </header>
  )
}
