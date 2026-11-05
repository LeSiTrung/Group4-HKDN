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
