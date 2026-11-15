import { useEffect, useRef, useState } from 'react'
import { api } from '../services/chatApi.js'
import { displayDate, ErrorNotice, Modal, Notice } from './UI.jsx'

const path = '/demo/reservations'
const actions = {
  reserve: { label: 'Đăng ký mượn', confirm: 'Xác nhận đăng ký', title: 'Xác nhận đăng ký giả lập', notice: 'Đã lưu đăng ký giả lập.', method: 'PUT' },
  cancel: { label: 'Hủy đăng ký', confirm: 'Xác nhận hủy', title: 'Xác nhận hủy giả lập', notice: 'Đã hủy đăng ký giả lập.', method: 'DELETE' },
  checkout: { label: 'Nhận sách', confirm: 'Xác nhận nhận sách', title: 'Nhận sách mẫu', notice: 'Đã nhận sách mẫu.', method: 'POST' },
  renew: { label: 'Gia hạn', confirm: 'Xác nhận gia hạn', title: 'Gia hạn sách mẫu', notice: 'Đã gia hạn khoản mượn mẫu.', method: 'POST' },
  return: { label: 'Trả sách', confirm: 'Xác nhận trả sách', title: 'Trả sách mẫu', notice: 'Đã trả sách mẫu.', method: 'POST' },
}

export default function DemoLibrary({ enabled, user, sessionLoading, onLogin }) {
  const [books, setBooks] = useState(null)
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    if (!enabled || !user) return
    let ignore = false
    api(path).then(data => { if (!ignore) setBooks(data.books) })
      .catch(err => { if (!ignore) setError(err.message) })
    return () => { ignore = true }
  }, [enabled, user, refresh])

  async function confirm() {
    if (pending.current) return
    pending.current = true
    setBusy(true); setError(''); setNotice('')
    const { book, action } = selected
    const details = actions[action]
    try {
      const endpoint = `${path}/${book.id}${details.method === 'POST' ? `/${action}` : ''}`
      const data = await api(endpoint, { method: details.method })
      if (action === 'cancel') setRefresh(value => value + 1)
      else setBooks(data.books)
      setSelected(null)
      setNotice(details.notice)
    } catch (err) {
      setSelected(null)
      setError(err.message)
      setRefresh(value => value + 1)
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  function actionButton(book, action, disabled = false) {
    const label = actions[action].label
    return <button className={action === 'cancel' ? 'secondary' : 'primary'} disabled={busy || disabled}
      aria-label={`${label} ${book.title}`} onClick={() => setSelected({ book, action })}>{label}</button>
  }

  return <section className="content-page">
    <h1>Thư viện mẫu</h1>
    <Notice>Thử đăng ký, nhận, gia hạn và trả sách trong kho giả lập. Hạn mượn mẫu là 7 ngày và có thể gia hạn một lần thêm 7 ngày trước khi quá hạn.</Notice>
    {enabled === undefined ? <p>Đang kiểm tra tính năng…</p> : !enabled ? <p>Thư viện mẫu hiện chưa được bật.</p>
      : sessionLoading ? <p>Đang kiểm tra phiên…</p> : !user ? <button className="primary" onClick={onLogin}>Đăng nhập để đăng ký mượn</button> : <>
        <ErrorNotice>{error}</ErrorNotice>
        {error && <button className="secondary" onClick={() => { setError(''); setRefresh(value => value + 1) }}>Tải lại danh mục mẫu</button>}
        {notice && <p role="status">{notice}</p>}
        {!books && !error && <p>Đang tải danh mục mẫu…</p>}
        <div className="chat-books">{books?.map(book => <article className="chat-book-card" key={book.id}>
          <h3>{book.title}</h3>
          <p>{book.available > 0 ? `Còn ${book.available} bản mẫu` : 'Hết bản mẫu'}</p>
          {book.due_date ? <>
            <p><strong>Đang mượn mẫu</strong> · Hạn trả {displayDate(book.due_date)}</p>
            {book.renewed && <p>Đã dùng lượt gia hạn mẫu.</p>}
            <div className="form-actions">{actionButton(book, 'renew', book.renewed)}{actionButton(book, 'return')}</div>
          </> : book.reserved ? <>
            <p><strong>Bạn đã đăng ký</strong></p>
            <div className="form-actions">{actionButton(book, 'checkout')}{actionButton(book, 'cancel')}</div>
          </> : actionButton(book, 'reserve', book.available === 0)}
        </article>)}</div>
      </>}
    {selected && <Modal title={actions[selected.action].title} onClose={() => { if (!busy) setSelected(null) }}>
      <p><strong>{selected.book.title}</strong></p>
      <p>Thao tác áp dụng cho tài khoản của bạn trong Thư viện mẫu.</p>
      <div className="form-actions"><button className="secondary" disabled={busy} onClick={() => setSelected(null)}>Quay lại</button>
        <button className="primary" disabled={busy} onClick={confirm}>{busy ? 'Đang xử lý…' : actions[selected.action].confirm}</button></div>
    </Modal>}
  </section>
}
