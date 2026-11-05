// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import ChatMessage from './components/ChatMessage.jsx'
import ChatWindow from './components/ChatWindow.jsx'

const pdf = 'https://opacthuvien.ut.edu.vn/opac/Upload/HDSD_TRACUU_OPAC.v1.1.pdf'
const message = (page = 3, changes = {}) => ({ role: 'assistant', content: 'Mở OPAC và nhập từ khóa để tìm sách.',
  status: 'answered', mode: 'faq', sources: [{ title: 'Hướng dẫn OPAC của thư viện UTH', url: `${pdf}#page=${page}`, checked_at: '2026-10-28' }], ...changes })

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
  Element.prototype.scrollIntoView = vi.fn()
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it.each([
  [3, /nhập từ khóa và xem kết quả/i],
  [4, /chọn loại tài liệu/i],
  [6, /tìm theo nhan đề hoặc tác giả/i],
])('shows the reviewed illustration for cited PDF page %s', (page, name) => {
  render(<ChatMessage item={message(page)} onSpeak={() => {}} />)
  const image = screen.getByRole('img', { name })
  expect(image.getAttribute('src')).toMatch(/opac-page-(3|4|6).*\.webp/)
  expect(image.getAttribute('loading')).toBe('lazy')
  expect(Number(image.getAttribute('width'))).toBeGreaterThan(0)
  expect(Number(image.getAttribute('height'))).toBeGreaterThan(0)
  expect(screen.getByText(/số liệu trong ảnh là minh họa/i)).toBeTruthy()
  expect(screen.getByRole('link', { name: `Xem trang ${page} trong PDF gốc` }).href).toBe(`${pdf}#page=${page}`)
  expect(screen.getByText('Mở OPAC và nhập từ khóa để tìm sách.')).toBeTruthy()
})

it('opens a keyboard-accessible enlarged image and closes it without changing the answer', () => {
  render(<ChatMessage item={message()} onSpeak={() => {}} />)
  fireEvent.click(screen.getByRole('button', { name: /phóng to hình/i }))
  const dialog = screen.getByRole('dialog', { name: /hình hướng dẫn.*trang 3/i })
  expect(dialog.querySelector('img').alt).toMatch(/nhập từ khóa/i)
  const original = screen.getByRole('link', { name: 'Mở ảnh kích thước gốc' })
  expect(original.href).toMatch(/opac-page-3.*\.webp/)
  expect(original.target).toBe('_blank')
  expect(original.rel).toContain('noopener')
  fireEvent.click(screen.getByRole('button', { name: 'Đóng hộp thoại' }))
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(screen.getByText('Mở OPAC và nhập từ khóa để tìm sách.')).toBeTruthy()
})

it('retains the answer and PDF source when an illustration cannot load', () => {
  render(<ChatMessage item={message()} onSpeak={() => {}} />)
  fireEvent.error(screen.getByRole('img', { name: /nhập từ khóa/i }))
  expect(screen.queryByRole('img')).toBeNull()
  expect(screen.getByText(/không tải được ảnh minh họa/i)).toBeTruthy()
  expect(screen.getByText('Mở OPAC và nhập từ khóa để tìm sách.')).toBeTruthy()
  expect(screen.getByRole('link', { name: /Hướng dẫn OPAC của thư viện UTH/ }).href).toBe(`${pdf}#page=3`)
})

it('shows one illustration when the same page is cited twice', () => {
  const item = message()
  item.sources.push({ ...item.sources[0] })
  render(<ChatMessage item={item} onSpeak={() => {}} />)
  expect(screen.getAllByRole('img')).toHaveLength(1)
})

it.each([
  { role: 'user' }, { mode: 'catalog' }, { mode: 'catalog_ai' }, { status: 'not_found' },
  { status: 'clarify' }, { status: 'needs_confirmation' },
  { sources: [{ url: `${pdf}#page=8` }] },
  { sources: [{ url: 'https://example.test/HDSD_TRACUU_OPAC.v1.1.pdf#page=3' }] },
  { sources: [{ url: `${pdf}?redirect=https://example.test/#page=3` }] },
  { sources: [{ url: 'https://opacthuvien.ut.edu.vn@example.test/opac/Upload/HDSD_TRACUU_OPAC.v1.1.pdf#page=3' }] },
  { sources: [{ url: '__proto__' }] },
])('does not add a guide image to unrelated or untrusted message %j', changes => {
  render(<ChatMessage item={message(3, changes)} onSpeak={() => {}} />)
  expect(screen.queryByRole('img')).toBeNull()
  expect(screen.queryByRole('button', { name: /phóng to hình/i })).toBeNull()
})

it('shows the illustration after submitting the actual search starter', async () => {
  fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ ...message(), answer: message().content, conversation_id: null }) })
  render(<ChatWindow user={null} />)
  fireEvent.click(screen.getByRole('button', { name: /Tìm tài liệu/ }))
  expect(await screen.findByRole('img', { name: /nhập từ khóa/i })).toBeTruthy()
  expect(JSON.parse(fetch.mock.calls[0][1].body).message).toBe('Làm thế nào để tra cứu sách tại thư viện?')
})

it('reconstructs illustrations from saved source citations when loading history', async () => {
  fetch.mockResolvedValue({ ok: true, status: 200, json: async () => ({ messages: [{ ...message(), id: 9 }] }) })
  render(<ChatWindow user={{ id: 1 }} conversationId={5} />)
  expect(await screen.findByRole('img', { name: /nhập từ khóa/i })).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Xem trang 3 trong PDF gốc' }).href).toBe(`${pdf}#page=3`)
})
