import { useState } from 'react'
import { api } from '../services/chatApi.js'
import { Empty, ErrorNotice, Field, Icon, Modal, Notice, Status } from './UI.jsx'

export default function Loans({ user, onLogin }) {
  const [token, setToken] = useState('')
  const [loans, setLoans] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [confirm, setConfirm] = useState(null)
  const [outcome, setOutcome] = useState(null)
  const [blocked, setBlocked] = useState([])
  async function load(event) {
    event.preventDefault(); setBusy(true); setError(''); setOutcome(null)
    try { const data = await api('/library/loans', { method: 'POST', body: { access_token: token } }); setLoans(data.loans || data.items || []); if (data.warning) setError(data.warning) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  async function renew() {
    if (busy || !confirm) return
    const selected = confirm
    setBusy(true); setError('')
    // An uncertain renewal must be reconciled; a new key must never blindly retry it.
    setBlocked(current => [...current, selected.id])
    try {
      const data = await api('/library/renew', { method: 'POST', body: { access_token: token, loan_id: String(selected.id), confirmation: true, idempotency_key: selected.key } })
      setOutcome(data)
    } catch (err) { setError(`${err.message} Không gửi lại gia hạn khoản mượn này; hãy kiểm tra với thư viện để đối soát.`) }
    finally { setConfirm(null); setBusy(false) }
  }
  return <div className="content-page"><div className="page-heading"><span className="eyebrow">DỊCH VỤ BẠN ĐỌC</span><h1>Sách đang mượn</h1><p>Theo dõi khoản mượn và gửi yêu cầu gia hạn có xác nhận.</p></div>
    {!user ? <div className="panel"><Empty icon="user" title="Đăng nhập để tiếp tục">Tài khoản chatbot giúp bảo vệ thông tin khoản mượn của bạn.</Empty><button className="primary center-button" onClick={onLogin}>Đăng nhập</button></div> : <>
      <Notice>Kết nối chỉ hoạt động khi thư viện đã cấu hình dịch vụ tích hợp. Mã truy cập chỉ ở trong bộ nhớ của trang này và được xóa khi bạn rời trang. Không nhập mật khẩu thư viện.</Notice>
      <form className="panel loan-connect" onSubmit={load}><Field label="Mã truy cập thư viện" hint="Dùng mã truy cập được hệ thống thư viện cấp."><input type="password" value={token} onChange={event => { setToken(event.target.value); setLoans(null) }} autoComplete="off" required maxLength={4096} /></Field><button className="primary" disabled={busy || !token.trim()}><Icon name="link" size={18} />{busy ? 'Đang xử lý…' : 'Xem sách đang mượn'}</button></form>
      <ErrorNotice>{error}</ErrorNotice>
      {outcome && <div className="panel outcome"><Status value={outcome.status || 'pending'} /><h3>Kết quả từ dịch vụ thư viện</h3><p>{outcome.message || 'Yêu cầu đã nhận được phản hồi. Kiểm tra trạng thái trước khi thực hiện thao tác khác.'}</p>{(outcome.due_date || outcome.due_at) && <p>Hạn trả do thư viện phản hồi: {outcome.due_date || outcome.due_at}</p>}<small>Chỉ phản hồi xác nhận thực tế từ thư viện mới chứng minh gia hạn thành công.</small></div>}
      {loans !== null && <div className="results-list">{loans.length === 0 ? <Empty title="Chưa có khoản mượn">Dịch vụ thư viện không trả về khoản mượn nào cho mã truy cập này.</Empty> : loans.map((loan, index) => {
        const id = loan.loan_id ?? loan.id
        return <article className="panel loan-card" key={id ?? index}><div className="book-spine"><Icon name="book" size={25} /></div><div><h3>{loan.title || loan.book_title || 'Tài liệu đang mượn'}</h3><p>Hạn trả: {loan.due_date || loan.due_at || 'Chưa có dữ liệu'}{loan.author ? ` · ${loan.author}` : ''}</p><small>Mã khoản mượn: {id ?? 'Chưa được cung cấp'}</small></div><button className="secondary" disabled={busy || !id || blocked.includes(id)} onClick={() => setConfirm({ id, title: loan.title || loan.book_title || 'Tài liệu', key: crypto.randomUUID() })}>{blocked.includes(id) ? 'Đã gửi · cần đối soát' : 'Gia hạn'}</button></article>
      })}</div>}
      {confirm && <Modal title="Xác nhận gia hạn" onClose={() => { if (!busy) setConfirm(null) }}><p>Bạn đang yêu cầu gia hạn <strong>{confirm.title}</strong> (mã {confirm.id}). Thư viện quyết định điều kiện và hạn trả mới.</p><Notice>Khi phản hồi chưa rõ hoặc hết thời gian chờ, ứng dụng sẽ giữ thao tác để đối soát và không tự gửi lại.</Notice><div className="form-actions"><button className="secondary" disabled={busy} onClick={() => setConfirm(null)}>Hủy</button><button className="primary" disabled={busy} onClick={renew}>{busy ? 'Đang gửi…' : 'Xác nhận gia hạn'}</button></div></Modal>}
    </>}
  </div>
}
