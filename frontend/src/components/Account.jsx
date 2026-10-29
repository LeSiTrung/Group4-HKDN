import { useState } from 'react'
import { api } from '../services/chatApi.js'
import { ErrorNotice, Field, Icon, Modal, Notice } from './UI.jsx'

export function AuthModal({ onClose, onSuccess }) {
  const [register, setRegister] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('')
    const form = event.currentTarget
    const data = Object.fromEntries(new FormData(form))
    try { const result = await api(`/auth/${register ? 'register' : 'login'}`, { method: 'POST', body: data }); form.reset(); onSuccess(result.user) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  return <Modal title={register ? 'Tạo tài khoản bạn đọc' : 'Chào mừng bạn trở lại'} onClose={onClose}><p className="subtle">Lưu cuộc trò chuyện và tiếp tục khám phá cùng trợ lý thư viện.</p><form className="stack" onSubmit={submit} key={register ? 'register' : 'login'}>
    {register && <Field label="Họ và tên"><input name="name" autoComplete="name" required maxLength={100} /></Field>}
    <Field label="Email"><input name="email" type="email" autoComplete="username" required maxLength={254} /></Field>
    <Field label="Mật khẩu" hint={register ? 'Ít nhất 12 ký tự. Không dùng mật khẩu của hệ thống thư viện.' : undefined}><input name="password" type="password" autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 12 : undefined} maxLength={128} required /></Field>
    <ErrorNotice>{error}</ErrorNotice><button className="primary full-width" disabled={busy}>{busy ? 'Đang xử lý…' : register ? 'Tạo tài khoản' : 'Đăng nhập'}<Icon name="arrow" size={18} /></button>
  </form><div className="auth-switch">{register ? 'Đã có tài khoản?' : 'Bạn chưa có tài khoản?'} <button className="text-button" disabled={busy} onClick={() => { setRegister(!register); setError('') }}>{register ? 'Đăng nhập' : 'Đăng ký'}</button></div><p className="fine-print">Phiên được bảo vệ bằng cookie. Ứng dụng không lưu mật khẩu trong bộ nhớ trình duyệt.</p></Modal>
}

export default function Account({ user, onLogout, onDeleted, health }) {
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState(false)
  async function changePassword(event) {
    event.preventDefault(); setBusy(true); setError(''); setNotice('')
    const form = event.currentTarget
    try { await api('/auth/password', { method: 'POST', body: Object.fromEntries(new FormData(form)) }); form.reset(); setNotice('Đã đổi mật khẩu. Vui lòng đăng nhập lại.'); await onLogout() }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  async function exportData() {
    setBusy(true); setError('')
    try {
      const data = await api('/export')
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8' }))
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `thu-vien-lich-su-${new Date().toISOString().slice(0, 10)}.json`; anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      setNotice('Đã xuất dữ liệu của bạn. Giữ tệp này ở nơi riêng tư.')
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  async function deleteAccount(event) {
    event.preventDefault(); setBusy(true); setError('')
    try { await api('/auth/me', { method: 'DELETE', body: { password: new FormData(event.currentTarget).get('password') } }); onDeleted() }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  const capabilities = health?.capabilities
  const services = [
    ['Tài khoản và lịch sử', capabilities?.accounts && capabilities?.history, 'Sẵn sàng'],
    ['Tìm kiếm ngữ nghĩa', capabilities?.vectors?.ready, capabilities?.vectors?.ready ? 'Sẵn sàng' : capabilities?.vectors?.configured ? 'Chưa nạp mô hình' : 'Chưa cấu hình'],
    ['Sinh câu trả lời bằng AI', Boolean(capabilities?.llm_provider && capabilities.llm_provider !== 'none'), 'Sẵn sàng'],
    ['Kết nối khoản mượn', capabilities?.library_configured, 'Sẵn sàng'],
    ['Kênh Messenger', capabilities?.messenger_configured, 'Sẵn sàng'],
    ['Kênh Zalo', capabilities?.zalo_configured, 'Sẵn sàng'],
  ]
  return <div className="content-page"><div className="page-heading"><span className="eyebrow">KHÔNG GIAN CÁ NHÂN</span><h1>Tài khoản của bạn</h1><p>Quản lý bảo mật và dữ liệu đã lưu trên hệ thống.</p></div>
    <ErrorNotice>{error}</ErrorNotice>{notice && <div className="notice success-notice" role="status"><Icon name="check" />{notice}</div>}
    <div className="account-grid"><section className="panel"><div className="profile-header"><div className="profile-avatar">{user.name.slice(0, 1).toUpperCase()}</div><div><h2>{user.name}</h2><p>{user.email}</p><span className="badge">{user.role === 'admin' ? 'Quản trị viên' : 'Bạn đọc'}</span></div></div><div className="divider" /><h3>Dữ liệu của bạn</h3><p className="subtle">Tải bản sao tài khoản và những cuộc trò chuyện chỉ thuộc về bạn.</p><button className="secondary" onClick={exportData} disabled={busy}><Icon name="download" size={18} />Xuất dữ liệu JSON</button><div className="divider" /><button className="secondary" onClick={onLogout} disabled={busy}>Đăng xuất</button></section>
      <section className="panel"><h2>Đổi mật khẩu</h2><p className="subtle">Bạn sẽ đăng nhập lại sau khi đổi mật khẩu.</p><form className="stack" onSubmit={changePassword}><Field label="Mật khẩu hiện tại"><input name="current_password" type="password" autoComplete="current-password" required maxLength={128} /></Field><Field label="Mật khẩu mới" hint="Ít nhất 12 ký tự."><input name="new_password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} /></Field><button className="primary" disabled={busy}>Cập nhật mật khẩu</button></form></section></div>
    <section className="panel danger-zone"><div><h2>Xóa tài khoản</h2><p>Xóa vĩnh viễn tài khoản và lịch sử của bạn. Hãy xuất dữ liệu cần giữ trước khi xóa.</p></div><button className="danger-outline" disabled={busy} onClick={() => setDeleting(true)}>Xóa tài khoản của tôi</button></section>
    <section className="panel"><h2>Trạng thái dịch vụ</h2><p className="subtle">Phiên bản {health?.version || 'chưa xác định'} · {health?.knowledge_count ?? '—'} mục tri thức</p><div className="capability-list">{services.map(([label, ready, detail]) => <div key={label}><strong>{label}</strong><span>{!health ? 'Chưa kiểm tra được' : ready ? detail : label === 'Tìm kiếm ngữ nghĩa' ? detail : 'Chưa cấu hình'}</span></div>)}</div></section>
    {deleting && <Modal title="Xóa vĩnh viễn tài khoản?" onClose={() => { if (!busy) setDeleting(false) }}><Notice>Thao tác này không thể hoàn tác. Toàn bộ lịch sử trò chuyện của bạn sẽ bị xóa.</Notice><form className="stack" onSubmit={deleteAccount}><Field label="Xác nhận bằng mật khẩu hiện tại"><input name="password" type="password" autoComplete="current-password" required maxLength={128} /></Field><ErrorNotice>{error}</ErrorNotice><div className="form-actions"><button type="button" className="secondary" disabled={busy} onClick={() => setDeleting(false)}>Giữ tài khoản</button><button className="danger" disabled={busy}>{busy ? 'Đang xóa…' : 'Xóa vĩnh viễn'}</button></div></form></Modal>}
  </div>
}
