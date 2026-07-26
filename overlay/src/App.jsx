import { useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/ask'

export default function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    const question = input.trim()
    if (!question || pending) return

    setMessages((prev) => [...prev, { role: 'user', text: question }])
    setInput('')
    setPending(true)
    setMessages((prev) => [...prev, { role: 'assistant', text: 'Thinking...' }])

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setMessages((prev) => [...prev.slice(0, -1), { role: 'assistant', text: data.answer }])
    } catch (err) {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: 'assistant', text: "Couldn't reach the advisor backend - is it running?" },
      ])
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="app">
      <div className="scrollback">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            {m.text}
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about a build, item, or gem..."
          disabled={pending}
        />
      </form>
    </div>
  )
}
