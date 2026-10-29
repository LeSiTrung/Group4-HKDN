import { Icon } from './UI.jsx'

export default function ChatInput({ value, onChange, onSend, busy, onVoice, listening }) {
  return <form className="composer" aria-label="Gửi câu hỏi" onSubmit={event => { event.preventDefault(); onSend(value) }}>
    <label className="sr-only" htmlFor="chat-question">Câu hỏi của bạn</label>
    <textarea id="chat-question" rows={2} maxLength={2000} value={value} onChange={event => onChange(event.target.value)} placeholder="Hỏi trợ lý về tài liệu, dịch vụ thư viện…" onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); if (!busy) onSend(value) } }} />
    <div className="composer-bottom"><span className="composer-hint">Enter để gửi · Shift + Enter để xuống dòng</span><div className="inline-actions"><button type="button" className={`icon-button ${listening ? 'listening' : ''}`} onClick={onVoice} aria-label={listening ? 'Dừng ghi âm' : 'Nhập bằng giọng nói'} aria-pressed={listening} disabled={busy}><Icon name={listening ? 'stop' : 'mic'} /></button><button type="submit" className="primary send-button" disabled={busy || !value.trim()} aria-label="Gửi câu hỏi"><Icon name="send" size={18} /><span>{busy ? 'Đang gửi' : 'Gửi'}</span></button></div></div>
  </form>
}
