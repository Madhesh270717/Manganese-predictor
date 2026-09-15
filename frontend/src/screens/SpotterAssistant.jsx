import { useEffect, useRef, useState } from 'react'
import { apiPost } from '../services/api.js'
import './SpotterAssistant.css'

// Screen 7 — Spotter AI Assistant (PRD Section 37).
// Natural-language interface over the real backend modules: the backend
// classifies the question into intent(s), calls the actual models/engine,
// and returns a grounded answer + which functions/data sources were used.

const SUGGESTED_QUESTIONS = [
  'Why is production expected to fall?',
  'Which zone should we mine today?',
  'Why should we leave Zone A?',
  'Which equipment should be moved?',
  'How much manganese is estimated in Zone B?',
  'What happens if rainfall increases tomorrow?',
]

const WELCOME =
  "I'm Spotter AI. Ask me about reserves, production, and the mining schedule — " +
  'every answer is grounded in the live mine models.'

export default function SpotterAssistant() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: WELCOME },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const send = async (text) => {
    const question = (text ?? input).trim()
    if (!question || loading) return
    setInput('')
    setError(null)

    // Rolling conversation history (user/assistant pairs only) for
    // multi-turn context — the backend carries the relevant context.
    const history = messages
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, content: m.content }))

    const userMessage = { role: 'user', content: question }
    setMessages((prev) => [...prev, userMessage])
    setLoading(true)

    try {
      const payload = await apiPost('/api/v1/assistant/chat', {
        message: question,
        conversation_history: history,
      })
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: payload.response,
          functions_called: payload.functions_called || [],
          data_sources_used: payload.data_sources_used || [],
        },
      ])
    } catch (err) {
      setError(err.message || 'Could not reach the assistant.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="assistant">
      <header className="assistant-header">
        <h1>SPOTTER AI</h1>
        <span className="assistant-subtitle">
          Natural-language mine intelligence — grounded in live model results
        </span>
      </header>

      <div className="chat-card">
        <div className="chat-history" aria-live="polite">
          {messages.map((msg, i) => (
            <div key={i} className={`chat-row ${msg.role}`}>
              <div className="chat-bubble">
                <span className="chat-sender">
                  {msg.role === 'user' ? 'You' : 'Spotter'}
                </span>
                <p className="chat-text">{msg.content}</p>
                {msg.data_sources_used && msg.data_sources_used.length > 0 && (
                  <div className="chat-sources">
                    Based on: {msg.data_sources_used.join(', ')}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="chat-row assistant">
              <div className="chat-bubble">
                <span className="chat-sender">Spotter</span>
                <div className="typing-indicator">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && <div className="chat-error">⚠ {error}</div>}

        {messages.length <= 1 && !loading && (
          <div className="suggestions">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                className="suggestion-chip"
                onClick={() => send(q)}
              >
                {q}
              </button>
            ))}
          </div>
        )}

        <form
          className="chat-input-row"
          onSubmit={(e) => {
            e.preventDefault()
            send()
          }}
        >
          <input
            className="chat-input"
            type="text"
            placeholder="Ask Spotter AI..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            aria-label="Ask Spotter AI"
          />
          <button className="chat-send" type="submit" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  )
}
