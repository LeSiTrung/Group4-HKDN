// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Admin from './components/Admin.jsx'
import ChatMessage from './components/ChatMessage.jsx'

const response = (value, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => value })
const item = { message_id: 7, question: '<script>question</script>', answer: '<img src=x onerror=alert(1)>', comment: 'Please correct', rating: -1, status: 'answered', mode: 'faq', sources: [{ title: 'Unsafe source', url: 'javascript:alert(1)' }, { title: 'Library source', url: 'https://lic.uth.edu.vn/' }] }
const data = { items: [item], total: 21, page: 1, page_size: 20, summary: { positive: 3, negative: 18 } }
beforeEach(() => vi.stubGlobal('fetch', vi.fn().mockImplementation(async url => response(url.includes('/feedback') ? data : []))))
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('loads feedback once, renders untrusted strings as text and blocks unsafe source URLs', async () => {
  const { container } = render(<Admin user={{ id: 1 }} />)
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))
  fireEvent.click(screen.getByRole('tab', { name: 'Phản hồi chatbot' }))
  expect(await screen.findByText(item.question)).toBeTruthy()
  expect(screen.getByText(item.answer)).toBeTruthy()
  expect(screen.getByText(item.comment)).toBeTruthy()
  expect(container.querySelector('script, img')).toBeNull()
  expect(screen.queryByRole('link', { name: 'Unsafe source' })).toBeNull()
  expect(screen.getByRole('link', { name: 'Library source' }).getAttribute('href')).toBe('https://lic.uth.edu.vn/')
  expect(fetch.mock.calls.filter(([url]) => url.includes('/admin/feedback'))).toHaveLength(1)
  expect(screen.getByText(/Hữu ích: 3/)).toBeTruthy()
})

it('paginates and resets the page on rating changes without affecting other admin endpoints', async () => {
  render(<Admin user={{ id: 1 }} />)
  fireEvent.click(screen.getByRole('tab', { name: 'Phản hồi chatbot' }))
  await screen.findByText(item.question)
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await waitFor(() => expect(fetch.mock.calls.at(-1)[0]).toContain('page=2'))
  await screen.findByText(item.question)
  fireEvent.change(screen.getByLabelText('Lọc đánh giá'), { target: { value: '-1' } })
  await waitFor(() => {
    expect(fetch.mock.calls.at(-1)[0]).toContain('rating=-1')
    expect(fetch.mock.calls.at(-1)[0]).toContain('page=1')
  })
  fireEvent.click(screen.getByRole('tab', { name: 'Danh mục' }))
  await waitFor(() => expect(fetch.mock.calls.at(-1)[0]).toBe('/api/admin/books'))
})

it('shows loading, empty feedback and recoverable API errors', async () => {
  let resolve
  fetch.mockImplementation(url => url.includes('/feedback') ? new Promise(done => { resolve = done }) : Promise.resolve(response([])))
  render(<Admin user={{ id: 1 }} />)
  fireEvent.click(screen.getByRole('tab', { name: 'Phản hồi chatbot' }))
  expect(screen.getByRole('status').textContent).toContain('Đang tải')
  resolve(response({ ...data, items: [], total: 0 }))
  expect(await screen.findByText('Chưa có phản hồi phù hợp')).toBeTruthy()
  fetch.mockResolvedValueOnce(response({ detail: 'Feedback service unavailable' }, false))
  fireEvent.click(screen.getByRole('button', { name: 'Làm mới' }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Feedback service unavailable')
})

it('discloses sharing before explicit rating and makes no automatic feedback request', async () => {
  render(<ChatMessage item={{ id: 7, role: 'assistant', content: 'An answer' }} user={{ name: 'Reader' }} onSpeak={() => {}} />)
  const positive = screen.getByRole('button', { name: 'Câu trả lời hữu ích' })
  const disclosure = document.getElementById(positive.getAttribute('aria-describedby'))
  expect(disclosure.textContent).toContain('câu hỏi liền trước')
  expect(disclosure.textContent).toContain('quản trị viên')
  expect(fetch).not.toHaveBeenCalled()
  fireEvent.click(positive)
  await screen.findByText('Đã gửi đánh giá')
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch.mock.calls[0][0]).toBe('/api/feedback')
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ message_id: 7, rating: 1 })
})

it('does not solicit or log guest ratings', () => {
  render(<ChatMessage item={{ role: 'assistant', content: 'Guest answer' }} user={null} onSpeak={() => {}} />)
  expect(screen.queryByRole('button', { name: 'Câu trả lời hữu ích' })).toBeNull()
  expect(fetch).not.toHaveBeenCalled()
})
