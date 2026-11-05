// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Admin from './components/Admin.jsx'
import Loans from './components/Loans.jsx'

const response = (value, status = 200) => ({ ok: status < 400, status, json: async () => value })
const loan = { loan_id: 'loan-a', title: 'Khoản mượn của mã cũ', due_date: '2026-11-30' }
function deferred() {
  let resolve
  const promise = new Promise(done => { resolve = done })
  return { promise, resolve }
}
function setToken(value) {
  fireEvent.change(screen.getByLabelText('Mã truy cập thư viện'), { target: { value } })
}
function loadLoans() {
  fireEvent.submit(screen.getByLabelText('Mã truy cập thư viện').closest('form'))
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it.each([
  ['loans', response({ loans: [loan] })],
  ['error', response({ detail: 'Mã cũ không truy cập được.' }, 403)],
])('discards previous token %s after the library token changes', async (_, result) => {
  const pending = deferred()
  fetch.mockReturnValueOnce(pending.promise).mockResolvedValueOnce(response({ loans: [] }))
  render(<Loans user={{ id: 1 }} />)
  setToken('test-token-a')
  loadLoans()
  setToken('test-token-b')
  await act(async () => pending.resolve(result))
  expect(screen.queryByText(loan.title)).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
  loadLoans()
  expect(await screen.findByText('Chưa có khoản mượn')).toBeTruthy()
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ access_token: 'test-token-b' })
})

it('starts one loan lookup when the form is submitted twice before React renders', async () => {
  const pending = deferred()
  fetch.mockReturnValue(pending.promise)
  render(<Loans user={{ id: 1 }} />)
  setToken('test-token-a')
  act(() => { loadLoans(); loadLoans() })
  expect(fetch).toHaveBeenCalledTimes(1)
  await act(async () => pending.resolve(response({ loans: [loan] })))
  expect(screen.getByText(loan.title)).toBeTruthy()
})

it('sends one confirmed renewal when two immediate confirmation clicks are batched', async () => {
  const pending = deferred()
  fetch.mockResolvedValueOnce(response({ loans: [loan] })).mockReturnValue(pending.promise)
  render(<Loans user={{ id: 1 }} />)
  setToken('test-token-a')
  loadLoans()
  await screen.findByText(loan.title)
  fireEvent.click(screen.getByRole('button', { name: 'Gia hạn' }))
  const confirm = screen.getByRole('button', { name: 'Xác nhận gia hạn' })
  act(() => { fireEvent.click(confirm); fireEvent.click(confirm) })
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({ access_token: 'test-token-a', loan_id: 'loan-a', confirmation: true })
  await act(async () => pending.resolve(response({ status: 'renewed', loan_id: 'loan-a', due_date: '2026-12-07', message: 'Thư viện đã gia hạn.' })))
  expect(screen.getByText('Thư viện đã gia hạn.')).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Đã gửi · cần đối soát' }).disabled).toBe(true)
})

it('clears the previous token renewal result when another token is entered', async () => {
  fetch.mockResolvedValueOnce(response({ loans: [loan] })).mockResolvedValueOnce(response({ status: 'renewed', loan_id: 'loan-a', due_date: '2026-12-07', message: 'Kết quả gia hạn của mã cũ.' }))
  render(<Loans user={{ id: 1 }} />)
  setToken('test-token-a')
  loadLoans()
  await screen.findByText(loan.title)
  fireEvent.click(screen.getByRole('button', { name: 'Gia hạn' }))
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gia hạn' }))
  await screen.findByText('Kết quả gia hạn của mã cũ.')
  setToken('test-token-b')
  expect(screen.queryByText('Kết quả gia hạn của mã cũ.')).toBeNull()
  expect(screen.queryByText(loan.title)).toBeNull()
})

