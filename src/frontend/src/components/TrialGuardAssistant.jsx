import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Shield, Bot, Zap, X, Trash2, Send, Hospital, ClipboardList } from 'lucide-react'
import { sendChatMessage, fetchChatSuggestions } from '../utils/api'

export default function TrialGuardAssistant({ initialOpen = false }) {
  const [isOpen, setIsOpen] = useState(initialOpen)
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      sender: 'assistant',
      text: '👋 **Hello! I am TrialGuard Assistant.**\n\nI can help you monitor protocol compliance, analyze site risk scores, investigate deviations, and generate regulatory CAPA reports for the **PHOENIX-301** trial.\n\nHow can I help you today?',
      toolUsed: null,
      suggestions: [
        '📊 Give me a trial summary',
        '🔴 Which sites are highest risk?',
        '🔍 What is the risk of SITE-042?',
        '⚠️ Show deviations for SITE-001',
        '📋 Generate CAPA for SITE-042',
      ],
      siteId: null,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [activeSuggestions, setActiveSuggestions] = useState([])
  
  // Dragging state
  const [position, setPosition] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef({ x: 0, y: 0, moved: false, startX: 0, startY: 0 })
  
  const [windowSize, setWindowSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight
  })

  useEffect(() => {
    const handleResize = () => setWindowSize({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  const handlePointerDown = (e) => {
    if (e.button !== 0) return
    setIsDragging(true)
    dragStart.current = {
      x: e.clientX - position.x,
      y: e.clientY - position.y,
      startX: e.clientX,
      startY: e.clientY,
      moved: false
    }
    e.target.setPointerCapture(e.pointerId)
  }

  const handlePointerMove = (e) => {
    if (!isDragging) return
    if (!dragStart.current.moved) {
      if (Math.abs(e.clientX - dragStart.current.startX) > 3 || Math.abs(e.clientY - dragStart.current.startY) > 3) {
        dragStart.current.moved = true
      }
    }
    
    let newX = e.clientX - dragStart.current.x
    let newY = e.clientY - dragStart.current.y

    // Keep the button within screen bounds (with a 10px safety margin)
    const BUTTON_WIDTH = 160
    const BUTTON_HEIGHT = 48
    const MARGIN = 10

    const minX = -(window.innerWidth - 28 - BUTTON_WIDTH - MARGIN)
    const maxX = 28 - MARGIN
    
    const minY = -(window.innerHeight - 24 - BUTTON_HEIGHT - MARGIN)
    const maxY = 24 - MARGIN

    if (newX < minX) newX = minX
    if (newX > maxX) newX = maxX
    if (newY < minY) newY = minY
    if (newY > maxY) newY = maxY

    setPosition({ x: newX, y: newY })
  }

  const handlePointerUp = (e) => {
    setIsDragging(false)
    e.target.releasePointerCapture(e.pointerId)
  }

  const handleLauncherClick = () => {
    if (dragStart.current.moved) {
      dragStart.current.moved = false
      return
    }
    setIsOpen(!isOpen)
  }

  useEffect(() => {
    fetchChatSuggestions()
      .then((data) => {
        if (data && data.suggestions) {
          setActiveSuggestions(data.suggestions)
        }
      })
      .catch(() => {
        // Fallback default suggestions
        setActiveSuggestions([
          'Give me a trial summary',
          'Which sites are highest risk?',
          'What is the risk of SITE-042?',
          'Show deviations for SITE-001',
          'Generate CAPA for SITE-042',
        ])
      })
  }, [])

  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [isOpen, messages])

  const handleSend = async (textToSend = null) => {
    const query = (textToSend || input).trim()
    if (!query || isLoading) return

    const userMsgId = 'user-' + Date.now()
    const userMsg = {
      id: userMsgId,
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const res = await sendChatMessage(query)
      const assistantMsg = {
        id: 'assistant-' + Date.now(),
        sender: 'assistant',
        text: res.reply || 'No response received.',
        toolUsed: res.tool_used,
        suggestions: res.suggestions && res.suggestions.length > 0 ? res.suggestions : [],
        siteId: res.site_id,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, assistantMsg])
      if (res.suggestions && res.suggestions.length > 0) {
        setActiveSuggestions(res.suggestions)
      }
    } catch (err) {
      const errorMsg = {
        id: 'err-' + Date.now(),
        sender: 'assistant',
        text: '❌ **Failed to connect to TrialGuard analysis engine.** Please check if the backend server is running.',
        toolUsed: null,
        suggestions: ['Give me a trial summary', 'Which sites are highest risk?'],
        siteId: null,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleClearChat = () => {
    setMessages([
      {
        id: 'welcome-reset',
        sender: 'assistant',
        text: '🧹 Chat cleared. What would you like to investigate next?',
        toolUsed: null,
        suggestions: [
          'Give me a trial summary',
          'Which sites are highest risk?',
          'What is the risk of SITE-042?',
        ],
        siteId: null,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ])
  }

  const BUTTON_WIDTH = 150
  const BUTTON_HEIGHT = 48
  const DRAWER_WIDTH = 440
  const DRAWER_HEIGHT = 620

  const btnBottom = 24 - position.y
  const btnRight = 28 - position.x
  const btnTop = windowSize.height - btnBottom - BUTTON_HEIGHT
  const btnLeft = windowSize.width - btnRight - BUTTON_WIDTH

  let drawerStyle = {
    position: 'fixed',
    zIndex: 998,
    transition: isDragging ? 'none' : 'all 0.1s ease-out'
  }

  // Y-Axis
  if (btnTop > DRAWER_HEIGHT + 20) {
    drawerStyle.bottom = btnBottom + BUTTON_HEIGHT + 16
    drawerStyle.top = 'auto'
  } else if (btnBottom > DRAWER_HEIGHT + 20) {
    drawerStyle.top = btnTop + BUTTON_HEIGHT + 16
    drawerStyle.bottom = 'auto'
  } else {
    drawerStyle.top = 20
    drawerStyle.bottom = 20
  }

  // X-Axis
  if (btnLeft > DRAWER_WIDTH - BUTTON_WIDTH + 20) {
    drawerStyle.right = btnRight
    drawerStyle.left = 'auto'
  } else if (windowSize.width - btnLeft > DRAWER_WIDTH + 20) {
    drawerStyle.left = btnLeft
    drawerStyle.right = 'auto'
  } else {
    drawerStyle.left = 20
    drawerStyle.right = 'auto'
  }

  return (
    <>
      {/* Floating Action Button */}
      <button
        className={`tg-assistant-launcher ${isOpen ? 'active' : ''}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onClick={handleLauncherClick}
        style={{ 
          transform: `translate(${position.x}px, ${position.y}px)`, 
          transition: isDragging ? 'none' : 'transform 0.1s',
          cursor: isDragging ? 'grabbing' : 'pointer'
        }}
        aria-label="Toggle TrialGuard Assistant"
        title="Open TrialGuard Assistant"
      >
        <span className="tg-launcher-icon"><Shield size={16} /></span>
        <span className="tg-launcher-text">Ask Assistant</span>
        <span className="tg-launcher-badge">Live</span>
      </button>

      {/* Floating Chat Drawer */}
      {isOpen && (
        <div 
          className="tg-assistant-container"
          style={drawerStyle}
        >
          {/* Header */}
          <div className="tg-assistant-header">
            <div className="tg-header-info">
              <span className="tg-header-avatar"><Bot size={18} /></span>
              <div>
                <h3 className="tg-header-title">TrialGuard Assistant</h3>
                <span className="tg-header-status">
                  <span className="tg-status-dot"></span> MCP Engine Active
                </span>
              </div>
            </div>
            <div className="tg-header-actions" onPointerDown={(e) => e.stopPropagation()}>
              <button
                className="tg-icon-btn"
                onClick={handleClearChat}
                title="Clear Chat History"
                aria-label="Clear chat history"
              >
                <Trash2 size={14} />
              </button>
              <button
                className="tg-icon-btn"
                onClick={() => setIsOpen(false)}
                title="Close Assistant"
                aria-label="Close assistant"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          {/* Quick suggestions banner */}
          {activeSuggestions.length > 0 && (
            <div className="tg-quick-suggestions">
              {activeSuggestions.map((sug, i) => (
                <button
                  key={i}
                  className="tg-suggestion-chip"
                  onClick={() => handleSend(sug)}
                  disabled={isLoading}
                >
                  {sug}
                </button>
              ))}
            </div>
          )}

          {/* Messages Body */}
          <div className="tg-assistant-messages">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`tg-message ${msg.sender === 'user' ? 'tg-msg-user' : 'tg-msg-assistant'}`}
              >
                {msg.sender === 'assistant' && (
                  <div className="tg-msg-avatar"><Shield size={14} /></div>
                )}
                <div className="tg-msg-content">
                  {msg.toolUsed && (
                    <div className="tg-tool-badge">
                      <Zap size={10} />
                      <span>MCP Tool: <strong>{msg.toolUsed}</strong></span>
                    </div>
                  )}

                  <div className="tg-markdown-body">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.text}
                    </ReactMarkdown>
                  </div>

                  {/* Contextual navigation buttons if a site is referenced */}
                  {msg.siteId && (
                    <div className="tg-site-actions">
                      <button
                        className="tg-btn-action"
                        onClick={() => { navigate(`/sites/${msg.siteId}`); setIsOpen(false) }}
                      >
                        <Hospital size={11} /> View {msg.siteId} Dashboard
                      </button>
                      <button
                        className="tg-btn-action"
                        onClick={() => { navigate(`/capa/${msg.siteId}`); setIsOpen(false) }}
                      >
                        <ClipboardList size={11} /> Open Full CAPA Report
                      </button>
                    </div>
                  )}

                  <span className="tg-msg-time">{msg.timestamp}</span>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="tg-message tg-msg-assistant">
                <div className="tg-msg-avatar"><Shield size={14} /></div>
                <div className="tg-msg-content tg-loading-bubble">
                  <span className="tg-typing-dot"></span>
                  <span className="tg-typing-dot"></span>
                  <span className="tg-typing-dot"></span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Footer / Input form */}
          <form
            className="tg-assistant-footer"
            onSubmit={(e) => {
              e.preventDefault()
              handleSend()
            }}
          >
            <input
              ref={inputRef}
              type="text"
              className="tg-chat-input"
              placeholder="Ask about site risk, deviations, CAPA, trial summary..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button
              type="submit"
              className="tg-send-btn"
              disabled={isLoading || !input.trim()}
              title="Send message"
              aria-label="Send message"
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      )}
    </>
  )
}
