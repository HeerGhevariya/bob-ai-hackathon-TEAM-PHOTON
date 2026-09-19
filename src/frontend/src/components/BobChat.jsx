import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bot, Zap, X, Send, Hospital, ClipboardList } from 'lucide-react'
import { sendChatMessage } from '../utils/api'

const DEFAULT_SUGGESTIONS = [
  '📊 Trial Summary',
  '🏥 Top Risk Sites',
  '📋 Protocol Info',
  '⚠️ Show all deviations',
  '🔍 Risk of SITE-042',
  '📄 CAPA for SITE-042',
]

function formatResponse(text) {
  if (!text) return ''
  return text
    .replace(/## (.*)/g, '<h3 class="chat-heading">$1</h3>')
    .replace(/### (.*)/g, '<h4 class="chat-subheading">$1</h4>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code class="chat-code">$1</code>')
    .replace(/_(.*?)_/g, '<em>$1</em>')
    .replace(/\n• /g, '\n<span class="chat-bullet">•</span> ')
    .replace(/\n- /g, '\n<span class="chat-bullet">•</span> ')
    .replace(/\n(\d+)\. /g, '\n<span class="chat-bullet">$1.</span> ')
    .replace(/\n/g, '<br/>')
}

export default function BobChat() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: '🛡️ **TrialGuard AI — Bob MCP Chatbot**\n\nI look up real data from the PHOENIX-301 trial database. No guesses, no made-up answers — only actual trial data.\n\n**Try asking:**\n• `Show me SITE-042`\n• `Trial summary`\n• `Top risk sites`\n• `Deviations for SITE-015`',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [hasUnread, setHasUnread] = useState(false)
  const [suggestions, setSuggestions] = useState(DEFAULT_SUGGESTIONS)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const suggestionsRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (isOpen) {
      setHasUnread(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  async function handleSend(messageText) {
    const text = (messageText || input).trim()
    if (!text || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text }])
    setLoading(true)

    try {
      const result = await sendChatMessage(text)
      // Backend returns: { reply, tool_used, suggestions, site_id }
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          text: result.reply || result.response || 'No response received.',
          toolUsed: result.tool_used || null,
          siteId: result.site_id || null,
        },
      ])
      // Update dynamic suggestions from backend
      if (result.suggestions && result.suggestions.length > 0) {
        setSuggestions(result.suggestions)
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          text: '❌ Could not reach the server. Make sure the backend is running on port 8080.',
          isError: true,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleNavigate(siteId, target) {
    if (!siteId) return
    if (target === 'capa') {
      navigate(`/capa/${siteId}`)
    } else {
      navigate(`/sites/${siteId}`)
    }
    setIsOpen(false)
  }

  return (
    <>
      {/* Floating Chat Button */}
      <button
        className={`bob-chat-fab ${isOpen ? 'open' : ''} ${hasUnread ? 'unread' : ''}`}
        onClick={() => setIsOpen((v) => !v)}
        aria-label="Open Bob MCP Chatbot"
        title="Bob MCP Chatbot"
      >
        {isOpen ? (
          <span className="bob-chat-fab-icon"><X size={20} /></span>
        ) : (
          <span className="bob-chat-fab-icon"><Bot size={22} /></span>
        )}
        {hasUnread && !isOpen && <span className="bob-chat-unread-dot" />}
      </button>

      {/* Chat Panel */}
      {isOpen && (
        <div className="bob-chat-panel">
          {/* Header */}
          <div className="bob-chat-header">
            <div className="bob-chat-header-left">
              <div className="bob-chat-header-icon"><Bot size={18} /></div>
              <div>
                <div className="bob-chat-header-title">Bob MCP Chat</div>
                <div className="bob-chat-header-subtitle">
                  <span className="bob-chat-live-dot" />
                  Database-only · No hallucination
                </div>
              </div>
            </div>
            <button className="bob-chat-close" onClick={() => setIsOpen(false)} aria-label="Close chat">
              <X size={16} />
            </button>
          </div>

          {/* Messages */}
          <div className="bob-chat-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`bob-chat-msg ${msg.role}`}>
                {msg.role === 'bot' && (
                  <div className="bob-chat-msg-avatar"><Bot size={14} /></div>
                )}
                <div className={`bob-chat-bubble ${msg.role} ${msg.isError ? 'error' : ''}`}>
                  {/* MCP Tool Badge */}
                  {msg.toolUsed && (
                    <div className="bob-chat-tool-badge">
                      <Zap size={10} />
                      <span>MCP Tool: <strong>{msg.toolUsed}</strong></span>
                    </div>
                  )}
                  <div dangerouslySetInnerHTML={{ __html: formatResponse(msg.text) }} />
                  {/* Site navigation buttons */}
                  {msg.siteId && (
                    <div className="bob-chat-site-actions">
                      <button
                        className="bob-chat-link-btn"
                        onClick={() => handleNavigate(msg.siteId, 'site')}
                      >
                        <Hospital size={11} /> View {msg.siteId}
                      </button>
                      <button
                        className="bob-chat-link-btn"
                        onClick={() => handleNavigate(msg.siteId, 'capa')}
                      >
                        <ClipboardList size={11} /> CAPA Report
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="bob-chat-msg bot">
                <div className="bob-chat-msg-avatar"><Bot size={14} /></div>
                <div className="bob-chat-bubble bot">
                  <div className="bob-chat-typing">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Dynamic Suggestions — always visible, scrollable */}
          <div className="bob-chat-suggestions-bar" ref={suggestionsRef}>
            {suggestions.map((s, i) => (
              <button
                key={i}
                className="bob-chat-quick-btn"
                onClick={() => handleSend(s.replace(/^[^\w]*/, ''))}
                disabled={loading}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Input */}
          <div className="bob-chat-input-bar">
            <input
              ref={inputRef}
              className="bob-chat-input"
              type="text"
              placeholder="Ask about site risk, deviations, CAPA..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              className="bob-chat-send"
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              aria-label="Send message"
            >
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
