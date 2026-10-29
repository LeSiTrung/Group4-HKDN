// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Catalog from './components/Catalog.jsx'
import BookAdmin from './components/BookAdmin.jsx'
import ChatMessage from './components/ChatMessage.jsx'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
const response = value => ({ ok: true, status: 200, json: async () => value })

it('labels local catalog snapshots and paginates the submitted query', async () => {
  fetch.mockResolvedValueOnce(response({ source: 'local', total: 21, page: 1, page_size: 20, items: [{ id: 1, title: 'Python từ nguồn thật', author: 'Tác giả', checked_at: '2026-10-28', url: 'https://example.edu/book/1' }] })).mockResolvedValueOnce(response({ source: 'local', total: 21, page: 2, page_size: 20, items: [{ id: 2, title: 'Biểu ghi trang hai', url: 'https://example.edu/book/2' }] }))
  render(<Catalog />)
  fireEvent.change(screen.getByLabelText('Từ khóa tìm kiếm'), { target: { value: 'Python' } })
  fireEvent.change(screen.getByLabelText('Nguồn tra cứu'), { target: { value: 'local' } })
  fireEvent.click(screen.getByRole('button', { name: 'Tra cứu', exact: true }))
  await screen.findByText('Python từ nguồn thật')
  expect(screen.getByText(/không phản ánh tình trạng mượn hiện tại/)).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Từ khóa tìm kiếm'), { target: { value: 'Đã sửa nhưng chưa tìm' } })
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Biểu ghi trang hai')
  expect(fetch.mock.calls[1][0]).toContain('q=Python')
  expect(fetch.mock.calls[1][0]).toContain('page=2')
  expect(fetch.mock.calls[1][0]).toContain('source=local')
})

it('creates an unpublished catalog record with source and review date', async () => {
  const mutate = vi.fn().mockResolvedValue({ id: 1 })
  render(<BookAdmin rows={[]} onMutate={mutate} />)
  fireEvent.click(screen.getByRole('button', { name: 'Thêm tài liệu' }))
  fireEvent.change(screen.getByLabelText('Nhan đề'), { target: { value: 'Tài liệu thử' } })
  fireEvent.change(screen.getByLabelText('URL biểu ghi / nguồn'), { target: { value: 'https://example.edu/book/1' } })
  fireEvent.change(screen.getByLabelText('Ngày đối chiếu'), { target: { value: '2026-10-28' } })
  fireEvent.click(screen.getByRole('button', { name: 'Lưu tài liệu' }))
  await waitFor(() => expect(mutate).toHaveBeenCalled())
  expect(mutate.mock.calls[0]).toMatchObject(['books', { method: 'POST', body: { title: 'Tài liệu thử', source_url: 'https://example.edu/book/1', published: false, kind: 'books' } }])
})

it('rejects invalid import JSON before network and imports a valid array atomically', async () => {
  const mutate = vi.fn().mockResolvedValue({ imported: 1 })
  render(<BookAdmin rows={[]} onMutate={mutate} />)
  fireEvent.click(screen.getByRole('button', { name: 'Nhập JSON' }))
  fireEvent.change(screen.getByLabelText('Dữ liệu JSON'), { target: { value: '{broken' } })
  fireEvent.click(screen.getByRole('button', { name: 'Nhập danh mục' }))
  await screen.findByRole('alert')
  expect(mutate).not.toHaveBeenCalled()
  const items = [{ title: 'Nguồn thử', source_url: 'https://example.edu/book/1', checked_at: '2026-10-28', published: false, kind: 'books' }]
  fireEvent.change(screen.getByLabelText('Dữ liệu JSON'), { target: { value: JSON.stringify(items) } })
  fireEvent.click(screen.getByRole('button', { name: 'Nhập danh mục' }))
  await waitFor(() => expect(mutate).toHaveBeenCalledWith('books/import', expect.objectContaining({ body: { items } })))
})

it('renders only supplied book records in the chat answer', () => {
  render(<ChatMessage item={{ role: 'assistant', content: 'Tài liệu có trong danh mục đã đối chiếu.', books: [{ id: 1, title: 'Sách có nguồn', author: 'Tác giả thật', url: 'https://example.edu/real-record', checked_at: '2026-10-28' }] }} onSpeak={() => {}} />)
  expect(screen.getByRole('link', { name: /Sách có nguồn/ }).href).toBe('https://example.edu/real-record')
  expect(screen.getByText(/không phải tình trạng mượn thời gian thực/)).toBeTruthy()
})

it('does not imply that an unchecked search link has been verified', () => {
  render(<ChatMessage item={{ role: 'assistant', content: 'Chưa tìm thấy bản ghi.', sources: [{ title: 'Tìm trên OPAC', url: 'https://example.edu/search', checked_at: null }] }} onSpeak={() => {}} />)
  expect(screen.getByText('Liên kết tra cứu; chưa kiểm tra kết quả')).toBeTruthy()
  expect(screen.queryByText(/Đối chiếu:/)).toBeNull()
})

it('opens a local book detail with related records from the API', async () => {
  fetch.mockResolvedValueOnce(response({ source: 'local', total: 1, items: [{ id: 7, title: 'Biểu ghi có chi tiết', url: 'https://example.edu/7' }] })).mockResolvedValueOnce(response({ id: 7, title: 'Biểu ghi có chi tiết', description: 'Mô tả đã đối chiếu từ nguồn.', checked_at: '2026-10-28', url: 'https://example.edu/7', related: [{ id: 8, title: 'Tài liệu liên quan thật', url: 'https://example.edu/8' }] }))
  render(<Catalog />)
  fireEvent.change(screen.getByLabelText('Từ khóa tìm kiếm'), { target: { value: 'chi tiết' } })
  fireEvent.click(screen.getByRole('button', { name: 'Tra cứu', exact: true }))
  fireEvent.click(await screen.findByRole('button', { name: 'Xem chi tiết' }))
  expect(await screen.findByText('Mô tả đã đối chiếu từ nguồn.')).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Tài liệu liên quan thật' }).href).toBe('https://example.edu/8')
  expect(fetch.mock.calls[1][0]).toBe('/api/catalog/7')
})

it('rejects imports larger than the 200-record backend limit', async () => {
  const mutate = vi.fn()
  render(<BookAdmin rows={[]} onMutate={mutate} />)
  fireEvent.click(screen.getByRole('button', { name: 'Nhập JSON' }))
  fireEvent.change(screen.getByLabelText('Dữ liệu JSON'), { target: { value: JSON.stringify(Array.from({ length: 201 }, () => ({ title: 'record' }))) } })
  fireEvent.click(screen.getByRole('button', { name: 'Nhập danh mục' }))
  expect(await screen.findByRole('alert')).toBeTruthy()
  expect(mutate).not.toHaveBeenCalled()
})
