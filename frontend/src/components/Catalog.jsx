import { useState } from 'react'
import { api } from '../services/chatApi.js'
import { displayDate, Empty, ErrorNotice, ExternalLink, Field, Icon, Notice } from './UI.jsx'
import BookDetails from './BookDetails.jsx'

export default function Catalog() {
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState('all')
  const [source, setSource] = useState('auto')
  const [submitted, setSubmitted] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [fallbackUrl, setFallbackUrl] = useState(null)
  const [detailId, setDetailId] = useState(null)

  async function search(params, page = 1) {
    if (busy) return
    setBusy(true); setError(''); setResult(null); setFallbackUrl(null)
    try { setResult(await api(`/catalog?${new URLSearchParams({ ...params, page, page_size: 20 })}`)) }
    catch (err) { setError(err.message); setFallbackUrl(err.search_url) }
    finally { setBusy(false) }
  }
  function submit(event) {
    event.preventDefault()
    if (!query.trim()) return
    const params = { q: query.trim(), kind, source }
    setSubmitted(params); search(params)
  }
  const local = result?.source === 'local'
  const total = result?.total ?? result?.items?.length ?? 0
  const page = result?.page || 1
  const pages = Math.max(1, Math.ceil(total / (result?.page_size || 20)))
  return <div className="content-page">
    <div className="page-heading"><span className="eyebrow">KHÁM PHÁ BỘ SƯU TẬP</span><h1>Tìm cuốn sách tiếp theo.</h1><p>Tra cứu tài liệu đã đối chiếu hoặc tìm trực tiếp từ mục lục thư viện, cùng nguồn gốc của từng biểu ghi.</p></div>
    <form className="panel catalog-search" onSubmit={submit}>
      <Field label="Từ khóa tìm kiếm"><div className="input-with-icon"><Icon name="search" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Tên sách, tác giả hoặc chủ đề…" required maxLength={200} /></div></Field>
      <Field label="Loại tài liệu"><select value={kind} onChange={event => setKind(event.target.value)}><option value="all">Tất cả tài liệu</option><option value="books">Sách in</option><option value="digital">Tài liệu số</option></select></Field>
      <Field label="Nguồn tra cứu"><select value={source} onChange={event => setSource(event.target.value)}><option value="auto">Tự động</option><option value="local">Danh mục đã đối chiếu</option><option value="opac">OPAC trực tuyến</option></select></Field>
      <button className="primary" disabled={busy || !query.trim()}><Icon name="search" size={18} />{busy ? 'Đang tìm…' : 'Tra cứu'}</button>
    </form>
    <ErrorNotice>{error}</ErrorNotice>
    {fallbackUrl && <ExternalLink className="secondary" href={fallbackUrl}>Tra cứu trực tiếp trên mục lục <Icon name="link" size={16} /></ExternalLink>}
    {local && !result.warning && <Notice>Đang xem danh mục đã đối chiếu. Đây là thông tin biểu ghi đã lưu, không phản ánh tình trạng mượn hiện tại hoặc số bản còn trên kệ.</Notice>}
    {result?.warning && <Notice>{result.warning}</Notice>}
    {busy && <div className="loading-state" role="status">Đang tra cứu tài liệu…</div>}
    {!result && !busy && !error && <Empty icon="search" title="Tri thức bắt đầu từ một câu hỏi">Nhập tên tài liệu, tác giả hoặc một chủ đề bạn đang quan tâm.</Empty>}
    {result && <>
      <div className="section-heading"><h2>{total} tài liệu{local ? ' · Danh mục đã đối chiếu' : ' · Mục lục trực tuyến'}</h2><ExternalLink className="text-button" href={result.search_url}>Mở mục lục gốc <Icon name="link" size={16} /></ExternalLink></div>
      <div className="results-list">{result.items?.length ? result.items.map((item, index) => <article className="panel catalog-card" key={item.id || `${item.url}-${index}`}>
        <div className={`book-cover cover-${index % 3}`} aria-hidden="true"><Icon name="book" size={31} /><span>UTH<br />LIBRARY</span></div>
        <div className="catalog-detail"><span className="eyebrow">{local ? 'BIỂU GHI ĐÃ ĐỐI CHIẾU' : 'BIỂU GHI THƯ VIỆN'}</span><h3><ExternalLink href={item.url || item.source_url}>{item.title}</ExternalLink></h3><p>{item.author || 'Chưa có tác giả'}{item.year ? ` · ${item.year}` : ''}</p>
          {item.description && <p className="catalog-description">{item.description}</p>}
          {!local && item.availability && <span className="badge">{item.availability}</span>}
          {item.checked_at && <small className="subtle block">Đối chiếu: {displayDate(item.checked_at)}</small>}
          {local && item.id && <button className="text-button" onClick={() => setDetailId(item.id)}>Xem chi tiết <Icon name="arrow" size={16} /></button>}
          <ExternalLink className="text-button record-link" href={item.url || item.source_url}>Xem biểu ghi gốc <Icon name="arrow" size={16} /></ExternalLink>
        </div>
      </article>) : <Empty icon="search" title="Chưa tìm thấy tài liệu phù hợp">Thử từ khóa ngắn hơn, đổi nguồn tra cứu hoặc tìm trực tiếp trên mục lục gốc.</Empty>}</div>
      {pages > 1 && <nav className="pagination" aria-label="Phân trang tài liệu"><button className="secondary" disabled={busy || page <= 1} onClick={() => search(submitted, page - 1)}>Trang trước</button><span>Trang {page} / {pages}</span><button className="secondary" disabled={busy || page >= pages} onClick={() => search(submitted, page + 1)}>Trang sau</button></nav>}
      <p className="subtle">Tình trạng lưu thông có thể thay đổi. Hãy kiểm tra biểu ghi gốc trước khi đến thư viện.</p>
    </>}
    {detailId !== null && <BookDetails id={detailId} onClose={() => setDetailId(null)} />}
  </div>
}
