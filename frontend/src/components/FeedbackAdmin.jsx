import { Empty, ExternalLink, Notice, Status } from './UI.jsx'

export default function FeedbackAdmin({ rows, loading, query, onQuery }) {
  const pages = rows ? Math.max(1, Math.ceil(rows.total / rows.page_size)) : 1
  return <>
    <Notice>Chỉ hiển thị câu trả lời được đánh giá, câu hỏi liền trước, nhận xét và nguồn kèm theo. Không kèm thông tin tài khoản hoặc toàn bộ hội thoại.</Notice>
    <div className="filter-row"><label>Lọc đánh giá <select aria-label="Lọc đánh giá" value={query.rating} disabled={loading} onChange={event => onQuery({ rating: event.target.value, page: 1 })}><option value="">Tất cả đánh giá</option><option value="1">Hữu ích</option><option value="-1">Chưa hữu ích</option></select></label></div>
    {!loading && rows && <>
      <p className="subtle">Tổng đánh giá: Hữu ích: {rows.summary.positive} · Chưa hữu ích: {rows.summary.negative}. Kết quả theo bộ lọc: {rows.total}.</p>
      <div className="results-list">{rows.items.length ? rows.items.map(item => <article className="panel stack" key={item.message_id}>
        <div className="inline-actions"><strong>{item.rating === 1 ? 'Hữu ích' : 'Chưa hữu ích'}</strong><Status value={item.status} /><Status value={item.mode} /></div>
        <div><h3>Câu hỏi</h3><p className="message-content">{item.question || 'Không có câu hỏi liền trước.'}</p></div>
        <div><h3>Câu trả lời</h3><p className="message-content">{item.answer}</p></div>
        {item.comment && <div><h3>Nhận xét</h3><p className="message-content">{item.comment}</p></div>}
        {item.sources.length > 0 && <div className="sources"><span className="eyebrow">NGUỒN KÈM CÂU TRẢ LỜI</span>{item.sources.map((source, index) => <ExternalLink className="source-link" key={index} href={source.url}>{source.title || 'Nguồn thư viện'}</ExternalLink>)}</div>}
      </article>) : <Empty title="Chưa có phản hồi phù hợp">Đánh giá do bạn đọc chủ động gửi sẽ xuất hiện tại đây.</Empty>}</div>
    </>}
    <div className="inline-actions"><button className="secondary" disabled={loading || query.page <= 1} onClick={() => onQuery({ ...query, page: query.page - 1 })}>Trang trước</button><span>Trang {query.page}{rows ? ` / ${pages}` : ''}</span><button className="secondary" disabled={loading || !rows || query.page >= pages} onClick={() => onQuery({ ...query, page: query.page + 1 })}>Trang sau</button></div>
  </>
}
