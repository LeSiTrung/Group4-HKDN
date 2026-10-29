import { useEffect, useState } from 'react'
import { api } from '../services/chatApi.js'
import { displayDate, Empty, ErrorNotice, ExternalLink, Field, Icon, Modal, Notice, Status } from './UI.jsx'
import BookAdmin from './BookAdmin.jsx'
import RenewalAdmin from './RenewalAdmin.jsx'

const tabs = [{ id: 'knowledge', label: 'Kho tri thức' }, { id: 'books', label: 'Danh mục' }, { id: 'jobs', label: 'Thu thập dữ liệu' }, { id: 'schedules', label: 'Lịch phục vụ' }, { id: 'users', label: 'Bạn đọc' }, { id: 'renewals', label: 'Gia hạn' }, { id: 'status', label: 'Hệ thống' }]
const weekdays = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật']
const listValue = value => Array.isArray(value) ? value.join(', ') : value || ''
const splitList = value => String(value || '').split(/[,;\n]/).map(item => item.trim()).filter(Boolean)

export default function Admin({ user }) {
  const [tab, setTab] = useState('knowledge')
  const [rows, setRows] = useState(null)
  const [version, setVersion] = useState(0)
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState(null)
  const [removing, setRemoving] = useState(null)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [scheduleClosed, setScheduleClosed] = useState(false)
  function moveTab(event) {
    const index = tabs.findIndex(item => item.id === tab)
    const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null
    if (next === null) return
    event.preventDefault(); setTab(tabs[next].id); setNotice(''); document.getElementById(`tab-${tabs[next].id}`)?.focus()
  }
  useEffect(() => {
    let ignore = false
    setLoading(true); setRows(null); setError('')
    api(`/admin/${tab}`).then(data => { if (!ignore) setRows(data) }).catch(err => { if (!ignore) setError(err.message) }).finally(() => { if (!ignore) setLoading(false) })
    return () => { ignore = true }
  }, [tab, version])
  async function mutate(path, { body, method = 'POST', message = 'Đã cập nhật dữ liệu.' } = {}) {
    setBusy(true); setError(''); setNotice('')
    try { const data = await api(`/admin/${path}`, { method, body }); setNotice(message); setVersion(current => current + 1); return data ?? true }
    catch (err) { setError(err.message); return false }
    finally { setBusy(false) }
  }
  async function saveKnowledge(event) {
    event.preventDefault()
    const data = Object.fromEntries(new FormData(event.currentTarget))
    data.aliases = splitList(data.aliases); data.keywords = splitList(data.keywords); data.published = data.published === 'on'
    for (const key of ['valid_from', 'valid_until', 'verified_by']) if (!data[key]) data[key] = null
    const result = await mutate(`knowledge${editing.id ? `/${editing.id}` : ''}`, { method: editing.id ? 'PUT' : 'POST', body: data, message: 'Đã lưu mục tri thức. Chỉ mục đã xuất bản và còn hiệu lực mới được dùng để trả lời.' })
    if (result) setEditing(null)
  }
  async function crawl(event) {
    event.preventDefault()
    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form)); data.max_pages = Number(data.max_pages)
    const result = await mutate('crawl', { body: data, message: 'Đã tạo tác vụ thu thập. Nội dung nhập vào luôn là bản nháp chờ duyệt.' })
    if (result) form.reset()
  }
  async function schedule(event) {
    event.preventDefault()
    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form)); data.weekday = Number(data.weekday); data.closed = data.closed === 'on'
    const result = await mutate('schedules', { body: data, message: 'Đã lưu lịch phục vụ với thông tin người xác minh.' })
    if (result) { form.reset(); setScheduleClosed(false) }
  }
  const knowledge = Array.isArray(rows) ? rows.filter(row => (filter === 'all' || (filter === 'draft' ? !row.published : row.status === filter)) && `${row.title} ${row.question} ${row.category}`.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi'))) : []
  return <div className="content-page admin-page"><div className="page-heading"><span className="eyebrow">KHÔNG GIAN QUẢN TRỊ</span><h1>Thông tin đáng tin cậy,<br /><em>từ sự kiểm duyệt cẩn thận.</em></h1><p>Quản lý tri thức, nguồn dữ liệu và dịch vụ dành cho bạn đọc.</p></div>
    <div className="admin-tabs" role="tablist" aria-label="Chức năng quản trị" onKeyDown={moveTab}>{tabs.map(item => <button key={item.id} role="tab" id={`tab-${item.id}`} tabIndex={tab === item.id ? 0 : -1} aria-controls={`panel-${item.id}`} aria-selected={tab === item.id} onClick={() => { setTab(item.id); setNotice('') }}>{item.label}</button>)}</div>
    <ErrorNotice>{error}</ErrorNotice>{notice && <div className="notice success-notice" role="status"><Icon name="check" /><span>{notice}</span></div>}
    <section id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`}>
      <div className="section-heading"><h2>{tabs.find(item => item.id === tab).label}</h2><div className="inline-actions"><button className="secondary" onClick={() => setVersion(current => current + 1)} disabled={loading || busy}><Icon name="refresh" size={16} />Làm mới</button>{tab === 'knowledge' && <button className="primary" onClick={() => setEditing({})} disabled={busy}><Icon name="plus" size={16} />Thêm tri thức</button>}</div></div>
      {tab === 'books' && <BookAdmin rows={rows} busy={busy} error={error} onMutate={mutate} />}
      {tab === 'renewals' && <RenewalAdmin rows={rows} busy={busy} error={error} onMutate={mutate} />}
      {tab === 'knowledge' && <><Notice>Dữ liệu thu thập cần được đối chiếu trước khi xuất bản. Chính sách, phí và giờ phục vụ cần nguồn xác minh còn hiệu lực.</Notice><div className="filter-row"><label className="input-with-icon"><Icon name="search" /><input aria-label="Tìm trong kho tri thức" value={search} onChange={event => setSearch(event.target.value)} placeholder="Tìm tiêu đề, câu hỏi, danh mục…" /></label><select aria-label="Lọc trạng thái tri thức" value={filter} onChange={event => setFilter(event.target.value)}><option value="all">Tất cả trạng thái</option><option value="draft">Chưa xuất bản</option><option value="needs_confirmation">Cần xác nhận</option><option value="reviewed_public">Đã duyệt nguồn công khai</option><option value="verified">Đã xác minh</option></select></div>{!loading && <div className="knowledge-list">{knowledge.length ? knowledge.map(row => <article className="panel knowledge-card" key={row.id}><div><div className="inline-actions"><span className="eyebrow">{row.category || 'THÔNG TIN CHUNG'}</span><Status value={row.status} /><span className={`badge ${row.published ? '' : 'warning'}`}>{row.published ? 'Đã xuất bản' : 'Bản nháp'}</span></div><h3>{row.title}</h3><p>{row.question}</p><ExternalLink className="text-button" href={row.source_url}><Icon name="link" size={14} />{row.source_title || 'Nguồn tham khảo'}</ExternalLink><small className="block subtle">Đối chiếu: {displayDate(row.checked_at)}{row.valid_until ? ` · Hết hiệu lực: ${displayDate(row.valid_until)}` : ''}</small></div><div className="inline-actions"><button className="icon-button" aria-label={`Sửa ${row.title}`} onClick={() => setEditing(row)}><Icon name="edit" size={18} /></button><button className="icon-button destructive-text" aria-label={`Thu hồi ${row.title}`} onClick={() => setRemoving({ path: `knowledge/${row.id}`, title: row.title, kind: 'knowledge' })}><Icon name="trash" size={18} /></button></div></article>) : <Empty title="Không có mục phù hợp">Thêm mục tri thức hoặc thay đổi bộ lọc để tiếp tục.</Empty>}</div>}</>}
      {tab === 'jobs' && <><form className="panel stack" onSubmit={crawl}><h3>Thu thập từ nguồn cho phép</h3><p className="subtle">Tác vụ giới hạn số trang, tuân thủ robots và chỉ nhập nội dung thành bản nháp.</p><div className="form-grid"><Field label="URL nguồn"><input name="url" type="url" placeholder="https://…" required maxLength={1000} /></Field><Field label="Số trang tối đa"><input name="max_pages" type="number" defaultValue={3} min={1} max={5} required /></Field></div><button className="primary fit" disabled={busy}><Icon name="globe" size={18} />{busy ? 'Đang tạo…' : 'Tạo tác vụ thu thập'}</button></form><Notice>Lịch thu thập định kỳ do máy chủ cấu hình. Dùng “Làm mới” để kiểm tra tác vụ; xem và duyệt bản nháp ở Kho tri thức.</Notice>{Array.isArray(rows) && <div className="results-list">{rows.length ? rows.map(row => <article className="panel job-card" key={row.id || row.job_id}><div><h3>Tác vụ #{row.id || row.job_id}</h3><p className="break-all">{row.url || row.seed_url || row.kind || 'Thu thập dữ liệu'}</p><small>{displayDate(row.created_at)}{row.pages_count !== undefined ? ` · ${row.pages_count} trang` : ''}</small>{row.error && <p className="destructive-text">{row.error}</p>}</div><Status value={row.status} /></article>) : <Empty icon="globe" title="Chưa có tác vụ">Tạo tác vụ từ một nguồn thư viện đã được cho phép.</Empty>}</div>}</>}
      {tab === 'schedules' && <>
        <Notice>Mỗi lịch cần ngày hiệu lực, nguồn và người xác minh. Không nhập thời gian phỏng đoán. Thứ trong tuần tính theo múi giờ Việt Nam.</Notice>
        <form className="panel stack" onSubmit={schedule}><h3>Thêm lịch đã đối chiếu</h3><div className="form-grid">
          <Field label="Cơ sở / địa điểm"><select name="branch"><option value="1">Cơ sở 1</option><option value="2">Cơ sở 2</option><option value="3">Cơ sở 3</option></select></Field>
          <Field label="Ngày trong tuần"><select name="weekday">{weekdays.map((day, index) => <option key={day} value={index}>{day}</option>)}</select></Field>
          <Field label="Giờ mở cửa"><input type="time" name="opens" required={!scheduleClosed} disabled={scheduleClosed} /></Field>
          <Field label="Giờ đóng cửa"><input type="time" name="closes" required={!scheduleClosed} disabled={scheduleClosed} /></Field>
          <Field label="Hiệu lực từ"><input type="date" name="valid_from" required /></Field>
          <Field label="Hiệu lực đến"><input type="date" name="valid_until" required /></Field>
          <Field label="Người / đơn vị xác minh"><input name="verified_by" required maxLength={100} /></Field>
          <Field label="Ghi chú"><input name="note" required maxLength={1000} /></Field>
          <Field label="URL nguồn xác minh"><input name="source_url" type="url" pattern="https://.*" placeholder="https://…" required maxLength={1000} /></Field>
          <Field label="Tên nguồn"><input name="source_title" defaultValue="Lịch thư viện" required maxLength={200} /></Field>
          <Field label="Ngày đối chiếu nguồn"><input name="checked_at" type="date" required /></Field>
        </div><label className="checkbox-field"><input type="checkbox" name="closed" checked={scheduleClosed} onChange={event => setScheduleClosed(event.target.checked)} /><span>Nghỉ phục vụ cả ngày trong khoảng hiệu lực (lịch ngoại lệ)</span></label><button className="primary fit" disabled={busy}>Lưu lịch phục vụ</button></form>
        {Array.isArray(rows) && <div className="results-list">{rows.length ? rows.map(row => <article className="panel job-card" key={row.id}><div><h3>{row.branch} · {weekdays[row.weekday] || row.weekday}</h3><p>{row.closed ? <Status value="closed" /> : `${row.opens} – ${row.closes}`} · {displayDate(row.valid_from)} đến {displayDate(row.valid_until)}</p><small>{row.note} · Xác minh: {row.verified_by}</small><ExternalLink className="text-button" href={row.source_url}>{row.source_title || 'Nguồn lịch phục vụ'}<Icon name="link" size={14} /></ExternalLink></div><button className="icon-button destructive-text" aria-label={`Xóa lịch ${row.branch} ${weekdays[row.weekday]}`} onClick={() => setRemoving({ path: `schedules/${row.id}`, title: `${row.branch} · ${weekdays[row.weekday]}`, kind: 'schedule' })}><Icon name="trash" size={18} /></button></article>) : <Empty icon="clock" title="Chưa có lịch đã xác minh">Thêm lịch khi có nguồn đối chiếu và thời gian hiệu lực cụ thể.</Empty>}</div>}
      </>}
      {tab === 'users' && Array.isArray(rows) && <div className="panel table-wrap"><table><caption className="sr-only">Danh sách tài khoản bạn đọc</caption><thead><tr><th scope="col">Bạn đọc</th><th scope="col">Vai trò</th><th scope="col">Trạng thái</th><th scope="col">Thao tác</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><td><strong>{row.name}</strong><small className="block">{row.email}</small></td><td>{row.role === 'admin' ? 'Quản trị viên' : 'Bạn đọc'}</td><td><span className={`badge ${row.active ? 'success' : 'warning'}`}>{row.active ? 'Hoạt động' : 'Đã khóa'}</span></td><td><button className="secondary" disabled={busy || row.id === user.id} onClick={() => mutate(`users/${row.id}`, { method: 'PATCH', body: { active: !row.active }, message: row.active ? 'Đã khóa tài khoản và thu hồi phiên truy cập.' : 'Đã mở lại tài khoản.' })}>{row.id === user.id ? 'Tài khoản của bạn' : row.active ? 'Khóa tài khoản' : 'Mở khóa'}</button></td></tr>)}</tbody></table>{!rows.length && <Empty icon="user" title="Chưa có tài khoản">Danh sách bạn đọc sẽ xuất hiện tại đây.</Empty>}</div>}
      {tab === 'status' && rows && <><div className="panel"><h3>Chỉ mục tìm kiếm</h3><p className="subtle">Cập nhật chỉ mục sau khi kiểm duyệt nguồn. Mục chưa xuất bản hoặc hết hiệu lực không được dùng để trả lời.</p><button className="primary" disabled={busy} onClick={() => mutate('reindex', { message: 'Đã yêu cầu cập nhật chỉ mục. Xem trạng thái hệ thống để kiểm tra kết quả.' })}><Icon name="refresh" size={18} />{busy ? 'Đang cập nhật…' : 'Cập nhật chỉ mục'}</button></div><div className="panel"><h3>Trạng thái máy chủ</h3><p className="subtle">Khả năng và trạng thái được trả về trực tiếp từ máy chủ. Chưa cấu hình tích hợp thì dịch vụ chưa sẵn sàng.</p><pre className="status-json">{JSON.stringify(rows, null, 2)}</pre></div></>}
      {loading && <div className="loading-state" role="status">Đang tải dữ liệu quản trị…</div>}
    </section>
    {editing && <Modal title={editing.id ? 'Chỉnh sửa tri thức' : 'Thêm mục tri thức'} onClose={() => { if (!busy) setEditing(null) }}><form className="stack" onSubmit={saveKnowledge}><div className="form-grid"><Field label="Tiêu đề"><input name="title" defaultValue={editing.title || ''} required maxLength={200} /></Field><Field label="Danh mục"><input name="category" defaultValue={editing.category || 'general'} required maxLength={50} /></Field></div><Field label="Câu hỏi chính"><input name="question" defaultValue={editing.question || ''} required maxLength={500} /></Field><Field label="Câu hỏi tương đương" hint="Ngăn cách bằng dấu phẩy, chấm phẩy hoặc xuống dòng."><textarea name="aliases" rows={2} defaultValue={listValue(editing.aliases)} maxLength={4000} /></Field><Field label="Từ khóa"><input name="keywords" defaultValue={listValue(editing.keywords)} maxLength={2000} /></Field><Field label="Nội dung trả lời"><textarea name="answer" rows={6} defaultValue={editing.answer || ''} required maxLength={12000} /></Field><div className="form-grid"><Field label="Tên nguồn"><input name="source_title" defaultValue={editing.source_title || ''} required maxLength={200} /></Field><Field label="URL nguồn"><input name="source_url" type="url" defaultValue={editing.source_url || ''} required maxLength={1000} /></Field><Field label="Ngày đối chiếu"><input name="checked_at" type="date" defaultValue={editing.checked_at?.slice(0, 10) || ''} required /></Field><Field label="Trạng thái kiểm duyệt"><select name="status" defaultValue={editing.status || 'needs_confirmation'}><option value="needs_confirmation">Cần xác nhận</option><option value="reviewed_public">Đã duyệt nguồn công khai</option><option value="verified">Đã xác minh</option></select></Field><Field label="Hiệu lực từ (nếu có)"><input name="valid_from" type="date" defaultValue={editing.valid_from?.slice(0, 10) || ''} /></Field><Field label="Hiệu lực đến (nếu có)"><input name="valid_until" type="date" defaultValue={editing.valid_until?.slice(0, 10) || ''} /></Field></div><Field label="Người / đơn vị xác minh"><input name="verified_by" defaultValue={editing.verified_by || ''} maxLength={100} /></Field><label className="checkbox-field"><input name="published" type="checkbox" defaultChecked={Boolean(editing.published)} /><span>Xuất bản sau khi đã kiểm tra nội dung và nguồn</span></label><ErrorNotice>{error}</ErrorNotice><div className="form-actions"><button className="secondary" type="button" disabled={busy} onClick={() => setEditing(null)}>Hủy</button><button className="primary" disabled={busy}>{busy ? 'Đang lưu…' : 'Lưu mục tri thức'}</button></div></form></Modal>}
    {removing && <Modal title={removing.kind === 'knowledge' ? 'Thu hồi mục tri thức?' : 'Xóa lịch phục vụ?'} onClose={() => { if (!busy) setRemoving(null) }}><p><strong>{removing.title}</strong></p><p>{removing.kind === 'knowledge' ? 'Nội dung sẽ ngừng được dùng để trả lời. Thao tác này xóa hoặc thu hồi mục ở máy chủ.' : 'Lịch này sẽ bị xóa khỏi dữ liệu phục vụ.'}</p><ErrorNotice>{error}</ErrorNotice><div className="form-actions"><button className="secondary" disabled={busy} onClick={() => setRemoving(null)}>Hủy</button><button className="danger" disabled={busy} onClick={async () => { if (await mutate(removing.path, { method: 'DELETE', message: 'Đã thu hồi dữ liệu.' })) setRemoving(null) }}>{busy ? 'Đang xử lý…' : 'Xác nhận thu hồi'}</button></div></Modal>}
  </div>
}
