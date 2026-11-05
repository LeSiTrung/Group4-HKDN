// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from './App.jsx'
import Account, { AuthModal } from './components/Account.jsx'
import BookDetails from './components/BookDetails.jsx'
import Catalog from './components/Catalog.jsx'
import ChatWindow from './components/ChatWindow.jsx'
import { api } from './services/chatApi.js'

const response = (value, status = 200) => ({ ok: status < 400, status, json: async () => value })
const answer = (text, id = null) => ({ answer: text, conversation_id: id, message_id: null, status: 'answered', sources: [], suggestions: [], mode: 'faq', books: [] })
const saved = text => ({ messages: [{ role: 'assistant', content: text, status: 'answered', sources: [], books: [] }] })
const reader = { id: 3, name: 'Bạn đọc A', role: 'reader', email: 'reader-a@example.test' }
function deferred() {
  let resolve, reject
  const promise = new Promise((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}
function send(text) {
  fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: text } })
  fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
}
function search(text) {
  fireEvent.change(screen.getByLabelText('Từ khóa tìm kiếm'), { target: { value: text } })
  fireEvent.submit(document.querySelector('.catalog-search'))
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
  Element.prototype.scrollIntoView = vi.fn()
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
  location.hash = ''
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('chat recovery and request isolation', () => {
  it('retries a failed guest turn without duplicating it in the conversation or context', async () => {
    fetch.mockRejectedValueOnce(new TypeError('offline')).mockResolvedValueOnce(response(answer('Đã kết nối lại.')))
    render(<ChatWindow user={null} />)
    send('Tìm sách Python')
    await screen.findByRole('alert')
    expect(screen.getByLabelText('Câu hỏi của bạn').value).toBe('Tìm sách Python')
    fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
    await screen.findByText('Đã kết nối lại.')
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ message: 'Tìm sách Python' })
    expect(screen.getAllByText('Tìm sách Python')).toHaveLength(1)
  })

  it('releases a timed-out send for manual retry while retaining the question', async () => {
    vi.useFakeTimers()
    fetch.mockImplementationOnce((url, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))))
      .mockResolvedValueOnce(response(answer('Đã thử lại.')))
    render(<ChatWindow user={null} />)
    send('Câu hỏi khi mạng chậm')
    await act(async () => { await vi.advanceTimersByTimeAsync(90000) })
    expect(screen.getByRole('alert').textContent).toMatch(/chưa phản hồi kịp/)
    expect(screen.getByLabelText('Câu hỏi của bạn').value).toBe('Câu hỏi khi mạng chậm')
    expect(screen.getByRole('button', { name: 'Gửi câu hỏi' }).disabled).toBe(false)
    await act(async () => { fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' })) })
    expect(screen.getByText('Đã thử lại.')).toBeTruthy()
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ message: 'Câu hỏi khi mạng chậm' })
  })

  it('reports a timeout while reading the response body without losing the question', async () => {
    vi.useFakeTimers()
    fetch.mockImplementationOnce(async (url, options) => ({
      ok: true, status: 200,
      json: () => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))),
    }))
    render(<ChatWindow user={null} />)
    send('Câu hỏi có phản hồi chậm')
    await act(async () => { await vi.advanceTimersByTimeAsync(90000) })
    expect(screen.getByRole('alert').textContent).toMatch(/chưa phản hồi kịp/)
    expect(screen.getByLabelText('Câu hỏi của bạn').value).toBe('Câu hỏi có phản hồi chậm')
    expect(screen.getByRole('button', { name: 'Gửi câu hỏi' }).disabled).toBe(false)
  })

  it('sends only once when the form is submitted twice before the request settles', async () => {
    const pending = deferred()
    fetch.mockReturnValue(pending.promise)
    render(<ChatWindow user={null} />)
    fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: 'Một câu hỏi' } })
    act(() => {
      fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
      fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
    })
    expect(fetch).toHaveBeenCalledTimes(1)
    await act(async () => pending.resolve(response(answer('Một câu trả lời.'))))
    expect(screen.getAllByText('Một câu hỏi')).toHaveLength(1)
  })

  it('preserves a newer draft when the previous send fails', async () => {
    const pending = deferred()
    fetch.mockReturnValue(pending.promise)
    render(<ChatWindow user={null} />)
    send('Câu hỏi trước')
    fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: 'Bản nháp mới' } })
    await act(async () => pending.reject(new TypeError('offline')))
    expect(screen.getByLabelText('Câu hỏi của bạn').value).toBe('Bản nháp mới')
  })

  it('discards a late send after switching conversations and sends the next question to the new one', async () => {
    const pending = deferred()
    fetch.mockResolvedValueOnce(response(saved('Lịch sử thứ nhất.'))).mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce(response(saved('Lịch sử thứ hai.'))).mockResolvedValueOnce(response(answer('Câu trả lời mới.', 22)))
    const onCreated = vi.fn()
    const { rerender } = render(<ChatWindow user={reader} conversationId={11} onCreated={onCreated} />)
    await screen.findByText('Lịch sử thứ nhất.')
    send('Câu hỏi cũ đang xử lý')
    rerender(<ChatWindow user={reader} conversationId={22} onCreated={onCreated} />)
    await screen.findByText('Lịch sử thứ hai.')
    await act(async () => pending.resolve(response(answer('Câu trả lời đến muộn.', 11))))
    expect(screen.queryByText('Câu trả lời đến muộn.')).toBeNull()
    expect(onCreated).not.toHaveBeenCalled()
    send('Câu hỏi trong hội thoại mới')
    await screen.findByText('Câu trả lời mới.')
    expect(JSON.parse(fetch.mock.calls[3][1].body)).toEqual({ message: 'Câu hỏi trong hội thoại mới', conversation_id: 22 })
  })

  it('clears private history and releases loading when the user becomes a guest', async () => {
    const pending = deferred()
    fetch.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(response(answer('Câu trả lời cho khách.')))
    const { rerender } = render(<ChatWindow user={reader} conversationId={11} />)
    rerender(<ChatWindow user={null} conversationId={null} />)
    expect(screen.getByRole('button', { name: 'Gửi câu hỏi' }).disabled).toBe(true)
    send('Câu hỏi của khách')
    await screen.findByText('Câu trả lời cho khách.')
    await act(async () => pending.resolve(response(saved('Nội dung riêng của A.'))))
    expect(screen.queryByText('Nội dung riêng của A.')).toBeNull()
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ message: 'Câu hỏi của khách' })
  })

  it('removes the previous user history while the next user history is loading or denied', async () => {
    const pending = deferred()
    fetch.mockResolvedValueOnce(response(saved('Nội dung riêng của A.'))).mockReturnValueOnce(pending.promise)
    const { rerender } = render(<ChatWindow user={reader} conversationId={11} />)
    await screen.findByText('Nội dung riêng của A.')
    rerender(<ChatWindow user={{ ...reader, id: 4, name: 'Bạn đọc B' }} conversationId={11} />)
    expect(screen.queryByText('Nội dung riêng của A.')).toBeNull()
    expect(screen.getByText('Đang mở cuộc trò chuyện…')).toBeTruthy()
    await act(async () => pending.resolve(response({ detail: 'Không tìm thấy hội thoại.' }, 404)))
    expect(screen.queryByText('Nội dung riêng của A.')).toBeNull()
  })

  it('keeps the new send busy when an older conversation request finishes first', async () => {
    const older = deferred(), newer = deferred()
    fetch.mockResolvedValueOnce(response(saved('Hội thoại thứ nhất.'))).mockReturnValueOnce(older.promise)
      .mockResolvedValueOnce(response(saved('Hội thoại thứ hai.'))).mockReturnValueOnce(newer.promise)
    const { rerender } = render(<ChatWindow user={reader} conversationId={11} />)
    await screen.findByText('Hội thoại thứ nhất.')
    send('Lượt cũ')
    rerender(<ChatWindow user={reader} conversationId={22} />)
    await screen.findByText('Hội thoại thứ hai.')
    send('Lượt mới')
    await act(async () => older.resolve(response(answer('Kết quả cũ.', 11))))
    expect(screen.getByRole('button', { name: 'Gửi câu hỏi' }).disabled).toBe(true)
    fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
    expect(fetch).toHaveBeenCalledTimes(4)
    await act(async () => newer.resolve(response(answer('Kết quả mới.', 22))))
    expect(screen.getByText('Kết quả mới.')).toBeTruthy()
    expect(screen.queryByText('Kết quả cũ.')).toBeNull()
  })
})

