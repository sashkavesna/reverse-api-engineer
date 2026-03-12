import { useState, useEffect, useRef, useCallback } from 'react'
import { AgentAction } from '../components/agent-action'
import { ChatInput } from '../components/chat-input'
import { SessionSelector } from '../components/session-selector'
import { ModeSelector } from '../components/mode-selector'
import { CodeBlock } from '../components/ui/code-block'
import { PlayIcon, StopIcon, Tick02Icon } from '../components/icons'
import type { AppState, AgentEvent, Settings, Session, AppMode } from '../shared/types'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content?: string
  events?: AgentEvent[]
  timestamp?: string
}

interface ExtendedAppState extends AppState {
  sessions?: Session[]
  codegenActive?: boolean
  codegenScript?: string
  currentTabUrl?: string
}

interface CapturedRequest {
  id: string
  method: string
  url: string
  status?: number
  statusText?: string
  type: string
  time: number
  size: number
}

const DEFAULT_STATE: ExtendedAppState = {
  capturing: false,
  runId: null,
  nativeHostConnected: false,
  isStreaming: false,
  stats: { total: 0 },
  current_task: null,
  activeSessionId: null,
  mode: 'capture',
  sessions: [],
  codegenActive: false,
  codegenScript: ''
}

const DEFAULT_SETTINGS: Settings = {
  lastModel: 'claude-sonnet-4-6',
  captureTypes: ['xhr', 'fetch', 'websocket'],
  saveLocation: 'downloads'
}

