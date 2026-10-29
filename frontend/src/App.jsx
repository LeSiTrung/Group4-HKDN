import { useEffect, useRef, useState } from 'react'
import { api } from './services/chatApi.js'
import Account, { AuthModal } from './components/Account.jsx'
import Admin from './components/Admin.jsx'
import Catalog from './components/Catalog.jsx'
import ChatWindow from './components/ChatWindow.jsx'
import Loans from './components/Loans.jsx'
import { Empty, ErrorNotice, Icon, Modal } from './components/UI.jsx'

const navigation = [{ id: 'chat', title: 'Trợ lý thư viện', icon: 'chat' }, { id: 'catalog', title: 'Tra cứu tài liệu', icon: 'search' }, { id: 'loans', title: 'Sách đang mượn', icon: 'book' }]
const route = () => ['chat', 'catalog', 'loans', 'account', 'admin'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'chat'

export default function App() {
  const [view, setView] = useState(route)
  const [user, setUser] = useState(null)
  const [sessionLoading, setSessionLoading] = useState(true)
  const [health, setHealth] = useState(null)
  const [connected, setConnected] = useState(false)
  const [auth, setAuth] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [error, setError] = useState('')
  const [history, setHistory] = useState([])
  const [historyError, setHistoryError] = useState('')
  const [historyVersion, setHistoryVersion] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(false)
  const [activeId, setActiveId] = useState(null)
  const [openedId, setOpenedId] = useState(null)
  const [chatKey, setChatKey] = useState(0)
  const [deleting, setDeleting] = useState(null)
  const [busy, setBusy] = useState(false)
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 700px)').matches)
  const sidebar = useRef(null)
  const menuButton = useRef(null)

  useEffect(() => {
    const media = window.matchMedia('(max-width: 700px)')
    const changed = () => { setIsMobile(media.matches); setDrawer(false) }
    media.addEventListener('change', changed)
    return () => media.removeEventListener('change', changed)
  }, [])

  useEffect(() => {
    let ignore = false
    api('/auth/me').then(data => { if (!ignore) setUser(data.user) }).catch(err => { if (!ignore && err.status !== 401) setError(err.message) }).finally(() => { if (!ignore) setSessionLoading(false) })
    api('/health').then(data => { if (!ignore) { setHealth(data); setConnected(true) } }).catch(() => { if (!ignore) setConnected(false) })
    const hashChanged = () => { setView(route()); setDrawer(false) }
    window.addEventListener('hashchange', hashChanged)
    return () => { ignore = true; window.removeEventListener('hashchange', hashChanged) }
  }, [])
  useEffect(() => {
    if (!user) { setHistory([]); setHistoryError(''); return }
    let ignore = false
    setHistoryLoading(true)
    api('/conversations').then(data => { if (!ignore) { setHistory(data); setHistoryError('') } }).catch(err => { if (!ignore) setHistoryError(err.message) }).finally(() => { if (!ignore) setHistoryLoading(false) })
    return () => { ignore = true }
  }, [user, historyVersion])
  useEffect(() => {
    if (!drawer) return
    sidebar.current.querySelector('button')?.focus()
    const escape = event => {
      if (event.key === 'Escape') { setDrawer(false); menuButton.current?.focus() }
      if (event.key === 'Tab') {
        const controls = [...sidebar.current.querySelectorAll('a, button:not(:disabled)')]
        const first = controls[0], last = controls.at(-1)
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }
    window.addEventListener('keydown', escape)
    return () => window.removeEventListener('keydown', escape)
  }, [drawer])

  function navigate(next) { location.hash = next; setView(next); setDrawer(false) }
  function openChat(id = null) { setOpenedId(id); setActiveId(id); setChatKey(current => current + 1); navigate('chat') }
  function resetSession(nextUser = null) { setUser(nextUser); setOpenedId(null); setActiveId(null); setChatKey(current => current + 1); setAuth(false); setError(''); setHistory([]) }
  async function logout() {
    setError('')
    try { await api('/auth/logout', { method: 'POST' }); resetSession(); navigate('chat') }
    catch (err) { setError(err.message); throw err }
  }
  async function deleteConversation() {
    setBusy(true); setError('')
    try { await api(`/conversations/${deleting.id}`, { method: 'DELETE' }); if (activeId === deleting.id) openChat(); setHistoryVersion(current => current + 1); setDeleting(null) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  const title = navigation.find(item => item.id === view)?.title || (view === 'admin' ? 'Quản trị thư viện' : 'Tài khoản')
  return <div className="app-shell">
    <a href="#main-content" className="skip-link" onClick={event => { event.preventDefault(); document.getElementById('main-content').focus() }}>Chuyển đến nội dung</a>
    {drawer && <button className="sidebar-backdrop" aria-label="Đóng điều hướng" onClick={() => setDrawer(false)} />}
    <aside ref={sidebar} id="app-navigation" className={`sidebar ${drawer ? 'is-open' : ''}`} inert={isMobile && !drawer} role={isMobile && drawer ? 'dialog' : undefined} aria-modal={isMobile && drawer ? 'true' : undefined} aria-label="Điều hướng thư viện">
      <button className="icon-button sidebar-close" aria-label="Đóng điều hướng" onClick={() => { setDrawer(false); menuButton.current?.focus() }}><Icon name="close" /></button>
      <a className="brand" href="#chat" onClick={() => setDrawer(false)} aria-label="UTH Library, trang chủ"><span className="brand-symbol"><Icon name="book" size={26} /></span><span>UTH<span className="brand-light"> Library</span><small>THƯ VIỆN ĐẠI HỌC UTH</small></span></a>
      <button className="new-chat" onClick={() => openChat()}><Icon name="plus" size={18} />Cuộc trò chuyện mới</button>
      <span className="nav-label">KHÁM PHÁ</span>
      <nav aria-label="Điều hướng chính">{navigation.map(item => <a key={item.id} href={`#${item.id}`} onClick={() => navigate(item.id)} className={`nav-link ${view === item.id ? 'active' : ''}`} aria-current={view === item.id ? 'page' : undefined}><Icon name={item.icon} /><span>{item.title}</span>{view === item.id && <span className="nav-active-dot" />}</a>)}{user?.role === 'admin' && <a href="#admin" onClick={() => navigate('admin')} className={`nav-link ${view === 'admin' ? 'active' : ''}`} aria-current={view === 'admin' ? 'page' : undefined}><Icon name="shield" /><span>Quản trị thư viện</span></a>}</nav>
      <div className="history-heading"><span className="nav-label">TRÒ CHUYỆN GẦN ĐÂY</span>{user && <button className="sidebar-icon" aria-label="Làm mới lịch sử" onClick={() => setHistoryVersion(current => current + 1)} disabled={historyLoading}><Icon name="refresh" size={14} /></button>}</div>
      <div className="history-list">{sessionLoading ? <p className="sidebar-note">Đang kiểm tra phiên…</p> : !user ? <div className="history-guest"><Icon name="clock" size={24} /><p>Giữ lại những điều<br />bạn đang khám phá.</p><button className="sidebar-text-button" onClick={() => { setDrawer(false); setAuth(true) }}>Đăng nhập để lưu lịch sử <Icon name="arrow" size={14} /></button></div> : <>{historyError && <p className="sidebar-note" role="alert">{historyError}</p>}{historyLoading && !history.length && <p className="sidebar-note">Đang tải lịch sử…</p>}{!historyLoading && !history.length && <p className="sidebar-note">Các cuộc trò chuyện của bạn sẽ xuất hiện ở đây.</p>}{history.map(item => <div className={`history-item ${activeId === item.id ? 'selected' : ''}`} key={item.id}><button className="history-open" onClick={() => openChat(item.id)} title={item.title}><Icon name="chat" size={15} /><span>{item.title}</span></button><button className="sidebar-icon history-delete" aria-label={`Xóa cuộc trò chuyện ${item.title}`} onClick={() => { setDrawer(false); setDeleting(item) }}><Icon name="trash" size={14} /></button></div>)}</>}</div>
      <div className="sidebar-bottom"><div className="sidebar-note source-assurance"><Icon name="shield" size={17} /><span>Câu trả lời có nguồn.<br />Tri thức được kiểm duyệt.</span></div>{user ? <button className="sidebar-account" onClick={() => navigate('account')}><span className="small-avatar">{user.name.slice(0, 1).toUpperCase()}</span><span><strong>{user.name}</strong><small>{user.role === 'admin' ? 'Quản trị viên' : 'Tài khoản bạn đọc'}</small></span><Icon name="arrow" size={16} /></button> : <button className="sidebar-account" disabled={sessionLoading} onClick={() => { setDrawer(false); setAuth(true) }}><span className="small-avatar"><Icon name="user" size={17} /></span><span><strong>Đăng nhập / Đăng ký</strong><small>Không gian dành riêng cho bạn</small></span><Icon name="arrow" size={16} /></button>}</div>
    </aside>
    <div className="main-shell" inert={isMobile && drawer}><header className="topbar"><div className="inline-actions"><button ref={menuButton} className="icon-button mobile-menu" aria-label="Mở điều hướng" aria-expanded={drawer} aria-controls="app-navigation" onClick={() => setDrawer(!drawer)}><Icon name="menu" /></button><div className="breadcrumb">Thư viện UTH<span>/</span><strong>{title}</strong></div></div><div className={`connection ${connected ? 'online' : ''}`} title={connected ? `Phiên bản ${health?.version || 'chưa xác định'}` : 'Chưa kết nối được máy chủ'}><span />{connected ? 'Đã kết nối' : 'Chưa kết nối'}</div></header>
      <main id="main-content" tabIndex={-1} className={`main-content ${view === 'chat' ? 'chat-page' : ''}`}>
        <div className="global-error"><ErrorNotice>{error}</ErrorNotice>{error && <button className="text-button" onClick={() => setError('')}>Đóng thông báo</button>}</div>
        <div hidden={view !== 'chat'} className="chat-host"><ChatWindow key={`${user?.id || 'guest'}-${chatKey}`} user={user} conversationId={openedId} onCreated={id => { setActiveId(id); if (user) setHistoryVersion(current => current + 1) }} /></div>
        {view === 'catalog' && <Catalog />}
        {view === 'loans' && <Loans key={user?.id || 'guest'} user={user} onLogin={() => setAuth(true)} />}
        {view === 'account' && user && <Account user={user} health={health} onLogout={() => logout().catch(() => {})} onDeleted={() => { resetSession(); navigate('chat') }} />}
        {view === 'admin' && user?.role === 'admin' && <Admin user={user} />}
        {(['account', 'admin'].includes(view) && (!user || (view === 'admin' && user.role !== 'admin'))) && <div className="content-page"><Empty icon="shield" title={sessionLoading ? 'Đang kiểm tra phiên…' : user ? 'Chỉ dành cho quản trị viên' : 'Vui lòng đăng nhập'}>{user ? 'Tài khoản của bạn không có quyền truy cập trang này.' : 'Đăng nhập để mở không gian của bạn.'}</Empty>{!user && !sessionLoading && <button className="primary center-button" onClick={() => setAuth(true)}>Đăng nhập</button>}</div>}
      </main>
    </div>
    {auth && <AuthModal onClose={() => setAuth(false)} onSuccess={nextUser => { resetSession(nextUser) }} />}
    {deleting && <Modal title="Xóa cuộc trò chuyện?" onClose={() => { if (!busy) setDeleting(null) }}><p><strong>{deleting.title}</strong></p><p>Cuộc trò chuyện này sẽ bị xóa vĩnh viễn khỏi lịch sử tài khoản.</p><ErrorNotice>{error}</ErrorNotice><div className="form-actions"><button className="secondary" disabled={busy} onClick={() => setDeleting(null)}>Giữ lại</button><button className="danger" disabled={busy} onClick={deleteConversation}>{busy ? 'Đang xóa…' : 'Xóa cuộc trò chuyện'}</button></div></Modal>}
  </div>
}