it('clears the pending renewal confirmation as soon as the library token changes', async () => {
  const pending = deferred()
  fetch.mockResolvedValueOnce(response({ loans: [loan] })).mockReturnValueOnce(pending.promise)
  render(<Loans user={{ id: 1 }} />)
  setToken('test-token-a')
  loadLoans()
  await screen.findByText(loan.title)
  fireEvent.click(screen.getByRole('button', { name: 'Gia hạn' }))
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gia hạn' }))
  setToken('test-token-b')
  const previousConfirmation = screen.queryByRole('dialog', { name: 'Xác nhận gia hạn' })
  await act(async () => pending.resolve(response({ status: 'renewed', loan_id: 'loan-a', due_date: '2026-12-07' })))
  expect(previousConfirmation).toBeNull()
})

it.each([
  ['acknowledgment', response({ status: 'renewed', loan_id: 'loan-a', due_date: '2026-12-07', message: 'Gia hạn cho mã cũ đã được xác nhận.' })],
  ['error', response({ detail: 'Gia hạn cho mã cũ chưa được xác nhận.' }, 503)],
])('discards a late renewal %s after token edit while keeping the loan blocked', async (_, result) => {
  const pending = deferred()
  fetch.mockResolvedValueOnce(response({ loans: [loan] })).mockReturnValueOnce(pending.promise).mockResolvedValueOnce(response({ loans: [loan] }))
  render(<Loans user={{ id: 1 }} />)
  setToken('test-token-a')
  loadLoans()
  await screen.findByText(loan.title)
  fireEvent.click(screen.getByRole('button', { name: 'Gia hạn' }))
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gia hạn' }))
  setToken('test-token-b')
  await act(async () => pending.resolve(result))
  expect(screen.queryByRole('heading', { name: 'Kết quả từ dịch vụ thư viện' })).toBeNull()
  expect(screen.queryByRole('alert')).toBeNull()
  expect(screen.getByRole('button', { name: 'Xem sách đang mượn' }).disabled).toBe(false)
  loadLoans()
  expect((await screen.findByRole('button', { name: 'Đã gửi · cần đối soát' })).disabled).toBe(true)
  expect(fetch).toHaveBeenCalledTimes(3)
  expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ access_token: 'test-token-b' })
})

it('creates one catalog record when the admin form is immediately submitted twice', async () => {
  const pending = deferred()
  const book = { id: 7, title: 'Tài liệu được lưu một lần', author: '', year: '', kind: 'books', subjects: '', description: '', source_url: 'https://example.edu/books/7', checked_at: '2026-11-03', published: false }
  let records = []
  fetch.mockImplementation(async (url, options) => {
    if (url === '/api/admin/knowledge') return response([])
    if (url === '/api/admin/books' && options.method === 'POST') return pending.promise
    if (url.startsWith('/api/admin/books?')) return response({ items: records, total: records.length, page: 1, page_size: 20 })
    throw new Error(`Unexpected request: ${url}`)
  })
  render(<Admin user={{ id: 1, role: 'admin' }} />)
  fireEvent.click(screen.getByRole('tab', { name: 'Danh mục' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Thêm tài liệu' }).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: 'Thêm tài liệu' }))
  fireEvent.change(screen.getByLabelText('Nhan đề'), { target: { value: book.title } })
  fireEvent.change(screen.getByLabelText('URL biểu ghi / nguồn'), { target: { value: book.source_url } })
  fireEvent.change(screen.getByLabelText('Ngày đối chiếu'), { target: { value: book.checked_at } })
  const form = screen.getByLabelText('Nhan đề').closest('form')
  act(() => { fireEvent.submit(form); fireEvent.submit(form) })
  await act(async () => { records = [book]; pending.resolve(response(book)) })
  const writes = fetch.mock.calls.filter(([url, options]) => url === '/api/admin/books' && options.method === 'POST')
  expect(writes).toHaveLength(1)
  expect(JSON.parse(writes[0][1].body)).toMatchObject({ title: book.title, source_url: book.source_url, checked_at: '2026-11-03', published: false })
  expect(screen.queryByRole('dialog', { name: 'Thêm tài liệu vào danh mục' })).toBeNull()
  expect(screen.getByRole('heading', { name: book.title })).toBeTruthy()
})
