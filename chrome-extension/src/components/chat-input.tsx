import { useRef, useEffect, useState } from 'react'
import type { AppMode } from '../shared/types'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: (message: string) => void
  isStreaming: boolean
  placeholder: string
  mode: AppMode
  onModeChange?: (mode: AppMode) => void
  modeDisabled?: boolean
}

export function ChatInput({ value, onChange, onSend, isStreaming, placeholder, mode }: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [isFocused, setIsFocused] = useState(false)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [value])

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim() && !isStreaming) {
        onSend(value.trim())
      }
    }
  }

  const handleSend = () => {
    if (value.trim() && !isStreaming) {
      onSend(value.trim())
    }
  }

  const handleContainerClick = () => {
    textareaRef.current?.focus()
  }

  const hasContent = value.trim().length > 0

  return (
    <div className="p-3">
      <div
        onClick={handleContainerClick}
        className={`
          flex min-h-[120px] flex-col rounded-3xl cursor-text
          bg-card transition-all duration-200
          border ${isFocused ? 'border-capture ring-1 ring-capture/30' : 'border-capture/30'}
        `}
      >
        {/* Textarea Area */}
        <div className="flex-1 relative overflow-y-auto max-h-[258px]">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyPress}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder={placeholder}
            disabled={isStreaming}
            aria-label="Chat message input"
            className="
              w-full border-0 p-3
              bg-transparent text-[16px] text-foreground
              placeholder:text-muted-foreground
              resize-none shadow-none outline-none
              min-h-[48.4px] leading-relaxed
              whitespace-pre-wrap break-words
              disabled:cursor-not-allowed disabled:opacity-50
              transition-[padding] duration-200 ease-in-out
            "
          />
        </div>

        {/* Bottom Toolbar */}
        <div className="flex min-h-[40px] items-center gap-2 p-2 pb-1 justify-end">
          {/* Right Side Actions */}
          <div className="flex items-center gap-2">
            {/* Send Button */}
            <button
              type="button"
              onClick={handleSend}
              disabled={!hasContent || isStreaming}
              aria-label="Send message"
              className={`
                inline-flex items-center justify-center
                h-8 w-8 rounded-full cursor-pointer
                transition-all duration-150
                outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-background
                ${hasContent && !isStreaming
                  ? mode === 'capture'
                    ? 'bg-capture text-white hover:opacity-90 focus-visible:ring-capture/50'
                    : 'bg-codegen text-white hover:opacity-90 focus-visible:ring-codegen/50'
                  : 'bg-muted text-muted-foreground cursor-not-allowed opacity-50'
                }
              `}
            >
              <ArrowUpIcon className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {isStreaming && (
        <div className="mt-2 flex items-center gap-2 px-1">
          <div
            className={`w-1.5 h-1.5 rounded-full animate-pulse ${mode === 'capture' ? 'bg-capture' : 'bg-codegen'
              }`}
          />
          <span className="text-caption text-muted-foreground">Processing...</span>
        </div>
      )}
    </div>
  )
}

function ArrowUpIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M12 5l0 14"></path>
      <path d="M18 11l-6 -6"></path>
      <path d="M6 11l6 -6"></path>
    </svg>
  )
}
