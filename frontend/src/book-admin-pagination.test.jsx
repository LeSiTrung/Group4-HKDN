// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import Admin from './components/Admin.jsx'

const response = value => ({ ok: true, status: 200, json: async () => value })
const books = Array.from({ length: 45 }, (_, index) => ({ id: index + 1, title: `Tài liệu ${index + 1}`, author: 'Tác giả', subjects: 'Chủ đề', kind: 'digital', source_url: 'https://thuvienso.ut.edu.vn/', checked_at: '2026-10-31', published: index !== 0 }))
let records
beforeEach(() => {
  records = [...books]
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
  vi.stubGlobal('fetch', vi.fn(async (url, options) => {
    if (!url.includes('/admin/books')) return response([])
    if (options?.method === 'DELETE') { records = records.filter(book => !url.endsWith(`/${book.id}`)); return response({ ok: true }) }
    const params = new URL(url, 'http://localhost').searchParams
    const filtered = records.filter(book => book.title.includes(params.get('q') || ''))
    const page = Math.min(Number(params.get('page') || 1), Math.max(1, Math.ceil(filtered.length / 20)))
    return response({ items: filtered.slice((page - 1) * 20, page * 20), total: filtered.length, page, page_size: 20 })
  }))
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

async function openBooks() {
  render(<Admin user={{ id: 1 }} />)
  fireEvent.click(screen.getByRole('tab', { name: 'Danh mục' }))
  await screen.findByText('Trang 1 / 3')
}

it('fetches only displayed pages and keeps submitted search when input changes', async () => {
  await openBooks()
  expect(fetch.mock.calls.at(-1)[0]).toBe('/api/admin/books?page=1&page_size=20')
  expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(20)
  expect(screen.getByText('Bản nháp')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Tìm trong danh mục quản trị'), { target: { value: 'Tài liệu' } })
  fireEvent.click(screen.getByRole('button', { name: 'Tìm danh mục' }))
  await waitFor(() => expect(fetch.mock.calls.at(-1)[0]).toContain('q=T%C3%A0i+li%E1%BB%87u'))
  await screen.findByText('Trang 1 / 3')
  fireEvent.change(screen.getByLabelText('Tìm trong danh mục quản trị'), { target: { value: 'chưa gửi' } })
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByRole('heading', { name: 'Tài liệu 21' })
  expect(fetch.mock.calls.at(-1)[0]).toBe('/api/admin/books?page=2&page_size=20&q=T%C3%A0i+li%E1%BB%87u')
  expect(screen.queryByRole('heading', { name: 'Tài liệu 1', exact: true })).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Tìm danh mục' }))
  await screen.findByText('Chưa có biểu ghi phù hợp')
  expect(fetch.mock.calls.at(-1)[0]).toContain('page=1')
})

it('uses the clamped server page after deletion and keeps filters on refresh', async () => {
  await openBooks()
  fireEvent.change(screen.getByLabelText('Tìm trong danh mục quản trị'), { target: { value: 'Tài liệu' } })
  fireEvent.click(screen.getByRole('button', { name: 'Tìm danh mục' }))
  await waitFor(() => expect(fetch.mock.calls.at(-1)[0]).toContain('q='))
  await screen.findByText('Trang 1 / 3')
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 2 / 3')
  fireEvent.click(screen.getByRole('button', { name: 'Trang sau' }))
  await screen.findByText('Trang 3 / 3')
  records = records.slice(0, 41)
  fireEvent.click(screen.getByRole('button', { name: 'Xóa tài liệu Tài liệu 41' }))
  fireEvent.click(screen.getByRole('button', { name: 'Xóa biểu ghi', exact: true }))
  await screen.findByText('Trang 2 / 2')
  expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(20)
  fireEvent.click(screen.getByRole('button', { name: 'Trang trước' }))
  await screen.findByText('Trang 1 / 2')
  expect(screen.getByRole('heading', { name: 'Tài liệu 1', exact: true })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Làm mới' }))
  await waitFor(() => expect(fetch.mock.calls.at(-1)[0]).toBe('/api/admin/books?page=1&page_size=20&q=T%C3%A0i+li%E1%BB%87u'))
})
