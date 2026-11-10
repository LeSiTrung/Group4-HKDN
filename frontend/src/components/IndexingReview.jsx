import { useEffect, useRef, useState } from 'react'
import { api } from '../services/chatApi.js'
import { displayDate, Empty, ErrorNotice, ExternalLink, Modal, Notice } from './UI.jsx'

const labels = { subjects: 'Từ khóa', summary: 'Tóm tắt từ nguồn' }

export default function IndexingReview({ book, busy, error, onMutate, onClose }) {
  const [preview, setPreview] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [version, setVersion] = useState(0)
  const [fields, setFields] = useState([])
  const pending = useRef(false)
  useEffect(() => {
    let ignore = false
    setPreview(null); setLoadError(''); setFields([])
    api(`/admin/books/${book.id}/indexing`).then(data => { if (!ignore) setPreview(data) })
      .catch(err => { if (!ignore) setLoadError(err.message) })
    return () => { ignore = true }
  }, [book.id, version])
  async function approve(event) {
    event.preventDefault()
    if (pending.current || busy || !preview || !fields.length) return
    pending.current = true
    try {
      const saved = await onMutate(`books/${book.id}/indexing`, {
        body: { revision: preview.revision, fields }, message: 'Đã duyệt và ghép thông tin từ nguồn vào biểu ghi.',
      })
      if (saved) onClose()
    } finally { pending.current = false }
  }
  return <Modal title="Duyệt gợi ý biên mục" onClose={() => { if (!busy) onClose() }}>
    <h3>{book.title}</h3>
    <Notice>Gợi ý lấy từ thông tin đã có trong nguồn. Chọn từng mục sau khi đối chiếu. Nội dung được ghép vào biểu ghi khi bạn duyệt, giữ nguyên trạng thái xuất bản.</Notice>
    <ErrorNotice>{loadError || error}</ErrorNotice>
    {!preview && !loadError && <p role="status">Đang đọc thông tin nguồn…</p>}
    {preview && <form className="stack" onSubmit={approve}>
      <ExternalLink href={preview.source_url}>Đối chiếu nguồn</ExternalLink>
      {preview.classification && <p>Mã phân loại DDC trong nguồn · {preview.classification} · Đối chiếu {displayDate(preview.checked_at)}</p>}
      {preview.suggestions.length ? preview.suggestions.map(suggestion => <div className="panel stack" key={suggestion.field}>
        <label className="checkbox-field"><input type="checkbox" disabled={busy} checked={fields.includes(suggestion.field)} onChange={event => setFields(current => event.target.checked ? [...current, suggestion.field] : current.filter(field => field !== suggestion.field))} /><strong>{labels[suggestion.field]}</strong></label>
        <p>{suggestion.value}</p><small>{suggestion.source_field} · Đối chiếu {displayDate(suggestion.checked_at)}</small>
      </div>) : <Empty title="Chưa có gợi ý mới từ nguồn">Kiểm tra hoặc bổ sung thông tin nguồn trước khi biên mục.</Empty>}
      <button className="primary" disabled={busy || !fields.length}>{busy ? 'Đang lưu…' : 'Duyệt và ghép vào biểu ghi'}</button>
    </form>}
    <div className="form-actions"><button className="secondary" disabled={busy || (!preview && !loadError)} onClick={() => setVersion(current => current + 1)}>Đọc lại nguồn</button><button className="secondary" disabled={busy} onClick={onClose}>Đóng</button></div>
  </Modal>
}
