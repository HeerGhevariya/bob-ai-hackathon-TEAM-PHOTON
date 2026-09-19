import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bot, Zap, Send, Hospital, ClipboardList } from 'lucide-react'
import { sendChatMessage } from '../utils/api'
import './GlobalMcpChat.css'

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
    .replace(/## (.*)/g, '<h3 style="font-size: 18px; margin: 16px 0 8px; color: var(--text-primary);">$1</h3>')
    .replace(/### (.*)/g, '<h4 style="font-size: 15px; margin: 12px 0 6px; color: var(--text-primary);">$1</h4>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.*?)`/g, '<code style="background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px; font-family: monospace;">$1</code>')
    .replace(/_(.*?)_/g, '<em>$1</em>')
    .replace(/\n• /g, '<br/><span style="color: var(--accent); margin-right: 6px;">•</span> ')
    .replace(/\n- /g, '<br/><span style="color: var(--accent); margin-right: 6px;">•</span> ')
    .replace(/\n(\d+)\. /g, '<br/><span style="color: var(--accent); font-weight: bold; margin-right: 6px;">$1.</span> ')
    .replace(/\n/g, '<br/>')
}

export default function GlobalMcpChat() {
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      text: '🛡️ **Global TrialGuard AI — Deep Analysis Mode**\n\nI look up real data from the PHOENIX-301 trial database and provide **in-depth, detailed analysis**. No guesses, no made-up answers.\n\n**Try asking:**\n• `Show me SITE-042`\n• `Trial summary`\n• `Top risk sites`\n• `Deviations for SITE-015`',
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [suggestions, setSuggestions] = useState(DEFAULT_SUGGESTIONS)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    setTimeout(() => inputRef.current?.focus(), 100)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function handleSend(messageText) {
    const text = (messageText || input).trim()
    if (!text || loading) return

    setInput('')
    setMessages((prev) => [...prev, { role: 'user', text }])
    setLoading(true)

    try {
      // Append instruction for in-depth analysis to the actual sent query
      const detailedQuery = text + '\\n\\n(Please provide a very detailed, in-depth, and comprehensive analysis.)'
      const result = await sendChatMessage(detailedQuery)
      
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          text: result.reply || result.response || 'No response received.',
          toolUsed: result.tool_used || null,
          siteId: result.site_id || null,
        },
      ])
      
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
  }

  return (
    <div className="global-chat-page animate-in">
      {/* Header */}
      <div className="global-chat-header">
        <div className="global-chat-title-group">
          <div className="global-chat-icon"><Bot size={22} /></div>
          <div>
            <div className="global-chat-title">Global MCP Deep Analysis Chat</div>
            <div className="global-chat-subtitle">
              <span className="global-chat-live-dot" />
              In-Depth AI Assistant
            </div>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="global-chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`global-chat-msg ${msg.role}`}>
            {msg.role === 'bot' && <div className="global-chat-avatar"><Bot size={18} /></div>}
            <div className="global-chat-bubble">
              {msg.toolUsed && (
                <div className="global-chat-tool-badge">
                  <Zap size={11} />
                  <span>MCP Tool: <strong>{msg.toolUsed}</strong></span>
                </div>
              )}
              <div dangerouslySetInnerHTML={{ __html: formatResponse(msg.text) }} />
              
              {msg.siteId && (
                <div className="global-chat-site-actions">
                  <button
                    className="global-chat-link-btn"
                    onClick={() => handleNavigate(msg.siteId, 'site')}
                  >
                    <Hospital size={12} /> View {msg.siteId} Dashboard
                  </button>
                  <button
                    className="global-chat-link-btn"
                    onClick={() => handleNavigate(msg.siteId, 'capa')}
                  >
                    <ClipboardList size={12} /> View CAPA Report
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {loading && (
          <div className="global-chat-msg bot">
            <div className="global-chat-avatar"><Bot size={18} /></div>
            <div className="global-chat-bubble">
              <div className="global-chat-typing">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggestions */}
      <div className="global-chat-suggestions">
        {suggestions.map((s, i) => (
          <button
            key={i}
            className="global-chat-suggestion-chip"
            onClick={() => handleSend(s.replace(/^[^\w]*/, ''))}
            disabled={loading}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="global-chat-input-area">
        <input
          ref={inputRef}
          className="global-chat-input"
          type="text"
          placeholder="Ask about site risk, deviations, CAPA for a detailed analysis..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button
          className="global-chat-send"
          onClick={() => handleSend()}
          disabled={!input.trim() || loading}
          aria-label="Send message"
          title="Send message"
        >
          <Send size={20} />
        </button>
      </div>
    </div>
  )
}
