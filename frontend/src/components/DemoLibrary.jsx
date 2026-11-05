import { useEffect, useRef, useState } from 'react'
import { api } from '../services/chatApi.js'
import { ErrorNotice, Modal, Notice } from './UI.jsx'

const path = '/demo/reservations'

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
    const cancel = selected.reserved
    try {
      const data = await api(`${path}/${selected.id}`, { method: cancel ? 'DELETE' : 'PUT' })
      if (cancel) setRefresh(value => value + 1)
      else setBooks(data.books)
      setSelected(null)
      setNotice(cancel ? 'Đã hủy đăng ký giả lập.' : 'Đã lưu đăng ký giả lập.')
    } catch (err) {
      setSelected(null)
      setError(err.message)
      setRefresh(value => value + 1)
    } finally {
      pending.current = false
      setBusy(false)
    }
  }

  return <section className="content-page">
    <h1>Thư viện mẫu</h1>
    <Notice>Đây là kho sách giả lập để thử đăng ký mượn. Số bản và yêu cầu thuộc riêng kho mẫu.</Notice>
    {enabled === undefined ? <p>Đang kiểm tra tính năng…</p> : !enabled ? <p>Thư viện mẫu hiện chưa được bật.</p>
      : sessionLoading ? <p>Đang kiểm tra phiên…</p> : !user ? <button className="primary" onClick={onLogin}>Đăng nhập để đăng ký mượn</button> : <>
        <ErrorNotice>{error}</ErrorNotice>
        {error && <button className="secondary" onClick={() => { setError(''); setRefresh(value => value + 1) }}>Tải lại danh mục mẫu</button>}
        {notice && <p role="status">{notice}</p>}
        {!books && !error && <p>Đang tải danh mục mẫu…</p>}
        <div className="chat-books">{books?.map(book => <article className="chat-book-card" key={book.id}>
          <h3>{book.title}</h3>
          <p>{book.available > 0 ? `Còn ${book.available} bản mẫu` : 'Hết bản mẫu'}</p>
          {book.reserved && <p><strong>Bạn đã đăng ký</strong></p>}
          <button className={book.reserved ? 'secondary' : 'primary'} disabled={busy || (!book.reserved && book.available === 0)}
            aria-label={`${book.reserved ? 'Hủy đăng ký' : 'Đăng ký mượn'} ${book.title}`}
            onClick={() => setSelected(book)}>{book.reserved ? 'Hủy đăng ký' : 'Đăng ký mượn'}</button>
        </article>)}</div>
      </>}
    {selected && <Modal title={selected.reserved ? 'Xác nhận hủy giả lập' : 'Xác nhận đăng ký giả lập'} onClose={() => { if (!busy) setSelected(null) }}>
      <p><strong>{selected.title}</strong></p>
      <p>Thao tác áp dụng cho tài khoản của bạn trong Thư viện mẫu.</p>
      <div className="form-actions"><button className="secondary" disabled={busy} onClick={() => setSelected(null)}>Quay lại</button>
        <button className="primary" disabled={busy} onClick={confirm}>{busy ? 'Đang xử lý…' : selected.reserved ? 'Xác nhận hủy' : 'Xác nhận đăng ký'}</button></div>
    </Modal>}
  </section>
}
