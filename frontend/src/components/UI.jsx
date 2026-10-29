import { cloneElement, useEffect, useId, useRef } from 'react'
import { safeUrl } from '../services/chatApi.js'

const paths = {
  book: 'M4 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-3H4z M20 4h-4a3 3 0 0 0-3 3v14a4 4 0 0 1 4-3h3z',
  chat: 'M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-2 2v-9.5A8.5 8.5 0 0 1 10.5 4h2a8.5 8.5 0 0 1 8.5 7.5z M7 10h10 M7 14h6',
  search: 'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0z',
  plus: 'M12 5v14 M5 12h14',
  arrow: 'M5 12h14 M13 6l6 6-6 6',
  send: 'M22 2L9 15 M22 2l-7 20-6-7-7-6z',
  clock: 'M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z',
  user: 'M20 21v-2a6 6 0 0 0-6-6h-4a6 6 0 0 0-6 6v2 M16 6a4 4 0 1 1-8 0 4 4 0 0 1 8 0z',
  shield: 'M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7z M8 12l3 3 5-6',
  link: 'M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-2 2 M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l2-2',
  trash: 'M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7',
  mic: 'M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z M5 10v2a7 7 0 0 0 14 0v-2 M12 19v3 M8 22h8',
  volume: 'M11 5L6 9H2v6h4l5 4z M15 8a6 6 0 0 1 0 8 M18 4a11 11 0 0 1 0 16',
  stop: 'M6 6h12v12H6z',
  close: 'M6 6l12 12 M6 18L18 6',
  menu: 'M4 6h16 M4 12h16 M4 18h16',
  download: 'M12 3v12 M7 10l5 5 5-5 M4 16v5h16v-5',
  check: 'M5 12l4 4L19 6',
  globe: 'M2 12h20 M12 2a17 17 0 0 1 0 20 17 17 0 0 1 0-20 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z',
  edit: 'M16 3l5 5-12 12H4v-5z M13 6l5 5',
  refresh: 'M20 7v5h-5 M4 17v-5h5 M5 8a8 8 0 0 1 13-3l2 3 M19 16a8 8 0 0 1-13 3l-2-3',
  info: 'M12 11v6 M12 7h.01 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0z',
  thumb: 'M7 10v11H3V10z M7 10l5-8a3 3 0 0 1 2 4l-1 4h6a2 2 0 0 1 2 2l-2 8H7',
}
export function Icon({ name, size = 20, ...props }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d={paths[name] || paths.book} /></svg>
}
export const ErrorNotice = ({ children }) => children ? <div className="notice error" role="alert"><Icon name="info" /><span>{children}</span></div> : null
export const Notice = ({ children }) => <div className="notice"><Icon name="info" /><span>{children}</span></div>
export function Empty({ icon = 'book', title, children }) {
  return <div className="empty"><div className="empty-icon"><Icon name={icon} size={30} /></div><h3>{title}</h3><p>{children}</p></div>
}
export function ExternalLink({ href, children, ...props }) {
  const url = safeUrl(href)
  return url ? <a href={url} target="_blank" rel="noopener noreferrer" {...props}>{children}</a> : <span {...props}>{children}</span>
}
export function Modal({ title, onClose, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const node = ref.current
    node.showModal()
    return () => { if (node.open) node.close() }
  }, [])
  return <dialog ref={ref} className="modal" aria-label={title} onCancel={event => { event.preventDefault(); onClose() }} onClick={event => { if (event.target === ref.current) onClose() }}>
    <div className="modal-head"><h2>{title}</h2><button type="button" className="icon-button" aria-label="Đóng hộp thoại" onClick={onClose}><Icon name="close" /></button></div>
    {children}
  </dialog>
}
export function Field({ label, children, hint }) {
  const hintId = useId()
  return <div className="field"><label className="field-control"><span>{label}</span>{hint ? cloneElement(children, { 'aria-describedby': hintId }) : children}</label>{hint && <small id={hintId}>{hint}</small>}</div>
}
export function Status({ value }) {
  if (value === 'closed') return <span className="badge warning">Nghỉ phục vụ cả ngày</span>
  if (value === 'succeeded') return <span className="badge success">Đã xác nhận thành công</span>
  const labels = { answered: 'Đã có câu trả lời', clarify: 'Cần làm rõ', not_found: 'Chưa đủ thông tin', verified: 'Đã xác minh', reviewed_public: 'Nguồn công khai đã duyệt', needs_confirmation: 'Cần xác nhận', draft: 'Bản nháp', fallback: 'Tra cứu dự phòng', faq: 'Kho tri thức', rag: 'AI có nguồn', confirmed: 'Đã xác nhận', renewed: 'Đã gia hạn theo phản hồi thư viện', pending: 'Chờ đối soát', uncertain: 'Chờ đối soát', failed: 'Thất bại', completed: 'Hoàn tất', done: 'Hoàn tất', running: 'Đang chạy', queued: 'Đang chờ' }
  return <span className={`badge ${['verified', 'confirmed', 'renewed', 'done', 'completed'].includes(value) ? 'success' : ['needs_confirmation', 'pending', 'uncertain', 'failed', 'not_found'].includes(value) ? 'warning' : ''}`}>{labels[value] || value || 'Chưa có trạng thái'}</span>
}
export const displayDate = value => value ? new Date(value).toLocaleDateString('vi-VN') : 'Chưa cập nhật'
