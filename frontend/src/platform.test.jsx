// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { api, safeUrl } from './services/chatApi.js'
import ChatWindow from './components/ChatWindow.jsx'
import Loans from './components/Loans.jsx'
import Admin from './components/Admin.jsx'
import Catalog from './components/Catalog.jsx'
import { AuthModal } from './components/Account.jsx'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn()); Element.prototype.scrollIntoView = vi.fn()
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
const response = (value, ok = true, status = 200) => ({ ok, status, json: async () => value })

describe('API security contract', () => {
  it('sends cookies and CSRF marker with JSON body', async () => {
    fetch.mockResolvedValue(response({ answer: 'ok' }))
    await api('/chat', { method: 'POST', body: { message: 'Xin chào' } })
    expect(fetch.mock.calls[0][0]).toBe('/api/chat')
    expect(fetch.mock.calls[0][1]).toMatchObject({ credentials: 'include', headers: { 'X-Requested-With': 'LibraryAssistant', 'Content-Type': 'application/json' }, body: JSON.stringify({ message: 'Xin chào' }) })
  })
  it('reports validation errors and blocks executable source URLs', async () => {
    fetch.mockResolvedValue(response({ detail: [{ msg: 'Câu hỏi quá dài' }] }, false, 422))
    await expect(api('/chat')).rejects.toThrow('Câu hỏi quá dài')
    expect(safeUrl('javascript:alert(1)')).toBeUndefined()
    expect(safeUrl('data:text/html,test')).toBeUndefined()
    expect(safeUrl('https://lic.uth.edu.vn/')).toBe('https://lic.uth.edu.vn/')
  })
})