describe('catalog and detail recovery', () => {
  it('keeps pagination tied to the actual request when another submit happens during loading', async () => {
    const pending = deferred()
    fetch.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(response({ source: 'local', total: 21, page: 2, page_size: 20, items: [] }))
    render(<Catalog />)
    search('Python')
    search('Từ khóa chưa được tìm')
    await act(async () => pending.resolve(response({ source: 'local', total: 21, page: 1, page_size: 20, items: [{ id: 1, title: 'Kết quả Python' }] })))
    fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
    await screen.findByText('Chưa tìm thấy tài liệu phù hợp')
    expect(fetch.mock.calls[1][0]).toContain('q=Python&')
    expect(fetch.mock.calls[1][0]).toContain('page=2')
  })

  it('does not start competing catalog searches from two immediate submissions', async () => {
    const pending = deferred()
    fetch.mockReturnValue(pending.promise)
    render(<Catalog />)
    act(() => { search('Python'); search('Python') })
    expect(fetch).toHaveBeenCalledTimes(1)
    await act(async () => pending.resolve(response({ source: 'local', total: 0, items: [] })))
  })

  it('keeps catalog filters and input after failure so the same query can be retried', async () => {
    fetch.mockResolvedValueOnce(response({ detail: 'Mục lục tạm ngừng.' }, 503)).mockResolvedValueOnce(response({ source: 'local', total: 1, items: [{ id: 1, title: 'Tài liệu đã tìm lại' }] }))
    render(<Catalog />)
    fireEvent.change(screen.getByLabelText('Tìm theo'), { target: { value: 'author' } })
    search('Nguyễn Văn An')
    await screen.findByRole('alert')
    expect(screen.getByLabelText('Từ khóa tìm kiếm').value).toBe('Nguyễn Văn An')
    expect(screen.getByLabelText('Tìm theo').value).toBe('author')
    expect(screen.getByLabelText('Nguồn tra cứu').value).toBe('local')
    fireEvent.click(screen.getByRole('button', { name: 'Tra cứu', exact: true }))
    await screen.findByText('Tài liệu đã tìm lại')
    expect(fetch.mock.calls[1][0]).toBe(fetch.mock.calls[0][0])
  })

  it('hides the previous book as soon as a different detail starts loading', async () => {
    const pending = deferred()
    fetch.mockResolvedValueOnce(response({ id: 1, title: 'Tài liệu cũ' })).mockReturnValueOnce(pending.promise)
    const { rerender } = render(<BookDetails id={1} onClose={() => {}} />)
    await screen.findByText('Tài liệu cũ')
    rerender(<BookDetails id={2} onClose={() => {}} />)
    expect(screen.queryByText('Tài liệu cũ')).toBeNull()
    expect(screen.getByText('Đang mở thông tin tài liệu…')).toBeTruthy()
    await act(async () => pending.resolve(response({ id: 2, title: 'Tài liệu mới' })))
    expect(screen.getByText('Tài liệu mới')).toBeTruthy()
  })

  it('clears an earlier detail error and ignores an older response for another book', async () => {
    const older = deferred(), newer = deferred()
    fetch.mockResolvedValueOnce(response({ detail: 'Tài liệu đã gỡ.' }, 404)).mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const { rerender } = render(<BookDetails id={1} onClose={() => {}} />)
    await screen.findByRole('alert')
    rerender(<BookDetails id={2} onClose={() => {}} />)
    expect(screen.queryByRole('alert')).toBeNull()
    rerender(<BookDetails id={3} onClose={() => {}} />)
    await act(async () => newer.resolve(response({ id: 3, title: 'Tài liệu được chọn' })))
    await act(async () => older.resolve(response({ id: 2, title: 'Phản hồi cũ' })))
    expect(screen.getByText('Tài liệu được chọn')).toBeTruthy()
    expect(screen.queryByText('Phản hồi cũ')).toBeNull()
  })
})

