/**
 * Content script for recording user interactions for Playwright codegen
 */

console.log('[Codegen Recorder] Content script loaded')

let isRecording = false

// Generate a robust CSS selector for an element
function getSelector(element: Element, depth: number = 0): string {
  // Prevent infinite recursion
  if (depth > 10) {
    return element.tagName.toLowerCase()
  }
  // Try data-testid first
  if (element.hasAttribute('data-testid')) {
    return `[data-testid="${CSS.escape(element.getAttribute('data-testid') || '')}"]`
  }

  // Try id
  if (element.id) {
    return `#${CSS.escape(element.id)}`
  }

  // Try unique class combination
  if (element.classList.length > 0) {
    const classes = Array.from(element.classList)
      .filter(c => !c.match(/^(active|hover|focus|selected|open|closed|hidden|visible)/i))
      .slice(0, 3)
    if (classes.length > 0) {
      const selector = classes.map(c => `.${CSS.escape(c)}`).join('')
      const matches = document.querySelectorAll(selector)
      if (matches.length === 1) {
        return selector
      }
    }
  }

  // Try name attribute for form elements
  if (element.hasAttribute('name')) {
    const name = element.getAttribute('name')
    const tag = element.tagName.toLowerCase()
    const selector = `${tag}[name="${CSS.escape(name || '')}"]`
    const matches = document.querySelectorAll(selector)
    if (matches.length === 1) {
      return selector
    }
  }

  // Try placeholder for inputs
  if (element.hasAttribute('placeholder')) {
    const placeholder = element.getAttribute('placeholder')
    return `[placeholder="${CSS.escape(placeholder || '')}"]`
  }

  // Try aria-label
  if (element.hasAttribute('aria-label')) {
    const ariaLabel = element.getAttribute('aria-label')
    return `[aria-label="${CSS.escape(ariaLabel || '')}"]`
  }

  // Try text content for buttons and links
  if (element.tagName === 'BUTTON' || element.tagName === 'A') {
    const text = element.textContent?.trim().slice(0, 30)
    if (text) {
      return `text="${text}"`
    }
  }

  // Fall back to tag + nth-child
  const parent = element.parentElement
  if (parent && parent.tagName !== 'BODY' && parent.tagName !== 'HTML') {
    const siblings = Array.from(parent.children)
    const index = siblings.indexOf(element) + 1
    const tag = element.tagName.toLowerCase()
    const parentSelector = getSelector(parent, depth + 1)
    return `${parentSelector} > ${tag}:nth-child(${index})`
  }

  // Last resort: just the tag
  return element.tagName.toLowerCase()
}

