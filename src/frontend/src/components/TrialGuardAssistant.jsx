import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
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
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()

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

  return (
    <>
      {/* Floating Action Button */}
      <button
        className={`tg-assistant-launcher ${isOpen ? 'active' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Toggle TrialGuard Assistant"
        title="Open TrialGuard Assistant"
      >
        <span className="tg-launcher-icon">🛡️</span>
        <span className="tg-launcher-text">Ask Assistant</span>
        <span className="tg-launcher-badge">Live</span>
      </button>

      {/* Floating Chat Drawer */}
      {isOpen && (
        <div className="tg-assistant-container">
          {/* Header */}
          <div className="tg-assistant-header">
            <div className="tg-header-info">
              <span className="tg-header-avatar">🤖</span>
              <div>
                <h3 className="tg-header-title">TrialGuard Assistant</h3>
                <span className="tg-header-status">
                  <span className="tg-status-dot"></span> MCP Engine Active
                </span>
              </div>
            </div>
            <div className="tg-header-actions">
              <button
                className="tg-icon-btn"
                onClick={handleClearChat}
                title="Clear Chat History"
              >
                🧹
              </button>
              <button
                className="tg-icon-btn"
                onClick={() => setIsOpen(false)}
                title="Close Assistant"
              >
                ✕
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
                  <div className="tg-msg-avatar">🛡️</div>
                )}
                <div className="tg-msg-content">
                  {msg.toolUsed && (
                    <div className="tg-tool-badge">
                      <span className="tg-tool-icon">⚡</span>
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
                        onClick={() => {
                          navigate(`/sites/${msg.siteId}`)
                          setIsOpen(false)
                        }}
                      >
                        🏥 View {msg.siteId} Dashboard
                      </button>
                      <button
                        className="tg-btn-action"
                        onClick={() => {
                          navigate(`/capa/${msg.siteId}`)
                          setIsOpen(false)
                        }}
                      >
                        📋 Open Full CAPA Report
                      </button>
                    </div>
                  )}

                  <span className="tg-msg-time">{msg.timestamp}</span>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="tg-message tg-msg-assistant">
                <div className="tg-msg-avatar">🛡️</div>
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
              title="Send Message"
            >
              ➤
            </button>
          </form>
        </div>
      )}
    </>
  )
}
