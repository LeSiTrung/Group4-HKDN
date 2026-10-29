// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import ChatWindow from './components/ChatWindow.jsx'

const response = value => ({ ok: true, status: 200, json: async () => value })
const answer = { answer: 'Bạn có thể tra cứu tài liệu trên mục lục thư viện.', status: 'answered', mode: 'faq', sources: [], books: [], suggestions: [], conversation_id: null }
function send(text) {
  fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: text } })
  fireEvent.submit(screen.getByRole('form', { name: 'Gửi câu hỏi' }))
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(answer)))
  Element.prototype.scrollIntoView = vi.fn()
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it('accepts and sends a complete 6,000-character question without a composer character cap', async () => {
  render(<ChatWindow user={null} />)
  const question = `  ${'Tìm sách '.repeat(750)}  `
  const input = screen.getByLabelText('Câu hỏi của bạn')
  expect(input.hasAttribute('maxlength')).toBe(false)
  send(question)
  await screen.findByText(answer.answer)
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ message: question })
  expect(document.querySelector('.user-message .message-content').textContent).toBe(question)
  expect(input.value).toBe('')
})

it('appends the complete voice transcript to an existing long draft', async () => {
  let recognition
  vi.stubGlobal('SpeechRecognition', class {
    constructor() { recognition = this }
    start() {}
    abort() {}
  })
  render(<ChatWindow user={null} />)
  const draft = 'Nội dung đang viết '.repeat(200)
  const transcript = 'phần nhận dạng giọng nói '.repeat(150)
  fireEvent.change(screen.getByLabelText('Câu hỏi của bạn'), { target: { value: draft } })
  fireEvent.click(screen.getByRole('button', { name: 'Nhập bằng giọng nói' }))
  act(() => recognition.onresult({ results: [[{ transcript }]] }))
  expect(screen.getByLabelText('Câu hỏi của bạn').value).toBe(`${draft} ${transcript}`)
  expect(fetch).not.toHaveBeenCalled()
})

it('introduces library assistance and invites library questions in the composer', () => {
  render(<ChatWindow user={null} />)
  expect(screen.getByText(/Tra cứu tài liệu, tìm hiểu dịch vụ và nhận hướng dẫn/).textContent).toContain('thư viện UTH')
  expect(screen.getByLabelText('Câu hỏi của bạn').placeholder).toMatch(/tài liệu, dịch vụ thư viện/)
  expect(screen.queryByRole('button', { name: /Cùng tìm hiểu/ })).toBeNull()
  expect(fetch).not.toHaveBeenCalled()
})

it('offers a digital-library starter that submits a library question', async () => {
  render(<ChatWindow user={null} />)
  fireEvent.click(screen.getByRole('button', { name: /Thư viện số/ }))
  await screen.findByText(answer.answer)
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ message: 'Làm thế nào để truy cập tài liệu điện tử?' })
  expect(screen.queryByText('Kiến thức chung (AI)')).toBeNull()
  expect(screen.queryByText('NGUỒN THAM KHẢO')).toBeNull()
})

it('sends six plain guest context excerpts with explicit markers while preserving full visible messages', async () => {
  const longQuestion = 'Tìm sách về Python '.repeat(350)
  const longAnswer = 'Nội dung chi tiết '.repeat(400)
  fetch.mockResolvedValueOnce(response({ ...answer, answer: 'Lượt cũ.' }))
    .mockResolvedValueOnce(response({ ...answer, answer: longAnswer, mode: 'faq', sources: [{ title: 'Nguồn đã đối chiếu', url: 'https://lic.uth.edu.vn/', checked_at: '2026-10-29' }], books: [{ id: 8, title: 'Biểu ghi thật', url: 'https://lic.uth.edu.vn/book/8' }] }))
    .mockResolvedValueOnce(response({ ...answer, answer: 'Lượt ba.' }))
    .mockResolvedValueOnce(response({ ...answer, answer: 'Lượt bốn.' }))
  render(<ChatWindow user={null} />)
  for (const [question, reply] of [['Câu hỏi cũ', 'Lượt cũ.'], [longQuestion, longAnswer], ['Câu hỏi ba', 'Lượt ba.'], ['Câu hỏi bốn', 'Lượt bốn.']]) {
    send(question)
    await screen.findByText(reply.trim())
  }
  send('Câu hỏi tiếp nối')
  await screen.findByText(answer.answer)
  const payload = JSON.parse(fetch.mock.calls[4][1].body)
  expect(payload.message).toBe('Câu hỏi tiếp nối')
  expect(payload.history).toHaveLength(6)
  for (const item of payload.history) expect(Object.keys(item).sort()).toEqual(['content', 'role'])
  expect(payload.history[0].role).toBe('user')
  expect(payload.history[1].role).toBe('assistant')
  for (const item of payload.history.slice(0, 2)) {
    expect(item.content.length).toBeLessThanOrEqual(2000)
    expect(item.content).toMatch(/\[Trích đoạn ngữ cảnh; phần còn lại không được gửi\.\]$/)
  }
  expect(payload.history.slice(2)).toEqual([{ role: 'user', content: 'Câu hỏi ba' }, { role: 'assistant', content: 'Lượt ba.' }, { role: 'user', content: 'Câu hỏi bốn' }, { role: 'assistant', content: 'Lượt bốn.' }])
  expect([...document.querySelectorAll('.message-content')].map(node => node.textContent)).toContain(longQuestion)
  expect([...document.querySelectorAll('.message-content')].map(node => node.textContent)).toContain(longAnswer)
  expect(screen.getByRole('link', { name: /Nguồn đã đối chiếu/ })).toBeTruthy()
  expect(screen.getByRole('link', { name: 'Biểu ghi thật' })).toBeTruthy()
  expect(payload.conversation_id).toBeUndefined()
})

it('uses saved authenticated history without uploading it as guest context', async () => {
  const saved = 'Nội dung đã lưu '.repeat(400)
  fetch.mockResolvedValueOnce(response({ messages: [{ role: 'user', content: saved }, { id: 17, role: 'assistant', content: 'Câu trả lời đã lưu.', mode: 'faq', status: 'answered', sources: [], books: [] }] }))
    .mockResolvedValueOnce(response({ ...answer, conversation_id: 12, message_id: 18 }))
  render(<ChatWindow user={{ id: 3, name: 'Bạn đọc' }} conversationId={12} />)
  await screen.findByText('Câu trả lời đã lưu.')
  send('Hỏi tiếp tự nhiên')
  await screen.findByText(answer.answer)
  expect(fetch.mock.calls[0][0]).toBe('/api/conversations/12')
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ message: 'Hỏi tiếp tự nhiên', conversation_id: 12 })
  expect(document.querySelector('.user-message .message-content').textContent).toBe(saved)
  expect(fetch.mock.calls[1][1]).toMatchObject({ credentials: 'include', headers: { 'X-Requested-With': 'LibraryAssistant', 'Content-Type': 'application/json' } })
})
