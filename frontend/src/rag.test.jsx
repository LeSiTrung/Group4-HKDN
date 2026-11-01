// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import Admin from './components/Admin.jsx'
import { api } from './services/chatApi.js'

vi.mock('./services/chatApi.js', async importOriginal => ({ ...await importOriginal(), api: vi.fn() }))
const model = { provider: 'ollama', model: 'local-model', configured: true, ready: true, reachable: true, model_available: true, error: null, check: 'model_catalog' }
const source = { id: 1, question: 'Quy định mượn sách', source_url: 'https://lic.uth.edu.vn/', checked_at: '2026-10-30', score: 0.75, excerpts: ['<img src=x onerror=alert(1)>'] }
beforeEach(() => api.mockImplementation(async path => path === '/admin/status' ? { llm: { configured: true } } : []))
afterEach(() => { cleanup(); vi.resetAllMocks() })

async function openStatus() {
  render(<Admin user={{ id: 1 }} />)
  fireEvent.click(screen.getByRole('tab', { name: 'Hệ thống' }))
  await screen.findByRole('button', { name: 'Kiểm tra mô hình' })
}
async function preview() {
  fireEvent.change(screen.getByLabelText('Câu hỏi kiểm tra truy xuất'), { target: { value: 'mượn sách' } })
  fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra truy xuất' }))
}

it('checks installed model explicitly and labels the result as catalog connectivity, without claiming inference', async () => {
  await openStatus()
  expect(api).not.toHaveBeenCalledWith('/admin/ai/check', expect.anything())
  api.mockResolvedValueOnce(model)
  fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra mô hình' }))
  expect(await screen.findByText('Mô hình đã có trên máy chủ')).toBeTruthy()
  expect(screen.getByText(/chưa xác minh khả năng sinh câu trả lời/)).toBeTruthy()
  expect(screen.getByText(/ollama · local-model/)).toBeTruthy()
  expect(api).toHaveBeenCalledWith('/admin/ai/check', { method: 'POST' })
})

it.each([
  [{ configured: false, ready: false, reachable: false, model_available: false }, 'Chưa cấu hình mô hình.'],
  [{ ready: false, reachable: false, model_available: false }, 'Chưa kết nối được máy chủ mô hình.'],
  [{ ready: false, model_available: false }, 'Chưa tìm thấy mô hình đã cấu hình trên máy chủ.'],
])('shows readiness accurately for %j', async (status, message) => {
  await openStatus()
  api.mockResolvedValueOnce({ ...model, ...status })
  fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra mô hình' }))
  expect(await screen.findByText(message)).toBeTruthy()
  expect(screen.queryByText('Mô hình đã có trên máy chủ')).toBeNull()
})

it('renders selected evidence as plain text, safe source links and retrieval metadata', async () => {
  await openStatus()
  api.mockResolvedValueOnce({ method: 'hybrid', degraded: false, sources: [source, { ...source, id: 2, source_url: 'javascript:alert(1)', question: 'Unsafe source' }] })
  await preview()
  expect(await screen.findByText('Quy định mượn sách')).toBeTruthy()
  expect(screen.getAllByText(source.excerpts[0])).toHaveLength(2)
  expect(document.querySelector('img, script')).toBeNull()
  expect(screen.getByRole('link', { name: 'Nguồn: Quy định mượn sách' }).getAttribute('href')).toBe(source.source_url)
  expect(screen.queryByRole('link', { name: 'Nguồn: Unsafe source' })).toBeNull()
  expect(screen.getByText(/Phương thức: hybrid/)).toBeTruthy()
  expect(api).toHaveBeenCalledWith('/admin/retrieval', { method: 'POST', body: { query: 'mượn sách' } })
  expect(screen.getByLabelText('Câu hỏi kiểm tra truy xuất').maxLength).toBe(1000)
})

it('shows empty/degraded retrieval and clears old results when the query changes or status tab is left', async () => {
  await openStatus()
  api.mockResolvedValueOnce({ method: 'lexical', degraded: true, sources: [] })
  await preview()
  expect(await screen.findByText('Không có nguồn phù hợp')).toBeTruthy()
  expect(screen.getByText(/Truy xuất đang dùng chế độ dự phòng/)).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Câu hỏi kiểm tra truy xuất'), { target: { value: 'giờ mở cửa' } })
  expect(screen.queryByText('Không có nguồn phù hợp')).toBeNull()
  api.mockResolvedValueOnce(model)
  fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra mô hình' }))
  await screen.findByText('Mô hình đã có trên máy chủ')
  fireEvent.click(screen.getByRole('tab', { name: 'Kho tri thức' }))
  fireEvent.click(screen.getByRole('tab', { name: 'Hệ thống' }))
  await screen.findByRole('button', { name: 'Kiểm tra mô hình' })
  expect(screen.queryByText('Mô hình đã có trên máy chủ')).toBeNull()
})

it('clears prior model/preview results on failed checks and permits retry', async () => {
  await openStatus()
  api.mockResolvedValueOnce(model)
  fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra mô hình' }))
  await screen.findByText('Mô hình đã có trên máy chủ')
  api.mockRejectedValueOnce(new Error('Model check unavailable'))
  fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra mô hình' }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Model check unavailable')
  expect(screen.queryByText('Mô hình đã có trên máy chủ')).toBeNull()
  api.mockResolvedValueOnce({ method: 'hybrid', degraded: false, sources: [source] })
  await preview()
  await screen.findByText(source.question)
  api.mockRejectedValueOnce(new Error('Retrieval unavailable'))
  fireEvent.click(screen.getByRole('button', { name: 'Kiểm tra truy xuất' }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Retrieval unavailable')
  expect(screen.queryByText(source.question)).toBeNull()
  expect(screen.getByRole('button', { name: 'Kiểm tra truy xuất' }).disabled).toBe(false)
})
