// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import App from './App.jsx'

const reply = value => ({ ok: true, status: 200, json: async () => value })
const book = { id: 2, title: 'Cơ sở dữ liệu thực hành', available: 1, reserved: false }

beforeEach(() => {
  location.hash = 'demo-library'
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
  Element.prototype.scrollIntoView = vi.fn()
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); location.hash = '' })

it('lets a signed-in reader confirm a reservation and see it in the sample library', async () => {
  const fetcher = vi.fn(async (url, options) => {
    if (url === '/health') return reply({ capabilities: { demo_reservations: true } })
    if (url === '/api/auth/me') return reply({ user: { id: 1, name: 'Bạn đọc thử', role: 'reader' } })
    if (url === '/api/conversations') return reply([])
    if (url === '/api/demo/reservations') return reply({ books: [book] })
    if (url === '/api/demo/reservations/2' && options.method === 'PUT') {
      return reply({ books: [{ ...book, available: 0, reserved: true }] })
    }
    throw new Error(`Unexpected request ${url}`)
  })
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: /đăng ký mượn cơ sở dữ liệu/i }))
  expect(screen.getByRole('dialog', { name: 'Xác nhận đăng ký giả lập' })).toBeTruthy()
  expect(fetcher.mock.calls.some(([, options]) => options.method === 'PUT')).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận đăng ký' }))
  expect(await screen.findByText('Bạn đã đăng ký')).toBeTruthy()
  expect(screen.getByRole('button', { name: /hủy đăng ký cơ sở dữ liệu/i })).toBeTruthy()
})

it('lets a reader receive, renew and return a sample loan with confirmation', async () => {
  const initial = { ...book, available: 0, reserved: true }
  const fetcher = vi.fn(async (url, options) => {
    if (url === '/health') return reply({ capabilities: { demo_reservations: true } })
    if (url === '/api/auth/me') return reply({ user: { id: 1, name: 'Bạn đọc thử', role: 'reader' } })
    if (url === '/api/conversations') return reply([])
    if (url === '/api/demo/reservations') return reply({ books: [initial] })
    if (options.method === 'POST' && url.endsWith('/checkout')) return reply({ books: [{ ...initial, due_date: '2026-11-21' }] })
    if (options.method === 'POST' && url.endsWith('/renew')) return reply({ books: [{ ...initial, due_date: '2026-11-28', renewed: true }] })
    if (options.method === 'POST' && url.endsWith('/return')) return reply({ books: [book] })
    throw new Error(`Unexpected request ${url}`)
  })
  vi.stubGlobal('fetch', fetcher)
  render(<App />)
  fireEvent.click(await screen.findByRole('button', { name: /nhận sách cơ sở dữ liệu/i }))
  expect(fetcher.mock.calls.some(([url]) => url.endsWith('/checkout'))).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận nhận sách' }))
  expect(await screen.findByText(/21\/11\/2026/)).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: /gia hạn cơ sở dữ liệu/i }))
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận gia hạn' }))
  expect(await screen.findByText(/28\/11\/2026/)).toBeTruthy()
  expect(screen.getByRole('button', { name: /gia hạn cơ sở dữ liệu/i }).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: /trả sách cơ sở dữ liệu/i }))
  fireEvent.click(screen.getByRole('button', { name: 'Xác nhận trả sách' }))
  expect(await screen.findByRole('button', { name: /đăng ký mượn cơ sở dữ liệu/i })).toBeTruthy()
})

it('offers the sample circulation from the unavailable real loans page only in demo mode', async () => {
  location.hash = 'loans'
  vi.stubGlobal('fetch', vi.fn(async url => {
    if (url === '/health') return reply({ capabilities: { demo_reservations: true, library_loans_configured: false } })
    if (url === '/api/auth/me') return { ok: false, status: 401, json: async () => ({ detail: 'Vui lòng đăng nhập.' }) }
    throw new Error(`Unexpected request ${url}`)
  }))
  render(<App />)
  expect((await screen.findByRole('link', { name: 'Thử mượn sách mẫu' })).getAttribute('href')).toBe('#demo-library')
  expect(screen.queryByLabelText('Mã truy cập thư viện')).toBeNull()
})
