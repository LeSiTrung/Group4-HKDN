import { useEffect, useState } from 'react'
import { api } from '../services/chatApi.js'
import { displayDate, ErrorNotice, ExternalLink, Icon, Modal, Notice } from './UI.jsx'

export default function BookDetails({ id, onClose }) {
  const [book, setBook] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let ignore = false
    setBook(null); setError('')
    api(`/catalog/${id}`).then(data => { if (!ignore) setBook(data) }).catch(err => { if (!ignore) setError(err.message) })
    return () => { ignore = true }
  }, [id])
  return <Modal title="Chi tiết tài liệu" onClose={onClose}>
    <ErrorNotice>{error}</ErrorNotice>
    {!book && !error && <div className="loading-state" role="status">Đang mở thông tin tài liệu…</div>}
    {book && <div className="book-details"><span className="badge">{book.kind === 'digital' ? 'Tài liệu số' : 'Sách và tài liệu khác'}</span><h2>{book.title}</h2><p className="subtle">{book.author || 'Chưa có tác giả'}{book.year ? ` · ${book.year}` : ''}</p>
      <Notice>Thông tin được đối chiếu ngày {displayDate(book.checked_at)}. Chưa xác nhận tình trạng còn sách hiện tại; vui lòng kiểm tra với thư viện trước khi mượn.</Notice>
      {book.subjects && <p className="subtle"><strong>Chủ đề: </strong>{book.subjects}</p>}
      {book.description && <p className="book-description">{book.description}</p>}
      <ExternalLink className="secondary" href={book.url || book.source_url}>Xem thông tin tại nguồn <Icon name="link" size={16} /></ExternalLink>
      {book.related?.length > 0 && <section className="related-books"><h3>Có thể bạn quan tâm</h3><p className="subtle">Những tài liệu có chủ đề hoặc nội dung mô tả liên quan.</p>{book.related.map((item, index) => <article className="related-book" key={item.id || index}><Icon name="book" size={19} /><div><ExternalLink href={item.url || item.source_url}><strong>{item.title}</strong></ExternalLink><small>{item.author || 'Chưa có tác giả'}{item.year ? ` · ${item.year}` : ''}</small><small>Đối chiếu: {displayDate(item.checked_at)}</small></div></article>)}</section>}
    </div>}
  </Modal>
}