describe('reader workflows', () => {
  it('renders grounded answer and safe sources, sends conversation ID', async () => {
    fetch.mockResolvedValue(response({ answer: 'Hướng dẫn tìm tài liệu.', status: 'reviewed_public', sources: [{ title: 'Thư viện', url: 'https://lic.uth.edu.vn/', checked_at: '2026-10-28' }], suggestions: ['Tìm sách thế nào?'], mode: 'faq', conversation_id: 8 }))
    render(<ChatWindow user={null} conversationId={8} onCreated={() => {}} />)
    fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: 'Tìm tài liệu' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
    expect(await screen.findByText('Hướng dẫn tìm tài liệu.')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Thư viện/ }).getAttribute('href')).toBe('https://lic.uth.edu.vn/')
    expect(JSON.parse(fetch.mock.calls.at(-1)[1].body)).toMatchObject({ message: 'Tìm tài liệu', conversation_id: 8 })
  })
  it('preserves a failed question for correction and retry', async () => {
    fetch.mockRejectedValue(new TypeError('Failed to fetch'))
    render(<ChatWindow user={null} onCreated={() => {}} />)
    fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: 'Câu hỏi cần giữ' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
    await screen.findByRole('alert')
    expect(screen.getByLabelText('Câu hỏi của bạn').value).toBe('Câu hỏi cần giữ')
  })
  it('explains unsupported speech recognition without sending a request', async () => {
    vi.stubGlobal('SpeechRecognition', undefined)
    vi.stubGlobal('webkitSpeechRecognition', undefined)
    render(<ChatWindow user={null} onCreated={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Nhập bằng giọng nói' }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(fetch).not.toHaveBeenCalled()
  })
  it('sends bounded plain guest context without source metadata or identity', async () => {
    fetch.mockResolvedValueOnce(response({ answer: 'Tài liệu Python đã đối chiếu.', sources: [{ title: 'Nguồn thật', url: 'https://example.edu/' }], books: [], conversation_id: null })).mockResolvedValueOnce(response({ answer: 'Hướng dẫn tiếp nối.', sources: [], conversation_id: null }))
    render(<ChatWindow user={null} onCreated={() => {}} />)
    fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: 'Tìm sách Python' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
    await screen.findByText('Tài liệu Python đã đối chiếu.')
    fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: 'Có cuốn nào cho người mới?' } })
    fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
    await screen.findByText('Hướng dẫn tiếp nối.')
    const payload = JSON.parse(fetch.mock.calls[1][1].body)
    expect(payload.history).toEqual([{ role: 'user', content: 'Tìm sách Python' }, { role: 'assistant', content: 'Tài liệu Python đã đối chiếu.' }])
    expect(payload.conversation_id).toBeUndefined()
  })
  it('shows catalog upstream failure with a safe direct search link', async () => {
    fetch.mockResolvedValue(response({ detail: 'Mục lục chưa phản hồi', search_url: 'https://lic.uth.edu.vn/search?q=test' }, false, 503))
    render(<Catalog />)
    fireEvent.change(screen.getByLabelText('Từ khóa tìm kiếm'), { target: { value: 'test' } })
    fireEvent.click(screen.getByRole('button', { name: 'Tra cứu' }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByRole('link', { name: /Tra cứu trực tiếp/ }).href).toContain('https://lic.uth.edu.vn/search')
    expect(screen.queryByText('Chưa tìm thấy tài liệu phù hợp')).toBeNull()
  })
  it('registers a reader through the cookie API without browser storage', async () => {
    const onSuccess = vi.fn()
    fetch.mockResolvedValue(response({ user: { id: 3, name: 'Bạn đọc', role: 'reader' } }))
    render(<AuthModal onClose={() => {}} onSuccess={onSuccess} />)
    fireEvent.click(screen.getByRole('button', { name: 'Đăng ký', exact: true }))
    fireEvent.change(screen.getByLabelText('Họ và tên'), { target: { value: 'Bạn đọc' } })
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader@example.test' } })
    const password = screen.getByLabelText('Mật khẩu', { exact: true })
    expect(password.minLength).toBe(12)
    fireEvent.change(password, { target: { value: 'long-test-only-password' } })
    fireEvent.click(screen.getByRole('button', { name: 'Tạo tài khoản', exact: true }))
    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(expect.objectContaining({ role: 'reader' })))
    expect(fetch.mock.calls[0][0]).toBe('/api/auth/register')
    expect(localStorage.length + sessionStorage.length).toBe(0)
  })
  it('loads loans without persisting token and requires confirmation before renewal', async () => {
    fetch.mockResolvedValueOnce(response({ loans: [{ id: 'loan-1', title: 'Sách thử', due_date: '2026-11-01' }] })).mockResolvedValueOnce(response({ status: 'confirmed', message: 'Đã xác nhận từ hệ thống thư viện' }))
    HTMLDialogElement.prototype.showModal = function () { this.open = true }
    HTMLDialogElement.prototype.close = function () { this.open = false }
    render(<Loans user={{ id: 1 }} />)
    fireEvent.change(screen.getByLabelText('Mã truy cập thư viện'), { target: { value: 'private-session-token' } })
    fireEvent.click(screen.getByRole('button', { name: 'Xem sách đang mượn' }))
    await screen.findByText('Sách thử')
    fireEvent.click(screen.getByRole('button', { name: 'Gia hạn' }))
    expect(fetch).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gia hạn' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    const payload = JSON.parse(fetch.mock.calls[1][1].body)
    expect(payload).toMatchObject({ access_token: 'private-session-token', loan_id: 'loan-1', confirmation: true })
    expect(payload.idempotency_key).toBeTruthy()
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
  it('serializes numeric upstream loan IDs as strings for the renewal contract', async () => {
    fetch.mockResolvedValueOnce(response({ loans: [{ loan_id: 42, title: 'Khoản mượn số' }] })).mockResolvedValueOnce(response({ status: 'renewed', loan_id: '42', due_date: '2026-11-01' }))
    render(<Loans user={{ id: 1 }} />)
    fireEvent.change(screen.getByLabelText('Mã truy cập thư viện'), { target: { value: 'test-only-token' } })
    fireEvent.click(screen.getByRole('button', { name: 'Xem sách đang mượn' }))
    await screen.findByText('Khoản mượn số')
    fireEvent.click(screen.getByRole('button', { name: 'Gia hạn' }))
    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gia hạn' }))
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2))
    expect(JSON.parse(fetch.mock.calls[1][1].body).loan_id).toBe('42')
  })
})

