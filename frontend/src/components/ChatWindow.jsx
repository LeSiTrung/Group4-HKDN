import { useEffect, useRef, useState } from 'react'
import { api, sendMessage } from '../services/chatApi.js'
import ChatInput from './ChatInput.jsx'
import ChatMessage from './ChatMessage.jsx'
import { ErrorNotice, Icon, Notice } from './UI.jsx'
import readingRoom from '../assets/reading-room.jpg'

const starters = [
  { icon: 'search', title: 'Cách tra cứu tài liệu', text: 'Làm thế nào để tra cứu sách tại thư viện?' },
  { icon: 'book', title: 'Mượn & trả sách', text: 'Tôi cần chuẩn bị gì để mượn sách?' },
  { icon: 'clock', title: 'Giờ phục vụ', text: 'Tôi có thể kiểm tra giờ mở cửa ở đâu?' },
  { icon: 'globe', title: 'Thư viện số', text: 'Làm thế nào để truy cập tài liệu điện tử?' },
]
const contextExcerptMarker = '\n[Trích đoạn ngữ cảnh; phần còn lại không được gửi.]'
const waitingLabels = [
  'Trợ lý đang trả lời…',
  'Đang đối chiếu danh mục và nguồn tài liệu…',
  'Đang tổng hợp câu trả lời từ nguồn thư viện, vui lòng đợi thêm giây lát…',
]
export default function ChatWindow({ user, conversationId, onCreated }) {
  const [messages, setMessages] = useState([])
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [waitStage, setWaitStage] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(Boolean(user && conversationId))
  const [error, setError] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [listening, setListening] = useState(false)
  const [speechView, setSpeechView] = useState(null)
  const activeId = useRef(conversationId)
  const recognition = useRef(null)
  const speech = useRef(null)
  const end = useRef(null)
  const mounted = useRef(true)
  const sending = useRef(false)
  const conversationVersion = useRef(0)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; recognition.current?.abort(); clearSpeech() }
  }, [])
  useEffect(() => {
    const version = ++conversationVersion.current
    activeId.current = conversationId
    sending.current = false
    stopSpeech()
    setMessages([]); setMessage(''); setSuggestions([]); setError(''); setBusy(false)
    setHistoryLoading(Boolean(user && conversationId))
    if (!user || !conversationId) return
    api(`/conversations/${conversationId}`).then(data => { if (version === conversationVersion.current) setMessages(data.messages || []) }).catch(err => { if (version === conversationVersion.current) setError(err.message) }).finally(() => { if (version === conversationVersion.current) setHistoryLoading(false) })
    return () => { conversationVersion.current++ }
  }, [user?.id, conversationId])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'instant', block: 'end' }) }, [messages, busy])
  useEffect(() => {
    if (!busy) { setWaitStage(0); return }
    const first = setTimeout(() => setWaitStage(1), 2500)
    const second = setTimeout(() => setWaitStage(2), 8000)
    return () => { clearTimeout(first); clearTimeout(second) }
  }, [busy])

  async function send(text) {
    const question = text
    if (!question.trim() || sending.current || historyLoading) return
    const version = conversationVersion.current
    const turn = { role: 'user', content: question }
    sending.current = true
    setBusy(true); setError(''); setSuggestions([])
    setMessages(current => [...current, turn])
    setMessage('')
    try {
      const history = user ? undefined : messages.filter(item => ['user', 'assistant'].includes(item.role)).slice(-6).map(item => ({ role: item.role, content: item.content.length > 2000 ? `${item.content.slice(0, 2000 - contextExcerptMarker.length)}${contextExcerptMarker}` : item.content,
        ...(item.role === 'assistant' && item.books?.length ? { book_ids: item.books.filter(book => Number.isSafeInteger(book.id) && book.id > 0).slice(0, 5).map(book => book.id) } : {}),
        ...(item.role === 'assistant' && item.list_book_ids?.length
          ? { list_book_ids: item.list_book_ids.filter(id => Number.isSafeInteger(id) && id > 0).slice(0, 5) } : {}) }))
      const result = await sendMessage(question, activeId.current, history)
      if (!mounted.current || version !== conversationVersion.current) return
      activeId.current = result.conversation_id
      setMessages(current => [...current, { role: 'assistant', content: result.answer, id: result.message_id, sources: result.sources, status: result.status, mode: result.mode, books: result.books, list_book_ids: result.list_book_ids }])
      setSuggestions(result.suggestions || [])
      onCreated?.(result.conversation_id)
    } catch (err) {
      if (mounted.current && version === conversationVersion.current) {
        setMessages(current => current.filter(item => item !== turn))
        setError(err.message)
        setMessage(current => current || question)
        if (err.code === 'chat_history_changed') {
          try {
            const updated = await api(`/conversations/${activeId.current}`)
            if (mounted.current && version === conversationVersion.current) {
              setMessages(updated.messages)
            }
          } catch {
            if (mounted.current && version === conversationVersion.current) {
              setError('Chưa tải được tin nhắn mới. Bạn có thể sao chép câu hỏi rồi mở lại hội thoại.')
            }
          }
        }
      }
    } finally { if (mounted.current && version === conversationVersion.current) { sending.current = false; setBusy(false) } }
  }
  function voice() {
    setError('')
    if (listening) { recognition.current?.stop(); return }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) { setError('Trình duyệt chưa hỗ trợ nhận dạng giọng nói. Bạn có thể nhập câu hỏi bằng bàn phím hoặc thử Chrome/Edge.'); return }
    const instance = new SpeechRecognition()
    recognition.current = instance
    instance.lang = 'vi-VN'; instance.interimResults = false; instance.maxAlternatives = 1
    instance.onresult = event => { if (mounted.current) setMessage(current => `${current}${current ? ' ' : ''}${event.results[0][0].transcript}`) }
    instance.onerror = event => { if (mounted.current) { setListening(false); setError(event.error === 'not-allowed' ? 'Chưa được cấp quyền micro. Hãy cho phép micro trong cài đặt trình duyệt.' : 'Không nhận được giọng nói. Hãy thử lại hoặc nhập câu hỏi bằng bàn phím.') } }
    instance.onend = () => { if (mounted.current) setListening(false) }
    try { instance.start(); setListening(true) } catch { setError('Không thể mở micro. Hãy kiểm tra quyền truy cập và thử lại.') }
  }
  function clearSpeech() {
    const current = speech.current
    speech.current = null
    if (current?.utterance) window.speechSynthesis.cancel()
    if (current?.url) URL.revokeObjectURL(current.url)
  }
  function stopSpeech() {
    clearSpeech()
    setSpeechView(null)
  }
  function speechFailed(item, error) {
    clearSpeech()
    setSpeechView({ item, error })
  }
  function speak(item) {
    const alreadySpeaking = speech.current?.item === item
    stopSpeech()
    if (alreadySpeaking) return
    const text = item.content
    const current = { item }
    speech.current = current
    async function playServerSpeech() {
      if (speech.current !== current) return
      delete current.utterance
      setSpeechView({ item, loading: true })
      try {
        if ([...text].length > 4000) throw new Error('Giọng đọc của máy chủ hỗ trợ câu trả lời dài tối đa 4.000 ký tự.')
        const audio = await api('/speech', { method: 'POST', body: { text }, responseType: 'audio' })
        if (speech.current !== current) return
        current.url = URL.createObjectURL(audio)
        setSpeechView({ item, url: current.url })
      } catch (error) {
        if (speech.current !== current) return
        speechFailed(item, error.message)
      }
    }
    const synthesis = window.speechSynthesis
    const voices = synthesis?.getVoices?.().filter(voice => voice.localService && /^vi(?:-|$)/i.test(voice.lang)) || []
    const voice = voices.find(voice => voice.lang.toLowerCase() === 'vi-vn') || voices[0]
    if (!voice || !window.SpeechSynthesisUtterance) { void playServerSpeech(); return }
    const utterance = new window.SpeechSynthesisUtterance(text)
    current.utterance = utterance
    setSpeechView({ item })
    utterance.voice = voice
    utterance.lang = voice.lang
    utterance.onend = () => { if (speech.current === current && current.utterance) stopSpeech() }
    utterance.onerror = playServerSpeech
    try { synthesis.speak(utterance) } catch { void playServerSpeech() }
  }
  return <section className="chat-workspace" aria-label="Trợ lý thư viện">
    <div className="chat-scroll">
      {historyLoading ? <div className="loading-state" role="status">Đang mở cuộc trò chuyện…</div> : messages.length === 0 ? <div className="welcome">
        <div className="welcome-banner">
          <div className="welcome-copy">
            <h1>Hỏi đáp<br />thư viện UTH</h1>
            <p>Tra cứu tài liệu, tìm hiểu dịch vụ và nhận hướng dẫn từ thư viện UTH.</p>
            <a href="#catalog" className="welcome-search">Mở mục tra cứu <Icon name="arrow" size={17} /></a>
          </div>
          <div className="welcome-media"><img className="welcome-photo" src={readingRoom} alt="" /></div>
        </div>
        <h2 className="starter-heading">Bạn muốn hỏi gì?</h2>
        <div className="starter-grid">{starters.map(item => <button key={item.title} className="starter-card" onClick={() => send(item.text)} disabled={busy}>
          <span className="starter-icon"><Icon name={item.icon} size={19} /></span>
          <span className="starter-copy"><strong>{item.title}</strong><span>{item.text}</span></span>
          <Icon className="card-arrow" name="arrow" size={16} />
        </button>)}</div>
      </div> : <div className="messages" aria-live="polite" aria-relevant="additions">{messages.map((item, index) => {
        const playback = speechView?.item === item ? speechView : null
        return <ChatMessage item={item} user={user} onSpeak={speak} key={item.id || `${item.role}-${index}`}
          isSpeaking={Boolean(playback && !playback.error)} speechControl={playback && <>
            {playback.loading && <p className="feedback-note" role="status">Đang tạo giọng đọc tiếng Việt…</p>}
            {playback.url && <audio key={playback.url} className="speech-player" controls autoPlay src={playback.url} aria-label="Phát giọng đọc tiếng Việt"
              onEnded={() => { if (speech.current?.url === playback.url) stopSpeech() }}
              onError={() => { if (speech.current?.url === playback.url) speechFailed(item, 'Trình duyệt không phát được âm thanh tiếng Việt.') }} />}
            <ErrorNotice>{playback.error}</ErrorNotice>
          </>} />
      })}{busy && <div className="typing" role="status"><span /><span /><span /><span className="typing-label">{waitingLabels[waitStage]}</span></div>}<div ref={end} /></div>}
    </div>
    <div className="chat-bottom">
      <ErrorNotice>{error}</ErrorNotice>
      {listening && <Notice>Đang nghe tiếng Việt… Nhấn dừng khi hoàn tất. Lời nói được chuyển thành chữ trước khi gửi; dịch vụ giọng nói phụ thuộc trình duyệt.</Notice>}
      {suggestions.length > 0 && <div className="suggestions">{suggestions.map((text, index) => <button key={`${text}-${index}`} onClick={() => send(text)} disabled={busy}>{text}<Icon name="arrow" size={14} /></button>)}</div>}
      <ChatInput value={message} onChange={setMessage} onSend={send} busy={busy || historyLoading} onVoice={voice} listening={listening} />
      <p className="composer-note">{user ? 'Lịch sử được lưu trong tài khoản.' : 'Phiên khách chỉ lưu trò chuyện khi trang này còn mở.'}</p>
    </div>
  </section>
}
