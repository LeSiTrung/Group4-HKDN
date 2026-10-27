import { useState } from 'react'
import { sendMessage } from './services/chatApi.js'

const initialMessages = [
  {
    role: 'assistant',
    content: 'Xin chào! Mình là chatbot thư viện D7. Bạn muốn hỏi gì về thư viện?',
  },
]

export default function App() {
  const [messages, setMessages] = useState(initialMessages)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    const text = message.trim()
    if (!text || loading) return

    setMessages((current) => [...current, { role: 'user', content: text }])
    setMessage('')
    setLoading(true)

    try {
      const result = await sendMessage(text)
      setMessages((current) => [
        ...current,
        { role: 'assistant', content: result.answer },
      ])
    } catch {
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: 'Chưa kết nối được backend. Hãy kiểm tra API tại http://127.0.0.1:8000/health.',
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="page">
      <section className="chat-card">
        <header className="header">
          <div className="logo" aria-hidden="true">D7</div>
          <div>
            <h1>Chatbot Thư viện UTH</h1>
            <p>Trợ lý thông tin thư viện · Bản khung demo</p>
          </div>
        </header>

        <div className="notice">
          Bản hiện tại dùng câu trả lời mẫu, chưa tích hợp AI hoặc dữ liệu thư viện thật.
        </div>

        <div className="messages" aria-live="polite">
          {messages.map((item, index) => (
            <div className={`message ${item.role}`} key={`${item.role}-${index}`}>
              <span className="role">{item.role === 'user' ? 'Bạn' : 'D7'}</span>
              <p>{item.content}</p>
            </div>
          ))}
          {loading && <div className="typing">D7 đang xử lý…</div>}
        </div>

        <form className="composer" onSubmit={handleSubmit}>
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Nhập câu hỏi về thư viện..."
            aria-label="Câu hỏi"
            maxLength={2000}
          />
          <button type="submit" disabled={loading || !message.trim()}>
            Gửi
          </button>
        </form>
        <footer>Đề tài D7 · Học kỳ doanh nghiệp</footer>
      </section>
    </main>
  )
}