describe('administration', () => {
  it('supports keyboard navigation between administration tabs', async () => {
    fetch.mockImplementation(async () => response([]))
    render(<Admin user={{ id: 1, role: 'admin' }} />)
    const first = screen.getByRole('tab', { name: 'Kho tri thức' })
    first.focus()
    fireEvent.keyDown(first, { key: 'ArrowRight' })
    const books = screen.getByRole('tab', { name: 'Danh mục' })
    expect(books.getAttribute('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(books)
    await waitFor(() => expect(fetch.mock.calls.some(call => call[0] === '/api/admin/books')).toBe(true))
  })
  it('creates knowledge as unpublished draft and serializes aliases', async () => {
    fetch.mockImplementation(async (path, options) => response(options?.method === 'POST' ? { id: 8 } : []))
    render(<Admin user={{ id: 1, role: 'admin' }} />)
    await waitFor(() => expect(fetch).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('button', { name: 'Thêm tri thức' }))
    for (const [label, value] of [['Tiêu đề', 'Nguồn thử'], ['Câu hỏi chính', 'Câu hỏi?'], ['Câu hỏi tương đương', 'Cách một, Cách hai'], ['Nội dung trả lời', 'Nội dung bản nháp'], ['Tên nguồn', 'Thư viện'], ['URL nguồn', 'https://lic.uth.edu.vn/'], ['Ngày đối chiếu', '2026-10-28']]) fireEvent.change(screen.getByLabelText(label, { exact: true }), { target: { value } })
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mục tri thức' }))
    await waitFor(() => expect(fetch.mock.calls.some(call => call[1].method === 'POST')).toBe(true))
    const call = fetch.mock.calls.find(item => item[1].method === 'POST')
    expect(JSON.parse(call[1].body)).toMatchObject({ published: false, status: 'needs_confirmation', aliases: ['Cách một', 'Cách hai'] })
  })
  it('submits a cited schedule with numeric weekday and verified date', async () => {
    fetch.mockImplementation(async () => response([]))
    render(<Admin user={{ id: 1, role: 'admin' }} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Lịch phục vụ' }))
    for (const [label, value] of [['Cơ sở / địa điểm', '1'], ['Giờ mở cửa', '08:00'], ['Giờ đóng cửa', '17:00'], ['Hiệu lực từ', '2026-10-28'], ['Hiệu lực đến', '2026-11-01'], ['Người / đơn vị xác minh', 'Đơn vị thử'], ['Ghi chú', 'Lịch thử đã đối chiếu'], ['URL nguồn xác minh', 'https://lic.uth.edu.vn/'], ['Ngày đối chiếu nguồn', '2026-10-28']]) fireEvent.change(screen.getByLabelText(label, { exact: true }), { target: { value } })
    fireEvent.click(screen.getByRole('button', { name: 'Lưu lịch phục vụ' }))
    await waitFor(() => expect(fetch.mock.calls.some(call => call[1].method === 'POST')).toBe(true))
    const call = fetch.mock.calls.find(item => item[1].method === 'POST')
    expect(call[0]).toBe('/api/admin/schedules')
    expect(JSON.parse(call[1].body)).toMatchObject({ weekday: 0, source_url: 'https://lic.uth.edu.vn/', checked_at: '2026-10-28' })
  })
  it('permits closed-day exceptions without invented opening times', async () => {
    fetch.mockImplementation(async () => response([]))
    render(<Admin user={{ id: 1, role: 'admin' }} />)
    fireEvent.click(screen.getByRole('tab', { name: 'Lịch phục vụ' }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Nghỉ phục vụ cả ngày/ }))
    expect(screen.getByLabelText('Giờ mở cửa').disabled).toBe(true)
    expect(screen.getByLabelText('Giờ đóng cửa').required).toBe(false)
    for (const [label, value] of [['Hiệu lực từ', '2026-10-28'], ['Hiệu lực đến', '2026-10-28'], ['Người / đơn vị xác minh', 'Kiểm thử'], ['Ghi chú', 'Ngoại lệ kiểm thử'], ['URL nguồn xác minh', 'https://lic.uth.edu.vn/'], ['Ngày đối chiếu nguồn', '2026-10-28']]) fireEvent.change(screen.getByLabelText(label, { exact: true }), { target: { value } })
    fireEvent.click(screen.getByRole('button', { name: 'Lưu lịch phục vụ' }))
    await waitFor(() => expect(fetch.mock.calls.some(call => call[1].method === 'POST')).toBe(true))
    const data = JSON.parse(fetch.mock.calls.find(item => item[1].method === 'POST')[1].body)
    expect(data.closed).toBe(true)
    expect(data.opens).toBeUndefined()
  })
})
