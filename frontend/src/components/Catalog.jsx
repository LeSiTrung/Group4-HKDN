import { useRef, useState } from 'react'
import { api } from '../services/chatApi.js'
import { displayDate, Empty, ErrorNotice, ExternalLink, Field, Icon, Notice } from './UI.jsx'
import BookDetails from './BookDetails.jsx'

const fieldLabels = { all: 'Tất cả nội dung', title: 'Tên tài liệu', author: 'Tác giả', smart: 'Câu hỏi tự nhiên' }
const semanticMessages = {
  preparing: 'Đang chuẩn bị tìm kiếm theo nội dung. Bạn có thể thử lại sau ít phút.',
  busy: 'Tìm kiếm theo nội dung đang bận. Bạn có thể thử lại sau.',
  unavailable: 'Tìm kiếm theo nội dung tạm thời chưa sẵn sàng. Bạn có thể đổi từ khóa hoặc mở mục lục gốc.',
}

export default function Catalog() {
  const [query, setQuery] = useState('')
  const [field, setField] = useState('all')
  const [kind, setKind] = useState('all')
  const [source, setSource] = useState('auto')
  const [submitted, setSubmitted] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [fallbackUrl, setFallbackUrl] = useState(null)
  const [detailId, setDetailId] = useState(null)
  const searching = useRef(false)

  async function search(params, page = 1) {
    if (searching.current) return
    searching.current = true
    setSubmitted(params)
    setBusy(true); setError(''); setResult(null); setFallbackUrl(null)
    try { setResult(await api(`/catalog?${new URLSearchParams({ ...params, page, page_size: 20 })}`)) }
    catch (err) { setError(err.message); setFallbackUrl(err.search_url) }
    finally { searching.current = false; setBusy(false) }
  }
  function submit(event) {
    event.preventDefault()
    if (!query.trim()) return
    const params = { q: query.trim(), kind, source, field }
    search(params)
  }
  function selectKeyword(text) {
    if (searching.current) return
    setQuery(text); setField('smart'); setSource('local'); setKind(submitted.kind)
    search({ ...submitted, q: text, source: 'local', field: 'smart' })
  }
  function retrySearch() {
    setQuery(submitted.q); setField(submitted.field); setKind(submitted.kind); setSource(submitted.source)
    search(submitted)
  }
  const local = result?.source === 'local'
  const semanticMessage = semanticMessages[result?.semantic_status]
  const interpretation = result?.interpretation
  const total = result?.total ?? result?.items?.length ?? 0
  const page = result?.page || 1
  const pages = Math.max(1, Math.ceil(total / (result?.page_size || 20)))
  return <div className="content-page">
    <div className="page-heading">
      <h1>Tra cứu tài liệu</h1>
      <p>Tìm theo nhan đề, tác giả, chủ đề hoặc mô tả tài liệu bạn cần.</p>
    </div>
    <form className="panel catalog-search" onSubmit={submit}>
      <Field label="Từ khóa tìm kiếm"><div className="input-with-icon"><Icon name="search" /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Tên sách, tác giả hoặc chủ đề…" required maxLength={200} /></div></Field>
      <Field label="Tìm theo"><select value={field} onChange={event => { setField(event.target.value); if (event.target.value !== 'all') setSource('local') }}>{Object.entries(fieldLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field label="Loại tài liệu"><select value={kind} onChange={event => setKind(event.target.value)}><option value="all">Tất cả tài liệu</option><option value="books">Sách và tài liệu khác</option><option value="digital">Tài liệu số</option></select></Field>
      <Field label="Nguồn tra cứu"><select value={source} onChange={event => setSource(event.target.value)} disabled={field === 'smart'}><option value="auto">Tự động</option><option value="local">Danh mục đã đối chiếu</option><option value="opac" disabled={field !== 'all'}>OPAC trực tuyến</option></select></Field>
      <button className="primary" disabled={busy || !query.trim()}><Icon name="search" size={18} />{busy ? 'Đang tìm…' : 'Tra cứu'}</button>
    </form>
    {field === 'smart' && <p className="subtle">Ví dụ “Tôi muốn học quản lý kho từ đầu” hoặc “Tìm theo tác giả Nguyễn Văn An”.</p>}
    <ErrorNotice>{error}</ErrorNotice>
    {fallbackUrl && <ExternalLink className="secondary" href={fallbackUrl}>Tra cứu trực tiếp trên mục lục <Icon name="link" size={16} /></ExternalLink>}
    {local && !result.warning && <Notice>Thông tin được lưu từ mục lục thư viện, không phản ánh tình trạng mượn hiện tại hoặc số bản còn trên kệ.</Notice>}
    {result?.warning && <Notice>{result.warning}</Notice>}
    {busy && <div className="loading-state" role="status">Đang tra cứu tài liệu…</div>}
    {result?.guidance && <Empty icon="chat" title="Bạn đang hỏi cách sử dụng thư viện">Trợ lý có thể hướng dẫn quy trình tra cứu và mượn sách. <a href="#chat">Hỏi Trợ lý thư viện</a></Empty>}
    {result && !result.guidance && <>
      {interpretation?.query && <Notice>{fieldLabels[interpretation.field]} · “{interpretation.query}”</Notice>}
      {result.learning_goal && total > 0 && <p className="subtle">Ưu tiên giáo trình, bài giảng và tài liệu tự học dựa trên nhan đề. Mở chi tiết để kiểm tra tài liệu có phù hợp với trình độ của bạn.</p>}
      {result.suggested_keywords?.length > 0 && <div className="inline-actions" role="group" aria-label="Từ khóa liên quan"><span className="subtle">Từ khóa liên quan</span>{result.suggested_keywords.map(term => <button type="button" className="secondary" key={term} onClick={() => selectKeyword(term)}>{term}</button>)}</div>}
      <div className="section-heading"><h2>{semanticMessage && !total ? 'Danh mục đã đối chiếu' : `${total} tài liệu · ${local ? 'Danh mục đã đối chiếu' : 'Mục lục trực tuyến'}`}</h2><ExternalLink className="text-button" href={result.search_url}>Mở mục lục gốc <Icon name="link" size={16} /></ExternalLink></div>
      {semanticMessage && <div role="status"><Notice>{semanticMessage} Danh mục chưa có kết quả khớp từ khóa.</Notice><button type="button" className="secondary" onClick={retrySearch}>Thử lại lượt tra cứu</button></div>}
      <div className="results-list">{result.items?.length ? result.items.map((item, index) => <article className="panel catalog-card" key={item.id || `${item.url}-${index}`}>
        <div className="book-cover" aria-hidden="true"><Icon name="book" size={25} /></div>
        <div className="catalog-detail"><h3><ExternalLink href={item.url || item.source_url}>{item.title}</ExternalLink></h3><p>{item.author || 'Chưa có tác giả'}{item.year ? ` · ${item.year}` : ''}</p>
          {item.description && <p className="catalog-description">{item.description}</p>}
          {item.marc_match && <small className="subtle block">{item.marc_match === 'subjects' ? 'Khớp chủ đề OPAC' : 'Khớp mô tả nội dung OPAC'} · {displayDate(item.marc?.checked_at)}</small>}
          {item.checked_at && <small className="subtle block">Đối chiếu: {displayDate(item.checked_at)}</small>}
          <div className="inline-actions catalog-actions">
            {local && item.id && <button className="text-button" onClick={() => setDetailId(item.id)}>Xem chi tiết <Icon name="arrow" size={16} /></button>}
            <ExternalLink className="text-button" href={item.url || item.source_url}>Xem thông tin gốc <Icon name="link" size={16} /></ExternalLink>
          </div>
        </div>
      </article>) : !semanticMessage && <Empty icon="search" title="Chưa tìm thấy tài liệu phù hợp">Thử từ khóa ngắn hơn, đổi nguồn tra cứu hoặc tìm trực tiếp trên mục lục gốc.</Empty>}</div>
      {pages > 1 && <nav className="pagination" aria-label="Phân trang tài liệu"><button className="secondary" disabled={busy || page <= 1} onClick={() => search(submitted, page - 1)}>Trang trước</button><span>Trang {page} / {pages}</span><button className="secondary" disabled={busy || page >= pages} onClick={() => search(submitted, page + 1)}>Trang sau</button></nav>}
      <p className="subtle">Tình trạng còn sách có thể thay đổi. Hãy kiểm tra trên mục lục hoặc liên hệ thư viện trước khi đến.</p>
    </>}
    {detailId !== null && <BookDetails id={detailId} onClose={() => setDetailId(null)} />}
  </div>
}
