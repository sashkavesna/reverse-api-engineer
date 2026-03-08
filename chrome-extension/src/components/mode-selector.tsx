import type { AppMode } from '../shared/types'

interface ModeSelectorProps {
  mode: AppMode
  onModeChange: (mode: AppMode) => void
  disabled?: boolean
}

export function ModeSelector({ mode, onModeChange, disabled }: ModeSelectorProps) {
  return (
    <div className="flex items-center justify-center gap-1">
      <button
        onClick={() => onModeChange('capture')}
        disabled={disabled}
        className={`px-3 py-1 text-[16px] leading-relaxed font-normal rounded-md transition-all duration-150 cursor-pointer ${
          mode === 'capture'
            ? 'text-capture'
            : 'text-white/50 hover:text-white/80'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        aria-label="Switch to Capture mode"
      >
        Capture
      </button>
      <div className="w-px h-3 bg-border" />
      <button
        onClick={() => onModeChange('codegen')}
        disabled={disabled}
        className={`px-3 py-1 text-[16px] leading-relaxed font-normal rounded-md transition-all duration-150 cursor-pointer ${
          mode === 'codegen'
            ? 'text-codegen'
            : 'text-white/50 hover:text-white/80'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        aria-label="Switch to Codegen mode"
      >
        Codegen
      </button>
    </div>
  )
}
