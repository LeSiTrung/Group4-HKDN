import { useState } from 'react'
import { displayDate, Empty, ErrorNotice, ExternalLink, Field, Icon, Modal, Notice } from './UI.jsx'

export default function BookAdmin({ rows, busy = false, error = '', onMutate }) {
  const [editing, setEditing] = useState(null)
  const [removing, setRemoving] = useState(null)
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState('')
  const [importResult, setImportResult] = useState(null)
  const [search, setSearch] = useState('')
  const books = (rows || []).filter(book => `${book.title} ${book.author} ${book.subjects}`.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi')))

  async function save(event) {
    event.preventDefault()
    const body = Object.fromEntries(new FormData(event.currentTarget))
    body.published = body.published === 'on'
    const result = await onMutate(`books${editing.id ? `/${editing.id}` : ''}`, { method: editing.id ? 'PUT' : 'POST', body, message: 'Đã lưu biểu ghi tài liệu cùng nguồn đối chiếu.' })
    if (result) setEditing(null)
  }
  async function importBooks(event) {
    event.preventDefault(); setImportError('')
    let items
    try {
      items = JSON.parse(new FormData(event.currentTarget).get('json'))
      if (!Array.isArray(items) || !items.length || items.some(item => !item || typeof item !== 'object' || Array.isArray(item))) throw new Error()
    } catch { setImportError('Dữ liệu phải là mảng JSON không rỗng gồm các biểu ghi tài liệu hợp lệ. Chưa gửi dữ liệu lên máy chủ.'); return }
    if (items.length > 200) { setImportError('Mỗi lần nhập tối đa 200 biểu ghi. Hãy chia dữ liệu thành các lô nhỏ hơn.'); return }
    const result = await onMutate('books/import', { body: { items }, message: 'Đã xử lý nhập danh mục. Các biểu ghi giữ nguyên trạng thái xuất bản đã khai báo.' })
    if (result) { setImportResult(result.imported); setImporting(false) }
  }
  return <>
    <Notice>Danh mục lưu bản ghi đã đối chiếu và nguồn gốc. Không nhập số lượng hay tình trạng lưu thông phỏng đoán. Bản ghi mới mặc định chưa xuất bản.</Notice>
    <div className="catalog-admin-toolbar"><div className="input-with-icon"><Icon name="search" /><input aria-label="Tìm trong danh mục quản trị" value={search} onChange={event => setSearch(event.target.value)} placeholder="Tìm nhan đề, tác giả, chủ đề…" /></div><div className="inline-actions"><button className="secondary" disabled={busy} onClick={() => { setImporting(true); setImportError('') }}><Icon name="download" size={16} />Nhập JSON</button><button className="primary" disabled={busy} onClick={() => setEditing({})}><Icon name="plus" size={16} />Thêm tài liệu</button></div></div>
    {importResult !== null && <p className="subtle" role="status">Đã nhập {importResult} biểu ghi.</p>}
    {rows && <div className="knowledge-list">{books.length ? books.map(book => <article className="panel knowledge-card" key={book.id}><div><div className="inline-actions"><span className="badge">{book.kind === 'digital' ? 'Tài liệu số' : 'Sách in'}</span><span className={`badge ${book.published ? '' : 'warning'}`}>{book.published ? 'Đã xuất bản' : 'Bản nháp'}</span></div><h3>{book.title}</h3><p>{book.author || 'Chưa có tác giả'}{book.year ? ` · ${book.year}` : ''}</p>{book.subjects && <p>Chủ đề: {book.subjects}</p>}<ExternalLink className="text-button" href={book.source_url || book.url}><Icon name="link" size={14} />Biểu ghi / nguồn gốc</ExternalLink><small className="block subtle">Đối chiếu: {displayDate(book.checked_at)}</small></div><div className="inline-actions"><button className="icon-button" aria-label={`Sửa tài liệu ${book.title}`} onClick={() => setEditing(book)} disabled={busy}><Icon name="edit" size={18} /></button><button className="icon-button destructive-text" aria-label={`Xóa tài liệu ${book.title}`} onClick={() => setRemoving(book)} disabled={busy}><Icon name="trash" size={18} /></button></div></article>) : <Empty title="Chưa có biểu ghi phù hợp">Thêm hoặc nhập tài liệu có nguồn đối chiếu để bạn đọc tra cứu.</Empty>}</div>}
    {editing && <Modal title={editing.id ? 'Sửa biểu ghi tài liệu' : 'Thêm tài liệu vào danh mục'} onClose={() => { if (!busy) setEditing(null) }}><form className="stack" onSubmit={save}>
      <Field label="Nhan đề"><input name="title" defaultValue={editing.title || ''} required maxLength={500} /></Field>
      <div className="form-grid"><Field label="Tác giả"><input name="author" defaultValue={editing.author || ''} maxLength={300} /></Field><Field label="Năm xuất bản" hint="Để trống nếu nguồn chưa xác định; nếu có, dùng bốn chữ số."><input name="year" defaultValue={editing.year || ''} maxLength={4} pattern="[0-9]{4}" inputMode="numeric" /></Field><Field label="Loại tài liệu"><select name="kind" defaultValue={editing.kind || 'books'}><option value="books">Sách in</option><option value="digital">Tài liệu số</option></select></Field><Field label="Chủ đề"><input name="subjects" defaultValue={editing.subjects || ''} maxLength={1000} /></Field></div>
      <Field label="Mô tả từ nguồn"><textarea name="description" rows={4} defaultValue={editing.description || ''} maxLength={8000} /></Field>
      <Field label="URL biểu ghi / nguồn"><input name="source_url" type="url" pattern="https://.*" defaultValue={editing.source_url || editing.url || ''} required maxLength={1000} /></Field>
      <Field label="Ngày đối chiếu"><input name="checked_at" type="date" defaultValue={editing.checked_at?.slice(0, 10) || ''} required /></Field>
      <label className="checkbox-field"><input name="published" type="checkbox" defaultChecked={Boolean(editing.published)} /><span>Xuất bản biểu ghi đã đối chiếu để bạn đọc tra cứu</span></label>
      <ErrorNotice>{error}</ErrorNotice><div className="form-actions"><button type="button" className="secondary" disabled={busy} onClick={() => setEditing(null)}>Hủy</button><button className="primary" disabled={busy}>{busy ? 'Đang lưu…' : 'Lưu tài liệu'}</button></div>
    </form></Modal>}
    {importing && <Modal title="Nhập danh mục từ JSON" onClose={() => { if (!busy) setImporting(false) }}><Notice>Mỗi mục cần nhan đề, URL nguồn HTTPS và ngày đối chiếu. Kiểm tra trường published trước khi nhập. Máy chủ kiểm tra toàn bộ lô trước khi lưu.</Notice><form className="stack" onSubmit={importBooks}><Field label="Dữ liệu JSON" hint="Mảng biểu ghi với các trường title, author, year, kind, subjects, description, source_url, checked_at, published."><textarea name="json" rows={12} maxLength={500000} spellCheck={false} required placeholder='[{"title":"…","source_url":"https://…","checked_at":"YYYY-MM-DD","published":false}]' /></Field><ErrorNotice>{importError || error}</ErrorNotice><div className="form-actions"><button type="button" className="secondary" disabled={busy} onClick={() => setImporting(false)}>Hủy</button><button className="primary" disabled={busy}>{busy ? 'Đang nhập…' : 'Nhập danh mục'}</button></div></form></Modal>}
    {removing && <Modal title="Xóa biểu ghi tài liệu?" onClose={() => { if (!busy) setRemoving(null) }}><p><strong>{removing.title}</strong></p><p>Biểu ghi sẽ ngừng xuất hiện trong danh mục và kết quả tra cứu.</p><ErrorNotice>{error}</ErrorNotice><div className="form-actions"><button className="secondary" disabled={busy} onClick={() => setRemoving(null)}>Giữ lại</button><button className="danger" disabled={busy} onClick={async () => { if (await onMutate(`books/${removing.id}`, { method: 'DELETE', message: 'Đã xóa biểu ghi tài liệu.' })) setRemoving(null) }}>{busy ? 'Đang xóa…' : 'Xóa biểu ghi'}</button></div></Modal>}
  </>
}