describe('session expiry', () => {
  it('clears private history and pending deletion after a protected API reports an expired session', async () => {
    const expired = deferred()
    fetch.mockImplementation(async url => {
      if (url === '/api/auth/me') return response({ user: reader })
      if (url === '/health') return response({ capabilities: {} })
      if (url === '/api/conversations') return response([{ id: 11, title: 'Cuộc trò chuyện riêng của A' }])
      if (url === '/api/export') return expired.promise
      throw new Error(`Unexpected request: ${url}`)
    })
    render(<App />)
    await screen.findByRole('button', { name: 'Xóa cuộc trò chuyện Cuộc trò chuyện riêng của A' })
    fireEvent.click(screen.getByRole('button', { name: 'Xóa cuộc trò chuyện Cuộc trò chuyện riêng của A' }))
    const failure = api('/export').catch(error => error)
    await act(async () => { expired.resolve(response({ detail: 'Vui lòng đăng nhập.' }, 401)); await failure })
    expect(screen.queryAllByText('Cuộc trò chuyện riêng của A')).toHaveLength(0)
    expect(screen.queryByRole('dialog', { name: 'Xóa cuộc trò chuyện?' })).toBeNull()
    expect(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ })).toBeTruthy()
  })

  it('keeps a guest login form open after both the initial guest check and wrong-password 401', async () => {
    const expiry = vi.fn()
    window.addEventListener('library-session-expired', expiry)
    try {
      fetch.mockImplementation(async url => url === '/health' ? response({ capabilities: {} }) : response({ detail: url === '/api/auth/login' ? 'Email hoặc mật khẩu không đúng.' : 'Vui lòng đăng nhập.' }, 401))
      render(<App />)
      await waitFor(() => expect(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }).disabled).toBe(false))
      fireEvent.click(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }))
      fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'guest@example.test' } })
      fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'wrong-test-password' } })
      fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập', exact: true }))
      await screen.findByText('Email hoặc mật khẩu không đúng.')
      expect(screen.getByRole('dialog', { name: 'Chào mừng bạn trở lại' })).toBeTruthy()
      expect(expiry).not.toHaveBeenCalled()
    } finally { window.removeEventListener('library-session-expired', expiry) }
  })

  it('does not expire a new login when a request from the previous identity returns a late 401', async () => {
    const oldRequest = deferred()
    const nextReader = { ...reader, id: 4, name: 'Bạn đọc B', email: 'reader-b@example.test' }
    fetch.mockImplementation(async url => {
      if (url === '/api/auth/me') return response({ user: reader })
      if (url === '/health') return response({ capabilities: {} })
      if (url === '/api/conversations') return response([])
      if (url === '/api/export') return oldRequest.promise
      if (url === '/api/feedback') return response({ detail: 'Phiên đã hết hạn.' }, 401)
      if (url === '/api/auth/login') return response({ user: nextReader })
      throw new Error(`Unexpected request: ${url}`)
    })
    render(<App />)
    await screen.findByRole('button', { name: /Bạn đọc A/ })
    const previousFailure = api('/export').catch(error => error)
    await act(async () => { await api('/feedback', { method: 'POST', body: { message_id: 1, rating: 1 } }).catch(() => {}) })
    fireEvent.click(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }))
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader-b@example.test' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'test-only-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập', exact: true }))
    await screen.findByRole('button', { name: /Bạn đọc B/ })
    await act(async () => { oldRequest.resolve(response({ detail: 'Phiên cũ hết hạn.' }, 401)); await previousFailure })
    expect(screen.getByRole('button', { name: /Bạn đọc B/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Đăng nhập \/ Đăng ký/ })).toBeNull()
  })

  it('expires a failed account deletion instead of treating it like the initial guest check', async () => {
    fetch.mockImplementation(async url => {
      if (url === '/api/auth/me') return response({ user: reader })
      if (url === '/health') return response({ capabilities: {} })
      if (url === '/api/conversations') return response([])
      throw new Error(`Unexpected request: ${url}`)
    })
    render(<App />)
    await screen.findByRole('button', { name: /Bạn đọc A/ })
    fetch.mockResolvedValueOnce(response({ detail: 'Vui lòng đăng nhập.' }, 401))
    await act(async () => { await api('/auth/me', { method: 'DELETE', body: { password: 'test-only-password' } }).catch(() => {}) })
    expect(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ })).toBeTruthy()
  })

  it('discards private chat and history responses that finish after expiry while a guest continues chatting', async () => {
    const history = deferred(), previousChat = deferred()
    let chats = 0
    fetch.mockImplementation(async url => {
      if (url === '/api/auth/me') return response({ user: reader })
      if (url === '/health') return response({ capabilities: {} })
      if (url === '/api/conversations') return history.promise
      if (url === '/api/export') return response({ detail: 'Phiên đã hết hạn.' }, 401)
      if (url === '/api/chat') return ++chats === 1 ? previousChat.promise : response(answer('Câu trả lời khách.'))
      throw new Error(`Unexpected request: ${url}`)
    })
    render(<App />)
    await screen.findByRole('button', { name: /Bạn đọc A/ })
    send('Câu hỏi riêng của A')
    await act(async () => { await api('/export').catch(() => {}) })
    send('Câu hỏi công khai của khách')
    await screen.findByText('Câu trả lời khách.')
    await act(async () => {
      history.resolve(response([{ id: 11, title: 'Tiêu đề riêng của A' }]))
      previousChat.resolve(response(answer('Câu trả lời riêng của A.', 11)))
    })
    expect(screen.queryByText('Câu trả lời riêng của A.')).toBeNull()
    expect(screen.queryByText('Tiêu đề riêng của A')).toBeNull()
    expect(screen.queryByText('Câu hỏi riêng của A')).toBeNull()
    const payloads = fetch.mock.calls.filter(call => call[0] === '/api/chat').map(call => JSON.parse(call[1].body))
    expect(payloads[1]).toEqual({ message: 'Câu hỏi công khai của khách' })
  })

  it('does not reset the newly signed-in interface when the old logout completes late', async () => {
    const logout = deferred()
    const nextReader = { ...reader, id: 4, name: 'Bạn đọc B' }
    fetch.mockImplementation(async url => {
      if (url === '/api/auth/me') return response({ user: reader })
      if (url === '/health') return response({ capabilities: {} })
      if (url === '/api/conversations') return response([])
      if (url === '/api/auth/logout') return logout.promise
      if (url === '/api/export') return response({ detail: 'Phiên đã hết hạn.' }, 401)
      if (url === '/api/auth/login') return response({ user: nextReader })
      throw new Error(`Unexpected request: ${url}`)
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Bạn đọc A/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Đăng xuất', exact: true }))
    await act(async () => { await api('/export').catch(() => {}) })
    fireEvent.click(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }))
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader-b@example.test' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'test-only-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập', exact: true }))
    await screen.findByRole('button', { name: /Bạn đọc B/ })
    await act(async () => logout.resolve(response({ ok: true })))
    expect(screen.getByRole('button', { name: /Bạn đọc B/ })).toBeTruthy()
  })
})

