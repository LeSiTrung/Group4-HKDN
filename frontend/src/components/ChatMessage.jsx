import { useState } from 'react'
import { api } from '../services/chatApi.js'
import { displayDate, ErrorNotice, ExternalLink, Icon, Status } from './UI.jsx'

export default function ChatMessage({ item, user, onSpeak }) {
  const [feedback, setFeedback] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function rate(rating) {
    setBusy(true); setError('')
    try { await api('/feedback', { method: 'POST', body: { message_id: item.id, rating } }); setFeedback(rating) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  const assistant = item.role === 'assistant'
  return <article className={`message ${assistant ? 'assistant' : 'user-message'}`}>
    <div className={`avatar ${assistant ? '' : 'reader-avatar'}`} aria-hidden="true">{assistant ? <Icon name="book" size={19} /> : <Icon name="user" size={18} />}</div>
    <div className="message-main"><div className="message-meta"><strong>{assistant ? 'Trợ lý Thư viện' : user?.name || 'Bạn'}</strong>{assistant && item.mode && <Status value={item.mode} />}</div>
      <div className="message-content">{item.content}</div>
      {item.books?.length > 0 && <div className="chat-books"><p className="chat-books-note">Biểu ghi có nguồn đối chiếu, không phải tình trạng mượn thời gian thực.</p>{item.books.map((book, index) => <article className="chat-book-card" key={book.id || index}><div className="inline-actions"><Icon name="book" size={17} /><ExternalLink href={book.url || book.source_url}><strong>{book.title}</strong></ExternalLink></div><p>{book.author || 'Chưa có tác giả'}{book.year ? ` · ${book.year}` : ''}</p>{book.description && <p className="catalog-description">{book.description}</p>}{book.checked_at && <small>Đối chiếu: {displayDate(book.checked_at)}</small>}</article>)}</div>}
      {assistant && item.status && <div className="message-status"><Status value={item.status} /></div>}
      {item.sources?.length > 0 && <div className="sources"><span className="eyebrow">NGUỒN THAM KHẢO</span>{item.sources.map((source, index) => <ExternalLink className="source-link" key={`${source.url}-${index}`} href={source.url}><span className="source-number">{index + 1}</span><span><strong>{source.title || 'Nguồn thư viện'}</strong><small>{source.checked_at ? `Đối chiếu: ${displayDate(source.checked_at)}` : 'Liên kết tra cứu; chưa kiểm tra kết quả'}</small></span><Icon name="link" size={16} /></ExternalLink>)}</div>}
      {assistant && <div className="message-actions">
        <button className="text-button" type="button" onClick={() => onSpeak(item.content)}><Icon name="volume" size={16} /> Đọc câu trả lời</button>
        {user && item.id && <>
          <button type="button" className="icon-button small" title="Câu trả lời hữu ích" aria-label="Câu trả lời hữu ích" aria-pressed={feedback === 1} disabled={busy} onClick={() => rate(1)}><Icon name="thumb" size={16} /></button>
          <button type="button" className="icon-button small" title="Câu trả lời chưa hữu ích" aria-label="Câu trả lời chưa hữu ích" aria-pressed={feedback === -1} disabled={busy} onClick={() => rate(-1)}><Icon name="thumb" size={16} style={{ transform: 'rotate(180deg)' }} /></button>
          {feedback && <small>Đã gửi đánh giá</small>}
        </>}
      </div>}
      <ErrorNotice>{error}</ErrorNotice>
    </div>
  </article>
}
