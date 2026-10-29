import { useState } from 'react'
import { Empty, ErrorNotice, Field, Modal, Notice, Status } from './UI.jsx'

export default function RenewalAdmin({ rows, busy = false, error = '', onMutate }) {
  const [selected, setSelected] = useState(null)
  const [state, setState] = useState('')
  async function reconcile(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const body = { state, confirmation: form.get('confirmation') === 'on', reference: form.get('reference') }
    if (state === 'succeeded') body.due_date = form.get('due_date')
    const result = await onMutate(`renewals/${encodeURIComponent(selected.idempotency_key)}/reconcile`, { body, message: 'Đã ghi nhận kết quả đối soát và tham chiếu kiểm tra.' })
    if (result) setSelected(null)
  }
  return <>
    <Notice>Chỉ đối soát sau khi kiểm tra kết quả thực tế với hệ thống hoặc đầu mối thư viện. Ghi nhận tại đây không gửi lại giao dịch gia hạn. Yêu cầu chưa rõ kết quả cần được xử lý trước khi bạn đọc xóa tài khoản.</Notice>
    {rows && (rows.length ? <div className="panel table-wrap"><table><caption className="sr-only">Yêu cầu gia hạn và trạng thái đối soát</caption><thead><tr><th scope="col">Yêu cầu</th><th scope="col">Bạn đọc / khoản mượn</th><th scope="col">Kết quả</th><th scope="col">Thao tác</th></tr></thead><tbody>{rows.map(row => <tr key={row.idempotency_key}><td><code className="renewal-key">{row.idempotency_key}</code></td><td><strong>Bạn đọc #{row.user_id}</strong><small className="block">Khoản mượn: {row.loan_id}</small></td><td><Status value={row.state} />{row.result?.due_date && <small className="block">Hạn trả: {row.result.due_date}</small>}</td><td>{['pending', 'uncertain'].includes(row.state) ? <button className="secondary" disabled={busy} onClick={() => { setSelected(row); setState('') }}>Đối soát</button> : <small className="subtle">Đã kết thúc</small>}</td></tr>)}</tbody></table></div> : <Empty icon="check" title="Chưa có yêu cầu gia hạn">Các giao dịch được thư viện ghi nhận sẽ xuất hiện tại đây để theo dõi kết quả.</Empty>)}
    {selected && <Modal title="Ghi nhận đối soát gia hạn" onClose={() => { if (!busy) setSelected(null) }}><p>Khoản mượn <strong>{selected.loan_id}</strong> của bạn đọc #{selected.user_id}.</p><Notice>Không chọn thành công nếu chưa có xác nhận thực tế và hạn trả mới từ thư viện. Không dùng câu trả lời chatbot làm bằng chứng đối soát.</Notice><form className="stack" onSubmit={reconcile}>
      <Field label="Kết quả đã xác nhận"><select value={state} onChange={event => setState(event.target.value)} required><option value="" disabled>Chọn sau khi đối soát</option><option value="succeeded">Thư viện xác nhận gia hạn thành công</option><option value="failed">Thư viện xác nhận không gia hạn</option></select></Field>
      <Field label="Hạn trả được thư viện xác nhận"><input name="due_date" type="date" required={state === 'succeeded'} disabled={state !== 'succeeded'} /></Field>
      <Field label="Tham chiếu đối soát" hint="Ghi mã phản hồi hoặc đầu mối, thời gian kiểm tra; không nhập mật khẩu hay mã truy cập."><textarea name="reference" rows={3} required maxLength={500} /></Field>
      <label className="checkbox-field"><input name="confirmation" type="checkbox" required /><span>Tôi đã kiểm tra kết quả thực tế với thư viện và chịu trách nhiệm về thông tin đối soát.</span></label>
      <ErrorNotice>{error}</ErrorNotice><div className="form-actions"><button type="button" className="secondary" disabled={busy} onClick={() => setSelected(null)}>Hủy</button><button className="primary" disabled={busy || !state}>{busy ? 'Đang ghi nhận…' : 'Ghi nhận kết quả đối soát'}</button></div>
    </form></Modal>}
  </>
}