describe('account action lifecycle', () => {
  function beginAction(action) {
    if (action === 'export') fireEvent.click(screen.getByRole('button', { name: 'Xuất dữ liệu JSON' }))
    if (action === 'password') {
      fireEvent.change(screen.getByLabelText('Mật khẩu hiện tại'), { target: { value: 'previous-test-password' } })
      fireEvent.change(screen.getByLabelText('Mật khẩu mới'), { target: { value: 'next-test-password' } })
      fireEvent.click(screen.getByRole('button', { name: 'Cập nhật mật khẩu' }))
    }
    if (action === 'delete') {
      fireEvent.click(screen.getByRole('button', { name: 'Xóa tài khoản của tôi' }))
      fireEvent.change(screen.getByLabelText('Xác nhận bằng mật khẩu hiện tại'), { target: { value: 'previous-test-password' } })
      fireEvent.click(screen.getByRole('button', { name: 'Xóa vĩnh viễn', exact: true }))
    }
  }

  function downloadSpies() {
    const create = vi.fn().mockReturnValue('blob:account-export')
    vi.stubGlobal('URL', class extends URL {
      static createObjectURL = create
      static revokeObjectURL = vi.fn()
    })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    return { create, click }
  }

  it.each(['export', 'password', 'delete'])('discards successful %s completion after the account screen unmounts', async action => {
    const pending = deferred(), onLogout = vi.fn(), onDeleted = vi.fn()
    const download = downloadSpies()
    fetch.mockReturnValue(pending.promise)
    const { unmount } = render(<Account user={reader} onLogout={onLogout} onDeleted={onDeleted} />)
    beginAction(action)
    expect(fetch).toHaveBeenCalledTimes(1)
    unmount()
    await act(async () => pending.resolve(response(action === 'export' ? { user: reader, conversations: [{ title: 'Dữ liệu riêng A' }] } : { ok: true })))
    expect(download.create).not.toHaveBeenCalled()
    expect(download.click).not.toHaveBeenCalled()
    expect(onLogout).not.toHaveBeenCalled()
    expect(onDeleted).not.toHaveBeenCalled()
  })

  it.each(['export', 'password', 'delete'])('discards successful %s completion after the account user changes', async action => {
    const pending = deferred(), onLogout = vi.fn(), onDeleted = vi.fn()
    const download = downloadSpies()
    fetch.mockReturnValue(pending.promise)
    const { rerender } = render(<Account user={reader} onLogout={onLogout} onDeleted={onDeleted} />)
    beginAction(action)
    rerender(<Account user={{ ...reader, id: 4, name: 'Bạn đọc B' }} onLogout={onLogout} onDeleted={onDeleted} />)
    await act(async () => pending.resolve(response(action === 'export' ? { user: reader, conversations: [] } : { ok: true })))
    expect(download.create).not.toHaveBeenCalled()
    expect(download.click).not.toHaveBeenCalled()
    expect(onLogout).not.toHaveBeenCalled()
    expect(onDeleted).not.toHaveBeenCalled()
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('dialog', { name: 'Xóa vĩnh viễn tài khoản?' })).toBeNull()
    expect(screen.getByLabelText('Mật khẩu hiện tại').value).toBe('')
    expect(screen.getByLabelText('Mật khẩu mới').value).toBe('')
  })

  it('downloads the active account export and leaves its password and deletion callbacks untouched', async () => {
    vi.useFakeTimers()
    const download = downloadSpies(), onLogout = vi.fn(), onDeleted = vi.fn()
    fetch.mockResolvedValue(response({ user: reader, conversations: [{ title: 'Lịch sử của bạn' }] }))
    render(<Account user={reader} onLogout={onLogout} onDeleted={onDeleted} />)
    await act(async () => beginAction('export'))
    expect(download.create).toHaveBeenCalledTimes(1)
    expect(download.create.mock.calls[0][0]).toBeInstanceOf(Blob)
    expect(download.click).toHaveBeenCalledTimes(1)
    expect(download.click.mock.instances[0].download).toMatch(/^thu-vien-lich-su-\d{4}-\d{2}-\d{2}\.json$/)
    expect(screen.getByRole('status').textContent).toMatch(/Đã xuất dữ liệu/)
    expect(onLogout).not.toHaveBeenCalled()
    expect(onDeleted).not.toHaveBeenCalled()
    await act(async () => vi.advanceTimersByTimeAsync(1000))
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:account-export')
  })

  it('resets the active password form and signs out only after a successful change', async () => {
    const pending = deferred(), onLogout = vi.fn().mockResolvedValue(undefined)
    fetch.mockReturnValue(pending.promise)
    render(<Account user={reader} onLogout={onLogout} onDeleted={() => {}} />)
    beginAction('password')
    expect(onLogout).not.toHaveBeenCalled()
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ current_password: 'previous-test-password', new_password: 'next-test-password' })
    await act(async () => pending.resolve(response({ ok: true })))
    expect(onLogout).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('Mật khẩu hiện tại').value).toBe('')
    expect(screen.getByLabelText('Mật khẩu mới').value).toBe('')
  })

  it('resets the active session only after confirmed account deletion succeeds', async () => {
    const pending = deferred(), onDeleted = vi.fn()
    fetch.mockReturnValue(pending.promise)
    render(<Account user={reader} onLogout={() => {}} onDeleted={onDeleted} />)
    beginAction('delete')
    expect(onDeleted).not.toHaveBeenCalled()
    expect(fetch.mock.calls[0][0]).toBe('/api/auth/me')
    expect(fetch.mock.calls[0][1].method).toBe('DELETE')
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ password: 'previous-test-password' })
    await act(async () => pending.resolve(response({ ok: true })))
    expect(onDeleted).toHaveBeenCalledTimes(1)
  })

  it('does not download the previous account export after expiry and a new login', async () => {
    const previousExport = deferred(), download = downloadSpies()
    const nextReader = { ...reader, id: 4, name: 'Bạn đọc B' }
    fetch.mockImplementation(async url => {
      if (url === '/api/auth/me') return response({ user: reader })
      if (url === '/health') return response({ capabilities: {} })
      if (url === '/api/conversations') return response([])
      if (url === '/api/export') return previousExport.promise
      if (url === '/api/feedback') return response({ detail: 'Phiên đã hết hạn.' }, 401)
      if (url === '/api/auth/login') return response({ user: nextReader })
      throw new Error(`Unexpected request: ${url}`)
    })
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Bạn đọc A/ }))
    beginAction('export')
    await act(async () => { await api('/feedback', { method: 'POST', body: { message_id: 1, rating: 1 } }).catch(() => {}) })
    fireEvent.click(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }))
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader-b@example.test' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'test-only-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập', exact: true }))
    await screen.findByRole('button', { name: /Bạn đọc B/ })
    await act(async () => previousExport.resolve(response({ user: reader, conversations: [{ title: 'Nội dung riêng A' }] })))
    expect(download.create).not.toHaveBeenCalled()
    expect(download.click).not.toHaveBeenCalled()
    expect(screen.getByRole('button', { name: /Bạn đọc B/ })).toBeTruthy()
  })

  it('keeps the new account action busy and error-free when an old account request fails', async () => {
    vi.useFakeTimers()
    const older = deferred(), newer = deferred(), download = downloadSpies()
    fetch.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise)
    const { rerender } = render(<Account user={reader} onLogout={() => {}} onDeleted={() => {}} />)
    beginAction('export')
    rerender(<Account user={{ ...reader, id: 4, name: 'Bạn đọc B' }} onLogout={() => {}} onDeleted={() => {}} />)
    expect(screen.getByRole('button', { name: 'Xuất dữ liệu JSON' }).disabled).toBe(false)
    beginAction('export')
    await act(async () => older.reject(new TypeError('offline')))
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByRole('button', { name: 'Xuất dữ liệu JSON' }).disabled).toBe(true)
    await act(async () => newer.resolve(response({ user: { ...reader, id: 4 }, conversations: [] })))
    expect(download.click).toHaveBeenCalledTimes(1)
    await act(async () => vi.advanceTimersByTimeAsync(1000))
  })

  it('keeps service implementation diagnostics out of the reader account', () => {
    render(<Account user={reader} health={{ version: 'operator-build', knowledge_count: 7, capabilities: { vectors: { ready: true } } }} onLogout={() => {}} onDeleted={() => {}} />)
    expect(screen.getByRole('button', { name: 'Xuất dữ liệu JSON' })).toBeTruthy()
    expect(screen.queryByRole('heading', { name: 'Trạng thái dịch vụ' })).toBeNull()
    expect(screen.queryByText(/Phiên bản|operator-build|Tìm kiếm ngữ nghĩa/)).toBeNull()
  })

  it('retains existing service diagnostics for the administrator account', () => {
    render(<Account user={{ ...reader, role: 'admin' }} health={{ version: 'operator-build', knowledge_count: 7, capabilities: { vectors: { ready: true } } }} onLogout={() => {}} onDeleted={() => {}} />)
    expect(screen.getByRole('heading', { name: 'Trạng thái dịch vụ' })).toBeTruthy()
    expect(screen.getByText(/Phiên bản operator-build/)).toBeTruthy()
    expect(screen.getByText('Tìm kiếm ngữ nghĩa')).toBeTruthy()
  })

  it.each(['login', 'register'])('ignores a successful %s after its authentication dialog unmounts', async action => {
    const pending = deferred(), onSuccess = vi.fn()
    fetch.mockReturnValue(pending.promise)
    const { unmount } = render(<AuthModal onSuccess={onSuccess} onClose={() => {}} />)
    if (action === 'register') {
      fireEvent.click(screen.getByRole('button', { name: 'Đăng ký', exact: true }))
      fireEvent.change(screen.getByLabelText('Họ và tên'), { target: { value: 'Bạn đọc A' } })
    }
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader-a@example.test' } })
    fireEvent.change(screen.getByLabelText('Mật khẩu', { exact: true }), { target: { value: 'test-only-password' } })
    fireEvent.click(screen.getByRole('button', { name: action === 'login' ? 'Đăng nhập' : 'Tạo tài khoản', exact: true }))
    expect(fetch.mock.calls[0][0]).toBe(`/api/auth/${action}`)
    unmount()
    await act(async () => pending.resolve(response({ user: reader })))
    expect(onSuccess).not.toHaveBeenCalled()
  })

  it('does not replace the current user when an earlier closed login dialog finishes late', async () => {
    const previousLogin = deferred()
    const nextReader = { ...reader, id: 4, name: 'Bạn đọc B' }
    let logins = 0
    fetch.mockImplementation(async url => {
      if (url === '/api/auth/me') return response({ detail: 'Vui lòng đăng nhập.' }, 401)
      if (url === '/health') return response({ capabilities: {} })
      if (url === '/api/conversations') return response([])
      if (url === '/api/auth/login') return ++logins === 1 ? previousLogin.promise : response({ user: nextReader })
      throw new Error(`Unexpected request: ${url}`)
    })
    render(<App />)
    await waitFor(() => expect(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }).disabled).toBe(false))
    for (const name of ['reader-a@example.test', 'reader-b@example.test']) {
      fireEvent.click(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }))
      fireEvent.change(screen.getByLabelText('Email'), { target: { value: name } })
      fireEvent.change(screen.getByLabelText('Mật khẩu'), { target: { value: 'test-only-password' } })
      fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập', exact: true }))
      if (name === 'reader-a@example.test') fireEvent.click(screen.getByRole('button', { name: 'Đóng hộp thoại' }))
    }
    await screen.findByRole('button', { name: /Bạn đọc B/ })
    await act(async () => previousLogin.resolve(response({ user: reader })))
    expect(screen.getByRole('button', { name: /Bạn đọc B/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Bạn đọc A/ })).toBeNull()
  })
})