// Escape string for Python
function escapeString(str: string): string {
  return str
    .replace(/\\/g, '\\\\')
    .replace(/"/g, '\\"')
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r')
    .replace(/\t/g, '\\t')
}

// Send action to background script
function sendAction(action: string, data: Record<string, unknown>) {
  chrome.runtime.sendMessage({
    type: 'codegenAction',
    action,
    ...data
  }).catch(() => {
    // Extension might not be listening
  })
}

// Track the last input element to capture its final value
let lastInputElement: HTMLInputElement | HTMLTextAreaElement | null = null
let inputTimeout: ReturnType<typeof setTimeout> | null = null

// Track scroll events
let lastScrollTime = 0
let scrollTimeout: ReturnType<typeof setTimeout> | null = null

// Track click events for navigation correlation
let lastClickTime = 0

function handleClick(event: MouseEvent) {
  if (!isRecording) return

  const target = event.target as Element
  if (!target) return

  // Skip clicks on the extension's own elements
  if (target.closest('[data-codegen-ignore]')) return

  // Commit any pending input
  commitPendingInput()

  const selector = getSelector(target)

  // Check if it's a select element
  if (target.tagName === 'SELECT') {
    // Will be handled by change event
    return
  }

  console.log('[Codegen] Click on:', selector, target)
  lastClickTime = Date.now()
  sendAction('click', { selector })
}

function handleInput(event: Event) {
  if (!isRecording) return

  const target = event.target as HTMLInputElement | HTMLTextAreaElement
  if (!target) return

  // Track the input element
  lastInputElement = target

  // Debounce the input to get the final value
  if (inputTimeout) {
    clearTimeout(inputTimeout)
  }

  inputTimeout = setTimeout(() => {
    commitPendingInput()
  }, 500)
}

function commitPendingInput() {
  if (!lastInputElement) return

  const selector = getSelector(lastInputElement)
  const value = lastInputElement.value

  console.log('[Codegen] Fill input:', selector, 'with value:', value)
  sendAction('fill', { selector, value })

  lastInputElement = null
  if (inputTimeout) {
    clearTimeout(inputTimeout)
    inputTimeout = null
  }
}

function handleChange(event: Event) {
  if (!isRecording) return

  const target = event.target as HTMLSelectElement
  if (!target || target.tagName !== 'SELECT') return

  const selector = getSelector(target)
  const value = target.value

  sendAction('select', { selector, value })
}

function handleKeyDown(event: KeyboardEvent) {
  if (!isRecording) return

  // Commit input on Enter
  if (event.key === 'Enter') {
    commitPendingInput()
  }
}

function handleScroll(_event: Event) {
  if (!isRecording) return

  // Debounce scroll events (300ms)
  if (scrollTimeout) {
    clearTimeout(scrollTimeout)
  }

  scrollTimeout = setTimeout(() => {
    const scrollX = window.scrollX
    const scrollY = window.scrollY

    console.log('[Codegen] Scroll detected:', { scrollX, scrollY })
    sendAction('scroll', { scrollX, scrollY })
    lastScrollTime = Date.now()
  }, 300)
}

// Handle navigation
let lastUrl = window.location.href
let navigationInterval: ReturnType<typeof setInterval> | null = null
function checkNavigation() {
  if (window.location.href !== lastUrl) {
    const newUrl = window.location.href
    const timeSinceClick = Date.now() - lastClickTime

    // Mark navigation as click-caused if within 500ms of a click
    const causedByClick = timeSinceClick < 500

    console.log('[Codegen] Navigation detected:', lastUrl, '->', newUrl, causedByClick ? '(caused by click)' : '')
    lastUrl = newUrl
    if (isRecording) {
      sendAction('navigate', { url: lastUrl, causedByClick })
    }
  }
}

// Start recording
function startRecording() {
  if (isRecording) return

  isRecording = true
  lastUrl = window.location.href

  // Don't send initial navigation - startCodegen() already adds page.goto() in the template

  document.addEventListener('click', handleClick, true)
  document.addEventListener('input', handleInput, true)
  document.addEventListener('change', handleChange, true)
  document.addEventListener('keydown', handleKeyDown, true)
  document.addEventListener('scroll', handleScroll, true)

  // Check for navigation periodically
  navigationInterval = setInterval(checkNavigation, 100)

  console.log('[Codegen] Recording started on:', lastUrl)
}

// Stop recording
function stopRecording() {
  if (!isRecording) return

  commitPendingInput()
  isRecording = false

  document.removeEventListener('click', handleClick, true)
  document.removeEventListener('input', handleInput, true)
  document.removeEventListener('change', handleChange, true)
  document.removeEventListener('keydown', handleKeyDown, true)
  document.removeEventListener('scroll', handleScroll, true)

  if (scrollTimeout) {
    clearTimeout(scrollTimeout)
    scrollTimeout = null
  }

  if (navigationInterval) {
    clearInterval(navigationInterval)
    navigationInterval = null
  }

  console.log('[Codegen] Recording stopped')
}

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'startCodegenRecording') {
    startRecording()
    sendResponse({ success: true })
  } else if (message.type === 'stopCodegenRecording') {
    stopRecording()
    sendResponse({ success: true })
  }
  return true
})

// Check if we should be recording on load
function checkInitialState(retries = 3) {
  chrome.runtime.sendMessage({ type: 'getCodegenState' }).then(response => {
    if (response?.codegenActive) {
      startRecording()
    }
  }).catch(() => {
    if (retries > 0) {
      setTimeout(() => checkInitialState(retries - 1), 500)
    }
  })
}
checkInitialState()
