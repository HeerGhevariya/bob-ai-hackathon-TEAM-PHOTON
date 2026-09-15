import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendChatMessage } from '../utils/api'

const QUICK_ACTIONS = [
  { label: '📊 Trial Summary', message: 'Trial summary' },
  { label: '🏥 Top Risk Sites', message: 'Top risk sites' },
  { label: '📋 Protocol Info', message: 'Protocol info' },
  { label: '⚠️ All Deviations', message: 'Show all deviations' },
]

function formatResponse(text) {
  // Simple markdown-like formatting for chat display
  return text
    .replace(/## (.*)/g, '<h3 class="chat-heading">$1</h3>')
    .replace(/### (.*)/g, '<h4 class="chat-subheading">$1</h4>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code class="chat-code">$1</code>')
    .replace(/_(.*?)_/g, '<em>$1</em>')
    .replace(/\n• /g, '\n<span class="chat-bullet">•</span> ')
    .replace(/\n(\d+)\. /g, '\n<span class="chat-bullet">$1.</span> ')
    .replace(/\n/g, '<br/>')
}

export default function BobChat() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: '🛡️ **TrialGuard AI — Bob MCP Chatbot**\n\nI look up real data from the PHOENIX-301 trial database. No guesses, no made-up answers — only actual trial data.\n\n**Try asking:**\n• `Show me SITE-042`\n• `Trial summary`\n• `Top risk sites`\n• `Deviations for SITE-015`',
      type: 'help',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [hasUnread, setHasUnread] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
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
      setMessages((prev) => [
        ...prev,
        { role: 'bot', text: result.response, type: result.type, data: result.data },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          text: '❌ Could not reach the server. Make sure the backend is running on port 8080.',
          type: 'error',
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

  function handleNavigate(data, type) {
    if (!data) return
    if (type === 'site_detail' || type === 'site_risk' || type === 'site_deviations') {
      navigate(`/sites/${data.site_id}`)
      setIsOpen(false)
    } else if (type === 'capa_report') {
      navigate(`/capa/${data.site_id}`)
      setIsOpen(false)
    }
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
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
        ) : (
          <span className="bob-chat-fab-icon">🤖</span>
        )}
        {hasUnread && !isOpen && <span className="bob-chat-unread-dot" />}
      </button>

      {/* Chat Panel */}
      {isOpen && (
        <div className="bob-chat-panel">
          {/* Header */}
          <div className="bob-chat-header">
            <div className="bob-chat-header-left">
              <span className="bob-chat-header-icon">🤖</span>
              <div>
                <div className="bob-chat-header-title">Bob MCP Chat</div>
                <div className="bob-chat-header-subtitle">
                  <span className="bob-chat-live-dot" />
                  Database-only · No hallucination
                </div>
              </div>
            </div>
            <button className="bob-chat-close" onClick={() => setIsOpen(false)} aria-label="Close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
            </button>
          </div>

          {/* Messages */}
          <div className="bob-chat-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`bob-chat-msg ${msg.role}`}>
                {msg.role === 'bot' && (
                  <div className="bob-chat-msg-avatar">🛡️</div>
                )}
                <div className={`bob-chat-bubble ${msg.role} ${msg.type === 'error' || msg.type === 'not_found' ? 'error' : ''} ${msg.type === 'unknown' ? 'unknown' : ''}`}>
                  <div dangerouslySetInnerHTML={{ __html: formatResponse(msg.text) }} />
                  {msg.data && (msg.type === 'site_detail' || msg.type === 'site_risk' || msg.type === 'site_deviations' || msg.type === 'capa_report') && (
                    <button
                      className="bob-chat-link-btn"
                      onClick={() => handleNavigate(msg.data, msg.type)}
                    >
                      View in Dashboard →
                    </button>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="bob-chat-msg bot">
                <div className="bob-chat-msg-avatar">🛡️</div>
                <div className="bob-chat-bubble bot">
                  <div className="bob-chat-typing">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Actions */}
          {messages.length <= 2 && (
            <div className="bob-chat-quick-actions">
              {QUICK_ACTIONS.map((qa) => (
                <button
                  key={qa.message}
                  className="bob-chat-quick-btn"
                  onClick={() => handleSend(qa.message)}
                  disabled={loading}
                >
                  {qa.label}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="bob-chat-input-bar">
            <input
              ref={inputRef}
              className="bob-chat-input"
              type="text"
              placeholder="Ask about a site, patient, or deviation..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              className="bob-chat-send"
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              aria-label="Send"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" /></svg>
            </button>
          </div>
        </div>
      )}
    </>
  )
}
