// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import BookAdmin from './components/BookAdmin.jsx'

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data })
const book = { id: 7, title: 'Nhập môn Python', published: false, source_url: 'https://lic.ut.edu.vn/book/7' }
const preview = { revision: 'a'.repeat(64), source_url: book.source_url, checked_at: '2026-10-28', classification: '005.133', suggestions: [
  { field: 'subjects', value: 'Python; Lập trình', source_field: 'MARC — chủ đề', checked_at: '2026-10-29' },
  { field: 'summary', value: 'Giới thiệu biến và vòng lặp.', source_field: 'MARC — tóm tắt', checked_at: '2026-10-29' },
] }
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(preview)))
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

async function open(onMutate = vi.fn()) {
  render(<BookAdmin rows={{ items: [book], total: 1, page: 1, page_size: 20 }} onMutate={onMutate} />)
  fireEvent.click(screen.getByRole('button', { name: `Gợi ý biên mục ${book.title}` }))
  await screen.findByText('Python; Lập trình')
}

it('requires choosing source suggestions before approving and sends no generated text', async () => {
  const mutate = vi.fn().mockResolvedValue(book)
  await open(mutate)
  expect(fetch.mock.calls[0][0]).toBe('/api/admin/books/7/indexing')
  expect(screen.getByRole('link', { name: 'Đối chiếu nguồn' }).href).toBe(book.source_url)
  expect(screen.getByText(/005.133/)).toBeTruthy()
  expect(screen.getByRole('button', { name: 'Duyệt và ghép vào biểu ghi' }).disabled).toBe(true)
  expect(mutate).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('checkbox', { name: /Từ khóa/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Duyệt và ghép vào biểu ghi' }))
  await waitFor(() => expect(mutate).toHaveBeenCalledWith('books/7/indexing', expect.objectContaining({
    body: { revision: preview.revision, fields: ['subjects'] },
  })))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
})

it('lets staff reload after a stale review without applying again automatically', async () => {
  await open(vi.fn().mockResolvedValue(false))
  fireEvent.click(screen.getByRole('checkbox', { name: /Tóm tắt/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Duyệt và ghép vào biểu ghi' }))
  await screen.findByRole('dialog')
  fetch.mockResolvedValueOnce(response({ ...preview, revision: 'b'.repeat(64), suggestions: [] }))
  fireEvent.click(screen.getByRole('button', { name: 'Đọc lại nguồn' }))
  await screen.findByText('Chưa có gợi ý mới từ nguồn')
  expect(screen.queryByRole('checkbox')).toBeNull()
})

it('shows source load failures and permits retry', async () => {
  fetch.mockResolvedValueOnce(response({ detail: 'Không tìm thấy biểu ghi.' }, 404))
  render(<BookAdmin rows={{ items: [book], total: 1, page: 1, page_size: 20 }} />)
  fireEvent.click(screen.getByRole('button', { name: `Gợi ý biên mục ${book.title}` }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Không tìm thấy biểu ghi.')
  fireEvent.click(screen.getByRole('button', { name: 'Đọc lại nguồn' }))
  await screen.findByText('Python; Lập trình')
})

it('sends the version of the opened book when saving an edited form', async () => {
  const mutate = vi.fn().mockResolvedValue(false)
  render(<BookAdmin rows={{ items: [{ ...book, checked_at: '2026-10-28', revision: 'c'.repeat(64) }], total: 1, page: 1, page_size: 20 }} onMutate={mutate} />)
  fireEvent.click(screen.getByRole('button', { name: `Sửa tài liệu ${book.title}` }))
  fireEvent.change(screen.getByLabelText('Nhan đề'), { target: { value: 'Nhan đề đã sửa' } })
  fireEvent.click(screen.getByRole('button', { name: 'Lưu tài liệu' }))
  await waitFor(() => expect(mutate).toHaveBeenCalledWith('books/7', expect.objectContaining({
    method: 'PUT', body: expect.objectContaining({ title: 'Nhan đề đã sửa', revision: 'c'.repeat(64) }),
  })))
})
