import { useEffect, useRef, useState } from 'react'
import { api, sendMessage } from '../services/chatApi.js'
import ChatInput from './ChatInput.jsx'
import ChatMessage from './ChatMessage.jsx'
import { ErrorNotice, Icon, Notice } from './UI.jsx'

const starters = [
  { icon: 'search', title: 'Tìm tài liệu', text: 'Làm thế nào để tra cứu sách tại thư viện?' },
  { icon: 'book', title: 'Mượn & trả sách', text: 'Tôi cần chuẩn bị gì để mượn sách?' },
  { icon: 'clock', title: 'Giờ phục vụ', text: 'Tôi có thể kiểm tra giờ mở cửa ở đâu?' },
  { icon: 'globe', title: 'Thư viện số', text: 'Làm thế nào để truy cập tài liệu điện tử?' },
]
export default function ChatWindow({ user, conversationId, onCreated }) {
  const [messages, setMessages] = useState([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(Boolean(user && conversationId))
  const [error, setError] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const activeId = useRef(conversationId)
  const recognition = useRef(null)
  const end = useRef(null)
  const mounted = useRef(true)
  const sending = useRef(false)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; recognition.current?.abort(); window.speechSynthesis?.cancel() }
  }, [])
  useEffect(() => {
    if (!user || !conversationId) return
    let ignore = false
    api(`/conversations/${conversationId}`).then(data => { if (!ignore) setMessages(data.messages || []) }).catch(err => { if (!ignore) setError(err.message) }).finally(() => { if (!ignore) setHistoryLoading(false) })
    return () => { ignore = true }
  }, [user, conversationId])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'instant', block: 'end' }) }, [messages, busy])

  async function send(text) {
    const question = text.trim()
    if (!question || sending.current || historyLoading) return
    sending.current = true
    setBusy(true); setError(''); setSuggestions([])
    setMessages(current => [...current, { role: 'user', content: question }])
    setMessage('')
    try {
      const history = user ? undefined : messages.filter(item => ['user', 'assistant'].includes(item.role)).slice(-6).map(item => ({ role: item.role, content: item.content.slice(0, 2000) }))
      const result = await sendMessage(question, activeId.current, history)
      if (!mounted.current) return
      activeId.current = result.conversation_id
      setMessages(current => [...current, { role: 'assistant', content: result.answer, id: result.message_id, sources: result.sources, status: result.status, mode: result.mode, books: result.books }])
      setSuggestions(result.suggestions || [])
      onCreated?.(result.conversation_id)
    } catch (err) {
      if (mounted.current) { setError(err.message); setMessage(current => current || question) }
    } finally { sending.current = false; if (mounted.current) setBusy(false) }
  }
  function voice() {
    setError('')
    if (listening) { recognition.current?.stop(); return }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) { setError('Trình duyệt chưa hỗ trợ nhận dạng giọng nói. Hãy nhập câu hỏi bằng bàn phím hoặc dùng Chrome/Edge hỗ trợ Web Speech.'); return }
    const instance = new SpeechRecognition()
    recognition.current = instance
    instance.lang = 'vi-VN'; instance.interimResults = false; instance.maxAlternatives = 1
    instance.onresult = event => { if (mounted.current) setMessage(current => `${current}${current ? ' ' : ''}${event.results[0][0].transcript}`.slice(0, 2000)) }
    instance.onerror = event => { if (mounted.current) { setListening(false); setError(event.error === 'not-allowed' ? 'Chưa được cấp quyền micro. Hãy cho phép micro trong cài đặt trình duyệt.' : `Không nhận được giọng nói (${event.error}). Bạn có thể nhập bằng bàn phím.`) } }
    instance.onend = () => { if (mounted.current) setListening(false) }
    try { instance.start(); setListening(true) } catch { setError('Không thể mở micro. Hãy kiểm tra quyền truy cập và thử lại.') }
  }
  function speak(text) {
    if (!window.speechSynthesis || !window.SpeechSynthesisUtterance) { setError('Trình duyệt chưa hỗ trợ đọc văn bản.'); return }
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'vi-VN'; utterance.onend = () => setSpeaking(false); utterance.onerror = () => { setSpeaking(false); setError('Không thể đọc văn bản bằng giọng nói trên trình duyệt này.') }
    window.speechSynthesis.speak(utterance); setSpeaking(true)
  }
  return <section className="chat-workspace" aria-label="Trợ lý thư viện">
    <div className="chat-scroll">
      {historyLoading ? <div className="loading-state" role="status">Đang mở cuộc trò chuyện…</div> : messages.length === 0 ? <div className="welcome">
        <span className="eyebrow">KHÔNG GIAN TRI THỨC CỦA BẠN</span>
        <div className="welcome-symbol"><Icon name="book" size={42} /><span className="orbit-dot" /></div>
        <h1>Xin chào{user ? `, ${user.name.split(' ').at(-1)}` : ' bạn'}.<br />Hôm nay bạn muốn<br /><em>khám phá điều gì?</em></h1>
        <p>Tra cứu tài liệu, tìm hiểu dịch vụ và nhận hướng dẫn<br className="desktop-break" /> từ những nguồn thông tin của thư viện UTH.</p>
        <div className="starter-grid">{starters.map(item => <button key={item.title} className="starter-card" onClick={() => send(item.text)} disabled={busy}><Icon name={item.icon} /><strong>{item.title}</strong><span>{item.text}</span><Icon className="card-arrow" name="arrow" size={16} /></button>)}</div>
      </div> : <div className="messages" aria-live="polite" aria-relevant="additions">{messages.map((item, index) => <ChatMessage item={item} user={user} onSpeak={speak} key={item.id || `${item.role}-${index}`} />)}{busy && <div className="typing" role="status"><span /><span /><span /><span className="typing-label">D7 đang đối chiếu nguồn…</span></div>}<div ref={end} /></div>}
    </div>
    <div className="chat-bottom">
      <ErrorNotice>{error}</ErrorNotice>
      {listening && <Notice>Đang nghe tiếng Việt… Nhấn dừng khi hoàn tất. Bản ghi được chuyển thành chữ trước khi gửi; dịch vụ giọng nói phụ thuộc trình duyệt.</Notice>}
      {speaking && <button className="text-button stop-speaking" onClick={() => { window.speechSynthesis.cancel(); setSpeaking(false) }}><Icon name="stop" size={16} /> Dừng đọc</button>}
      {suggestions.length > 0 && <div className="suggestions">{suggestions.map((text, index) => <button key={`${text}-${index}`} onClick={() => send(text)} disabled={busy}>{text}<Icon name="arrow" size={14} /></button>)}</div>}
      <ChatInput value={message} onChange={setMessage} onSend={send} busy={busy || historyLoading} onVoice={voice} listening={listening} />
      <p className="composer-note"><Icon name="shield" size={13} /> Thông tin chính sách cần nguồn còn hiệu lực. {user ? 'Lịch sử được lưu trong tài khoản.' : 'Khách: lịch sử chỉ lưu trong phiên đang mở.'}</p>
    </div>
  </section>
}