export function SidePanel() {
  const [state, setState] = useState<ExtendedAppState>(DEFAULT_STATE)
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [warningMessage, setWarningMessage] = useState<string | null>(null)
  const [codegenSavedPath, setCodegenSavedPath] = useState<string | null>(null)
  const [codegenVisiblePath, setCodegenVisiblePath] = useState<string | null>(null)
  const [codegenVisibleDirectory, setCodegenVisibleDirectory] = useState<string | null>(null)
  const [showTrafficList, setShowTrafficList] = useState(false)
  const [capturedRequests, setCapturedRequests] = useState<CapturedRequest[]>([])
  const [isRestrictedPage, setIsRestrictedPage] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const currentResponseIdRef = useRef<string | null>(null)
  const warningTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const showTrafficListRef = useRef(false)
  showTrafficListRef.current = showTrafficList

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  const checkRestrictedUrl = useCallback((url: string) => {
    if (!url) { setIsRestrictedPage(true); return }
    const restrictedProtocols = ['chrome:', 'chrome-extension:', 'edge:', 'about:', 'data:', 'file:', 'view-source:']
    try {
      const urlObj = new URL(url)
      setIsRestrictedPage(restrictedProtocols.includes(urlObj.protocol))
    } catch {
      setIsRestrictedPage(true)
    }
  }, [])

  // Initialize: load state and settings
  useEffect(() => {
    const init = async () => {
      try {
        const [stateRes, settingsRes] = await Promise.all([
          chrome.runtime.sendMessage({ type: 'getState' }),
          chrome.runtime.sendMessage({ type: 'getSettings' }),
        ])
        if (stateRes) {
          setState(prev => ({ ...prev, ...stateRes }))
          if (stateRes.currentTabUrl) checkRestrictedUrl(stateRes.currentTabUrl)

          // Load active session's data including messages and codegen info
          const sessions = stateRes.sessions as Session[] | undefined
          const activeSession = sessions?.find(s => s.id === stateRes.activeSessionId)
          if (activeSession) {
            setMessages(activeSession.messages || [])
            setCodegenSavedPath(activeSession.codegenSavedPath || null)
            setCodegenVisiblePath(activeSession.codegenVisiblePath || null)
            setCodegenVisibleDirectory(activeSession.codegenVisibleDirectory || null)
          }
        }
        if (settingsRes) setSettings(prev => ({ ...prev, ...settingsRes }))
      } catch (err) {
        console.error('Failed to initialize:', err)
      }
    }
    init()
  }, [checkRestrictedUrl])

  // Listen for tab changes to detect restricted pages
  useEffect(() => {
    const handleTabActivated = () => {
      chrome.runtime.sendMessage({ type: 'getTabInfo' }).then(res => {
        if (res) checkRestrictedUrl(res.url)
      }).catch(() => {})
    }
    const handleTabUpdated = (_tabId: number, changeInfo: chrome.tabs.TabChangeInfo) => {
      if (changeInfo.url || changeInfo.status === 'complete') {
        handleTabActivated()
      }
    }

    chrome.tabs.onActivated.addListener(handleTabActivated)
    chrome.tabs.onUpdated.addListener(handleTabUpdated)
    return () => {
      chrome.tabs.onActivated.removeListener(handleTabActivated)
      chrome.tabs.onUpdated.removeListener(handleTabUpdated)
    }
  }, [checkRestrictedUrl])

  // Cleanup warning timeout on unmount
  useEffect(() => {
    return () => {
      if (warningTimeoutRef.current) clearTimeout(warningTimeoutRef.current)
    }
  }, [])

  // Listen for messages from background
  useEffect(() => {
    const handleMessage = (message: { type: string; event?: AgentEvent | { type: string }; script?: string; session?: Session; mode?: AppMode; newCode?: string; savedPath?: string }) => {
      switch (message.type) {
        case 'captureEvent':
          // Refresh state to get updated counts
          chrome.runtime.sendMessage({ type: 'getState' }).then(res => {
            if (res) setState(prev => ({ ...prev, ...res }))
          })
          // Refresh request list if it's open
          if (showTrafficListRef.current) {
            chrome.runtime.sendMessage({ type: 'getCapturedRequests' }).then(res => {
              if (Array.isArray(res)) setCapturedRequests(res as CapturedRequest[])
            }).catch(() => {})
          }
          break
        case 'agentEvent':
          handleAgentEvent(message.event as AgentEvent)
          break
        case 'nativeHostDisconnected':
          setState(prev => ({ ...prev, nativeHostConnected: false }))
          break
        case 'sessionCreated':
        case 'sessionSwitched':
        case 'sessionDeleted':
        case 'sessionRenamed':
          // Refresh sessions list and load the active session's data
          chrome.runtime.sendMessage({ type: 'getState' }).then(res => {
            if (res) {
              setState(prev => ({ ...prev, ...res }))
              const sessions = res.sessions as Session[] | undefined
              const newActiveSession = sessions?.find(s => s.id === res.activeSessionId)
              if (newActiveSession) {
                setMessages(newActiveSession.messages || [])
                setCodegenSavedPath(newActiveSession.codegenSavedPath || null)
                setCodegenVisiblePath(newActiveSession.codegenVisiblePath || null)
                setCodegenVisibleDirectory(newActiveSession.codegenVisibleDirectory || null)
              } else {
                setMessages([])
                setCodegenSavedPath(null)
                setCodegenVisiblePath(null)
                setCodegenVisibleDirectory(null)
              }
            }
          }).catch(() => {})
          break
        case 'trafficCleared':
          chrome.runtime.sendMessage({ type: 'getState' }).then(res => {
            if (res) setState(prev => ({ ...prev, ...res }))
          })
          setCapturedRequests([])
          setShowTrafficList(false)
          break
        case 'modeChanged':
          if (message.mode) {
            setState(prev => ({ ...prev, mode: message.mode! }))
          }
          break
        case 'codegenStarted':
          setState(prev => ({ ...prev, codegenActive: true, codegenScript: message.script || '' }))
          setCodegenSavedPath(null)
          break
        case 'codegenUpdate':
          setState(prev => ({ ...prev, codegenScript: message.script || '' }))
          break
        case 'codegenStopped':
          setState(prev => ({ ...prev, codegenActive: false, codegenScript: message.script || '' }))
          if (message.savedPath) {
            setCodegenSavedPath(message.savedPath)
          }
          // Handle dual save paths
          if ((message as { visiblePath?: string }).visiblePath) {
            setCodegenVisiblePath((message as { visiblePath?: string }).visiblePath || null)
          }
          if ((message as { visibleDirectory?: string }).visibleDirectory) {
            setCodegenVisibleDirectory((message as { visibleDirectory?: string }).visibleDirectory || null)
          }
          break
      }
    }

    chrome.runtime.onMessage.addListener(handleMessage)
    return () => chrome.runtime.onMessage.removeListener(handleMessage)
  }, [])

  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const handleAgentEvent = useCallback((event: AgentEvent) => {
    // Extract current task from TodoWrite tool events
    if (event.event_type === 'tool_use' && event.tool_name === 'TodoWrite' && event.tool_input) {
      const todos = (event.tool_input as { todos?: Array<{ status: string; content: string; activeForm?: string }> }).todos
      if (todos && Array.isArray(todos)) {
        const inProgressTodo = todos.find(todo => todo.status === 'in_progress')
        if (inProgressTodo) {
          const currentTask = inProgressTodo.activeForm || inProgressTodo.content
          setState(prev => ({ ...prev, current_task: currentTask }))
        } else {
          // Check if all todos are completed
          const allCompleted = todos.every(todo => todo.status === 'completed')
          if (allCompleted) {
            setState(prev => ({ ...prev, current_task: null }))
          }
        }
      }
    }

    setMessages(prev => {
      // Find or create the current assistant message
      let currentId = currentResponseIdRef.current

      if (!currentId) {
        currentId = `assistant-${Date.now()}`
        currentResponseIdRef.current = currentId
        return [...prev, { id: currentId, role: 'assistant', events: [event] }]
      }

      return prev.map(msg => {
        if (msg.id === currentId) {
          return { ...msg, events: [...(msg.events || []), event] }
        }
        return msg
      })
    })

    // Handle done/error events — persist messages when response completes
    if (event.event_type === 'done' || event.event_type === 'error') {
      currentResponseIdRef.current = null
      setState(prev => ({ ...prev, isStreaming: false, current_task: null }))
      // Read latest messages and persist
      setMessages(prev => {
        chrome.runtime.sendMessage({ type: 'saveMessages', messages: prev }).catch(() => {})
        return prev
      })
    }
  }, [])

  const toggleCapture = async () => {
    try {
      if (state.capturing) {
        await chrome.runtime.sendMessage({ type: 'stopCapture' })
      } else {
        if (isRestrictedPage) {
          showWarning('Navigate to a website first (http:// or https://)')
          return
        }
        await chrome.runtime.sendMessage({ type: 'startCapture' })
      }
      const res = await chrome.runtime.sendMessage({ type: 'getState' })
      if (res) setState(prev => ({ ...prev, ...res }))
    } catch (err) {
      console.error('Capture error:', err)
      showWarning((err as Error).message || 'Failed to start capture')
    }
  }

  const handleClearTraffic = async () => {
    try {
      await chrome.runtime.sendMessage({ type: 'clearTraffic' })
      const res = await chrome.runtime.sendMessage({ type: 'getState' })
      if (res) setState(prev => ({ ...prev, ...res }))
      setCapturedRequests([])
      setShowTrafficList(false)
    } catch (err) {
      showWarning((err as Error).message || 'Failed to clear traffic')
    }
  }

  const loadCapturedRequests = async () => {
    try {
      const res = await chrome.runtime.sendMessage({ type: 'getCapturedRequests' })
      if (Array.isArray(res)) setCapturedRequests(res as CapturedRequest[])
    } catch (err) {
      console.error('Failed to load requests:', err)
    }
  }

  const toggleTrafficList = () => {
    if (!showTrafficList) loadCapturedRequests()
    setShowTrafficList(prev => !prev)
  }

  const checkNativeHost = async () => {
    try {
      const res = await chrome.runtime.sendMessage({ type: 'checkNativeHost' })
      setState(prev => ({ ...prev, nativeHostConnected: res.connected }))
    } catch (err) {
      console.error('Host check error:', err)
    }
  }

  const showWarning = (msg: string) => {
    if (warningTimeoutRef.current) clearTimeout(warningTimeoutRef.current)
    setWarningMessage(msg)
    warningTimeoutRef.current = setTimeout(() => {
      setWarningMessage(null)
    }, 3000)
  }

  const persistMessages = useCallback((msgs: ChatMessage[]) => {
    chrome.runtime.sendMessage({ type: 'saveMessages', messages: msgs }).catch(() => {})
  }, [])

  const sendMessage = async (message: string) => {
    if (!message.trim()) return

    if (state.isStreaming) {
      showWarning('Agent is already working...')
      return
    }

    if (!state.nativeHostConnected) {
      showWarning('Native host not connected')
      return
    }

    if (state.stats.total === 0) {
      showWarning('Capture traffic first')
      return
    }

    // Reset response tracking for the new query
    currentResponseIdRef.current = null
    setState(prev => ({ ...prev, current_task: null }))

    // Add user message
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => {
      const updated = [...prev, userMsg]
      persistMessages(updated)
      return updated
    })
    setInputValue('')
    setWarningMessage(null)
    setState(prev => ({ ...prev, isStreaming: true }))

    try {
      await chrome.runtime.sendMessage({
        type: 'chat',
        message,
        model: settings.lastModel,
      })
    } catch (err) {
      console.error('Chat error:', err)
      setState(prev => ({ ...prev, isStreaming: false }))
      showWarning('Failed to send message')
    }
  }

  // Session management handlers
  const handleCreateSession = async (name?: string) => {
    try {
      await chrome.runtime.sendMessage({ type: 'createSession', name })
      const res = await chrome.runtime.sendMessage({ type: 'getState' })
      if (res) setState(prev => ({ ...prev, ...res }))
      // Clear messages and codegen data for new session
      setMessages([])
      setCodegenSavedPath(null)
      setCodegenVisiblePath(null)
      setCodegenVisibleDirectory(null)
    } catch (err) {
      console.error('Create session error:', err)
      showWarning('Failed to create session')
    }
  }

  const handleSwitchSession = async (sessionId: string) => {
    try {
      await chrome.runtime.sendMessage({ type: 'switchSession', sessionId })
      const res = await chrome.runtime.sendMessage({ type: 'getState' })
      if (res) setState(prev => ({ ...prev, ...res }))

      // Load session-specific data including messages and codegen info
      const sessions = res?.sessions as Session[] | undefined
      const currentSession = sessions?.find(s => s.id === sessionId)
      if (currentSession) {
        setMessages(currentSession.messages || [])
        setCodegenSavedPath(currentSession.codegenSavedPath || null)
        setCodegenVisiblePath(currentSession.codegenVisiblePath || null)
        setCodegenVisibleDirectory(currentSession.codegenVisibleDirectory || null)
      } else {
        setMessages([])
        setCodegenSavedPath(null)
        setCodegenVisiblePath(null)
        setCodegenVisibleDirectory(null)
      }
    } catch (err) {
      console.error('Switch session error:', err)
      showWarning((err as Error).message || 'Failed to switch session')
    }
  }

  const handleDeleteSession = async (sessionId: string) => {
    try {
      await chrome.runtime.sendMessage({ type: 'deleteSession', sessionId })
      const res = await chrome.runtime.sendMessage({ type: 'getState' })
      if (res) setState(prev => ({ ...prev, ...res }))
    } catch (err) {
      console.error('Delete session error:', err)
      showWarning((err as Error).message || 'Failed to delete session')
    }
  }

  const handleRenameSession = async (sessionId: string, name: string) => {
    try {
      await chrome.runtime.sendMessage({ type: 'renameSession', sessionId, name })
      const res = await chrome.runtime.sendMessage({ type: 'getState' })
      if (res) setState(prev => ({ ...prev, ...res }))
    } catch (err) {
      console.error('Rename session error:', err)
      showWarning('Failed to rename session')
    }
  }

  // Mode management handlers
  const handleModeChange = async (mode: AppMode) => {
    try {
      await chrome.runtime.sendMessage({ type: 'setMode', mode })
      setState(prev => ({ ...prev, mode }))
    } catch (err) {
      console.error('Mode change error:', err)
    }
  }

  // Codegen handlers
  const toggleCodegen = async () => {
    try {
      if (state.codegenActive) {
        await chrome.runtime.sendMessage({ type: 'stopCodegen' })
      } else {
        await chrome.runtime.sendMessage({ type: 'startCodegen' })
      }
      const res = await chrome.runtime.sendMessage({ type: 'getState' })
      if (res) setState(prev => ({ ...prev, ...res }))
    } catch (err) {
      console.error('Codegen error:', err)
      showWarning((err as Error).message || 'Codegen error')
    }
  }

  const isActive = state.mode === 'capture' ? state.capturing : state.codegenActive

  return (
    <div className="flex flex-col h-screen bg-background text-text-primary selection:bg-primary/30">
      {/* Header */}
      <header className="flex items-center justify-between gap-3 px-4 py-3 bg-background backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {/* Session Selector */}
          <SessionSelector
            sessions={state.sessions || []}
            activeSessionId={state.activeSessionId}
            isCapturing={state.capturing}
            onCreateSession={handleCreateSession}
            onSwitchSession={handleSwitchSession}
            onDeleteSession={handleDeleteSession}
            onRenameSession={handleRenameSession}
          />

          {/* Mode Switcher */}
          <ModeSelector
            mode={state.mode}
            onModeChange={handleModeChange}
            disabled={state.capturing || state.codegenActive}
          />

          {/* Current Task Pill */}
          {state.current_task && (
            <div
              className={`flex items-center gap-2 px-3 py-1.5 text-tiny truncate max-w-md rounded-lg border ${state.mode === 'capture'
                  ? 'bg-capture/5 text-capture/80 border-capture/10'
                  : 'bg-codegen/5 text-codegen/80 border-codegen/10'
                }`}
            >
              <span className="opacity-60">Current:</span>
              <span className="truncate">{state.current_task}</span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={state.mode === 'capture' ? toggleCapture : toggleCodegen}
            className={`p-1.5 rounded-lg cursor-pointer transition-all duration-200 ${isActive
                ? state.mode === 'capture'
                  ? 'text-capture bg-capture/10 hover:bg-capture/20'
                  : 'text-codegen bg-codegen/10 hover:bg-codegen/20'
                : 'text-white/60 hover:text-white hover:bg-white/10'
              }`}
            title={
              state.mode === 'capture'
                ? state.capturing
                  ? `Stop recording (${state.stats.total} requests)`
                  : 'Start recording traffic'
                : state.codegenActive
                  ? 'Stop code generation'
                  : 'Start generating code'
            }
            aria-label={
              state.mode === 'capture'
                ? state.capturing ? 'Stop capture' : 'Start capture'
                : state.codegenActive ? 'Stop recording' : 'Start recording'
            }
          >
            {isActive ? (
              <StopIcon className="w-4 h-4" />
            ) : (
              <PlayIcon className="w-4 h-4" />
            )}
          </button>
        </div>
      </header>

      {/* Native host warning */}
      {!state.nativeHostConnected && state.mode === 'capture' && (
        <div className="mx-4 mt-4 p-3 bg-capture/5 rounded-xl border border-capture/10">
          <div className="flex items-start gap-3">
            <WarningIcon />
            <div className="flex-1 min-w-0">
              <p className="text-small font-bold text-capture uppercase tracking-tight">Connection Error</p>
              <p className="text-caption text-text-secondary mt-1 leading-relaxed">
                Native host not found. Execute:
                <code className="block mt-1 bg-background-elevated p-1.5 rounded-lg text-capture/80 font-mono">
                  reverse-api-engineer install-host
                </code>
              </p>
              <button
                onClick={checkNativeHost}
                className="mt-2 text-caption text-white hover:text-capture transition-colors font-bold underline cursor-pointer"
                aria-label="Retry connection to native host"
              >
                {'>'} Retry connection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Restricted page warning */}
      {isRestrictedPage && !state.capturing && state.mode === 'capture' && (
        <div className="mx-4 mt-4 p-3 bg-capture/5 rounded-xl border border-capture/10">
          <div className="flex items-start gap-3">
            <WarningIcon />
            <div className="flex-1 min-w-0">
              <p className="text-small font-bold text-capture uppercase tracking-tight">Cannot record here</p>
              <p className="text-caption text-text-secondary mt-1 leading-relaxed">
                Navigate to a website (http:// or https://) to start recording.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Traffic panel */}
      {state.mode === 'capture' && state.stats.total > 0 && (
        <div className="mx-4 mt-4">
          <div className="rounded-xl border border-border bg-muted/50 overflow-hidden">
            {/* Traffic header row */}
            <div className="flex items-center justify-between px-3 py-2">
              <button
                onClick={toggleTrafficList}
                className="flex items-center gap-2 text-tiny text-text-secondary hover:text-white transition-colors cursor-pointer"
              >
                <svg
                  className={`w-3 h-3 transition-transform duration-200 ${showTrafficList ? 'rotate-90' : ''}`}
                  fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                </svg>
                Traffic captured: <span className="text-white font-bold">{state.stats.total}</span>
              </button>
              <button
                onClick={handleClearTraffic}
                disabled={state.capturing}
                className="text-tiny text-text-secondary hover:text-capture transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed px-1.5 py-0.5 rounded hover:bg-capture/10"
                title={state.capturing ? 'Stop capture before clearing' : 'Clear captured traffic'}
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>

            {/* Expandable request list */}
            {showTrafficList && (
              <div className="border-t border-border max-h-60 overflow-y-auto custom-scrollbar">
                {capturedRequests.length === 0 ? (
                  <div className="px-3 py-4 text-center text-tiny text-text-secondary">
                    No requests recorded yet
                  </div>
                ) : (
                  capturedRequests.map((req, idx) => {
                    let urlPath = req.url
                    try { urlPath = new URL(req.url).pathname + new URL(req.url).search } catch { /* use full url */ }
                    const statusColor = !req.status ? 'text-text-secondary'
                      : req.status < 300 ? 'text-green-400'
                      : req.status < 400 ? 'text-amber-400'
                      : 'text-red-400'
                    return (
                      <div
                        key={req.id || idx}
                        className="flex items-center gap-2 px-3 py-1.5 text-tiny border-t border-border/50 first:border-t-0 hover:bg-white/5"
                      >
                        <span className="font-bold text-primary w-10 flex-shrink-0 text-right">{req.method}</span>
                        <span className={`w-8 flex-shrink-0 text-right ${statusColor}`}>{req.status || '-'}</span>
                        <span className="text-text-secondary truncate flex-1 font-mono" title={req.url}>{urlPath}</span>
                        <span className="text-text-secondary/50 flex-shrink-0 w-10 text-right">{req.type?.toLowerCase()}</span>
                      </div>
                    )
                  })
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main content area - conditional based on mode */}
      {state.mode === 'codegen' ? (
        /* Codegen Mode - Show code display */
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* Dual save completion notification */}
          {(codegenSavedPath || codegenVisiblePath) && (
            <div className="mx-3 mb-2 px-3 py-3 bg-[#3b82f6]/10 border border-[#3b82f6]/30 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Tick02Icon className="w-4 h-4 text-[#3b82f6] flex-shrink-0" />
                <span className="text-sm text-white font-medium">Script saved (dual location)</span>
              </div>
              
              {/* Visible location - Primary */}
              {codegenVisiblePath && (
                <div className="mb-2">
                  <div className="text-xs text-white/60 mb-1">Visible (easy to find):</div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(codegenVisiblePath)
                        showWarning('Path copied to clipboard')
                      }}
                      className="text-xs text-[#3b82f6] hover:text-[#3b82f6]/80 font-mono truncate flex-1 text-left"
                      title={codegenVisiblePath}
                    >
                      {codegenVisibleDirectory ? codegenVisibleDirectory.split('/').slice(-2).join('/') : codegenVisiblePath.split('/').slice(-3).join('/')}
                    </button>
                    <button
                      onClick={() => {
                        if (codegenVisibleDirectory) {
                          // Open folder in file manager (would need native host support)
                          navigator.clipboard.writeText(codegenVisibleDirectory)
                          showWarning('Folder path copied')
                        }
                      }}
                      className="text-xs bg-[#3b82f6]/20 hover:bg-[#3b82f6]/30 text-[#3b82f6] px-2 py-1 rounded transition-colors"
                    >
                      Copy
                    </button>
                  </div>
                </div>
              )}
              
              {/* Hidden location - Secondary */}
              {codegenSavedPath && (
                <div>
                  <div className="text-xs text-white/40 mb-1">Hidden (for sync/history):</div>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(codegenSavedPath)
                      showWarning('Hidden path copied')
                    }}
                    className="text-xs text-white/40 hover:text-white/60 font-mono truncate"
                    title={codegenSavedPath}
                  >
                    {codegenSavedPath.split('/').slice(-4).join('/')}
                  </button>
                </div>
              )}
            </div>
          )}
          <div className="flex-1 pb-3">
            <CodeBlock language="python" filename="playwright_script.py">
              {state.codegenScript || ''}
            </CodeBlock>
          </div>
        </div>
      ) : (
        /* Capture Mode - Show chat area */
        <>
          <div className="flex-1 overflow-y-auto overflow-x-hidden px-6 pb-4 pt-6 custom-scrollbar">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full">
                <div className="w-24 h-24 text-white/10">
                  <svg viewBox="0 0 400 400" className="w-full h-full" fill="none" stroke="currentColor" strokeWidth="12" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M 170 110 Q 150 110 140 120 Q 130 130 130 150 L 130 185 Q 130 195 120 195 L 110 195 L 110 205 L 120 205 Q 130 205 130 215 L 130 250 Q 130 270 140 280 Q 150 290 170 290" />
                    <path d="M 230 110 Q 250 110 260 120 Q 270 130 270 150 L 270 185 Q 270 195 280 195 L 290 195 L 290 205 L 280 205 Q 270 205 270 215 L 270 250 Q 270 270 260 280 Q 250 290 230 290" />
                    <circle cx="185" cy="200" r="5" fill="currentColor" stroke="none" />
                    <circle cx="200" cy="200" r="5" fill="currentColor" stroke="none" />
                    <circle cx="215" cy="200" r="5" fill="currentColor" stroke="none" />
                  </svg>
                </div>
              </div>
            ) : (
              <div className="space-y-8 max-w-full">
                {messages.map((msg, msgIdx) => (
                  <div key={msg.id} className="animate-in fade-in duration-500 w-full">
                    {msg.role === 'user' ? (
                      <>
                        {msgIdx > 0 && (
                          <div className="h-px bg-primary/10 my-6"></div>
                        )}
                        <div className="flex items-start gap-3 w-full">
                          <span className="text-primary font-bold mt-0.5 select-none flex-shrink-0">{'>'}</span>
                          <div className="flex-1 text-sm text-white font-normal break-words leading-relaxed min-w-0">
                            {msg.content}
                          </div>
                        </div>
                      </>
                    ) : (
                      <div className="space-y-4 pl-6 w-full">
                        {msg.events?.map((event, idx) => {
                          const previousEvent = idx > 0 ? msg.events?.[idx - 1] : undefined
                          return <AgentAction key={`${msg.id}-${idx}`} event={event} previousEvent={previousEvent} />
                        })}
                      </div>
                    )}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Chat input */}
          <div className="relative bg-background">
            {warningMessage && (
              <div
                className={`absolute bottom-full left-0 right-0 px-4 py-2 backdrop-blur-sm animate-slide-in-from-bottom ${state.mode === 'capture' ? 'bg-capture/10' : 'bg-codegen/10'
                  }`}
              >
                <div className="flex items-center gap-2">
                  <div
                    className={`w-1 h-1 rounded-full ${state.mode === 'capture' ? 'bg-capture' : 'bg-codegen'
                      }`}
                  />
                  <span
                    className={`text-tiny ${state.mode === 'capture' ? 'text-capture' : 'text-codegen'
                      }`}
                  >
                    {warningMessage}
                  </span>
                </div>
              </div>
            )}
            <ChatInput
              value={inputValue}
              onChange={setInputValue}
              onSend={sendMessage}
              isStreaming={state.isStreaming}
              placeholder={
                !state.nativeHostConnected
                  ? 'Native host disconnected'
                  : state.stats.total === 0
                    ? 'Capture traffic to begin'
                    : 'Build an API client...'
              }
              mode={state.mode}
            />
          </div>
        </>
      )}

    </div>
  )
}

function WarningIcon(): JSX.Element {
  return (
    <div className="text-capture flex-shrink-0">
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    </div>
  )
}
