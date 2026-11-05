// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import ChatMessage from './components/ChatMessage.jsx'

afterEach(cleanup)

const book = {
  id: 1,
  title: 'Giáo trình lập trình thử nghiệm',
  author: 'Tác giả thử nghiệm',
  url: 'https://lic.ut.edu.vn/synthetic-recommendation/',
  checked_at: '2026-10-28',
}

it.each([['catalog', 'Tra cứu danh mục'], ['catalog_ai', 'AI tìm tài liệu']])('shows the recommendation reason and source for %s', (mode, label) => {
  const reason = 'Nhan đề đề cập lập trình; phù hợp chủ đề bạn muốn tìm.'
  render(<ChatMessage item={{ role: 'assistant', mode, content: 'Mình gợi ý các tài liệu sau.', books: [{ ...book, recommendation_reason: reason }] }} onSpeak={() => {}} />)
  expect(screen.queryByText(label)).toBeNull()
  expect(screen.getByText('Vì sao gợi ý:')).toBeTruthy()
  expect(screen.getByText(reason, { exact: false })).toBeTruthy()
  expect(screen.getByRole('link', { name: book.title }).href).toBe(book.url)
  expect(screen.getByText(/chưa xác nhận tình trạng còn sách hiện tại/)).toBeTruthy()
})

it('renders recommendation evidence as literal text without creating HTML', () => {
  const reason = '<img src=x onerror="alert(1)"><script>alert(2)</script>'
  const { container } = render(<ChatMessage item={{ role: 'assistant', content: 'Tài liệu có nguồn.', books: [{ ...book, recommendation_reason: reason }] }} onSpeak={() => {}} />)
  expect(screen.getByText(reason, { exact: false }).textContent).toContain(reason)
  expect(container.querySelector('img, script')).toBeNull()
})
