// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import Catalog from './components/Catalog.jsx'
import ChatMessage from './components/ChatMessage.jsx'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
const response = value => ({ ok: true, status: 200, json: async () => value })

it.each(['faq', 'rag', 'catalog', 'catalog_ai', 'fallback'])('keeps %s routing details out of the reader conversation while retaining sources', mode => {
  const { container } = render(<ChatMessage item={{ role: 'assistant', content: 'Bạn có thể tra cứu tại đây.', mode, status: 'answered', sources: [{ title: 'Thư viện UTH', url: 'https://lic.ut.edu.vn/', checked_at: '2026-11-03' }] }} onSpeak={() => {}} />)
  expect(screen.getByText('Trợ lý Thư viện')).toBeTruthy()
  expect(container.querySelector('.message-meta .badge, .message-status')).toBeNull()
  expect(screen.getByRole('link', { name: /Thư viện UTH/ }).href).toBe('https://lic.ut.edu.vn/')
  expect(screen.getByText(/Đối chiếu:/)).toBeTruthy()
})

it('keeps review workflow details out of ordinary answers', () => {
  const { container } = render(<ChatMessage item={{ role: 'assistant', content: 'Hướng dẫn của thư viện.', status: 'reviewed_public' }} onSpeak={() => {}} />)
  expect(screen.getByText('Hướng dẫn của thư viện.')).toBeTruthy()
  expect(container.querySelector('.message-status')).toBeNull()
})

it.each([['needs_confirmation', 'Cần xác nhận'], ['clarify', 'Cần làm rõ'], ['not_found', 'Chưa đủ thông tin'], ['failed', 'Thất bại']])('preserves the actionable %s answer status', (status, label) => {
  render(<ChatMessage item={{ role: 'assistant', content: 'Vui lòng liên hệ thư viện để xác nhận.', status, mode: 'rag' }} onSpeak={() => {}} />)
  expect(screen.getByText(label)).toBeTruthy()
})

it.each(['available', 'unavailable', 'unknown'])('describes %s availability truthfully in reader language', status => {
  render(<ChatMessage item={{ role: 'assistant', content: 'Kết quả tìm tài liệu.', books: [{ title: 'Python cơ bản', url: 'https://lic.ut.edu.vn/book/1', availability_snapshot: { status } }] }} onSpeak={() => {}} />)
  expect(screen.getByText(status === 'unknown' ? /chưa xác nhận tình trạng còn sách hiện tại/ : /chưa phải xác nhận đặt mượn/)).toBeTruthy()
  expect(screen.queryByText(/biểu ghi|metadata|Trạng thái rỗi/i)).toBeNull()
  expect(fetch).not.toHaveBeenCalled()
})

it('presents saved search results and book details in reader language without losing freshness limits', async () => {
  const book = { id: 7, title: 'Python cơ bản', checked_at: '2026-11-03', url: 'https://lic.ut.edu.vn/book/7' }
  fetch.mockResolvedValueOnce(response({ source: 'local', total: 1, items: [book] })).mockResolvedValueOnce(response({ ...book, related: [{ ...book, id: 8, title: 'Lập trình căn bản' }] }))
  const { container } = render(<Catalog />)
  fireEvent.change(screen.getByLabelText('Từ khóa tìm kiếm'), { target: { value: 'Python' } })
  fireEvent.click(screen.getByRole('button', { name: 'Tra cứu', exact: true }))
  await screen.findByText(book.title)
  expect(screen.getByText(/không phản ánh tình trạng mượn hiện tại/)).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Xem thông tin gốc' }).href).toBe(book.url)
  fireEvent.click(screen.getByRole('button', { name: 'Xem chi tiết' }))
  await screen.findByText('Lập trình căn bản')
  expect(screen.getByText(/Chưa xác nhận tình trạng còn sách hiện tại/)).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Xem thông tin tại nguồn' }).href).toBe(book.url)
  expect(container.textContent).not.toMatch(/biểu ghi|bản ghi|metadata/i)
})
