// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import App from './App.jsx'

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async url => ({ ok: true, status: 200, json: async () => url.endsWith('/auth/me') ? { user: null } : {} })))
  vi.stubGlobal('matchMedia', () => ({ matches: true, addEventListener() {}, removeEventListener() {} }))
  Element.prototype.scrollIntoView = vi.fn()
  location.hash = '#chat'
  const focus = HTMLElement.prototype.focus
  // jsdom needs the browser's inert focus restriction to reproduce this regression.
  vi.spyOn(HTMLElement.prototype, 'focus').mockImplementation(function (...args) {
    if (!this.closest('[inert]')) focus.apply(this, args)
  })
})
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

it.each(['Escape', 'close button', 'backdrop', 'navigation'])('restores focus after closing mobile navigation via %s', async method => {
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }).disabled).toBe(false))
  const trigger = screen.getByRole('button', { name: 'Mở điều hướng' })
  trigger.focus()
  fireEvent.click(trigger)
  const drawer = screen.getByRole('dialog', { name: 'Điều hướng thư viện' })
  const close = within(drawer).getByRole('button', { name: 'Đóng điều hướng' })
  expect(document.activeElement).toBe(close)
  expect(trigger.closest('[inert]')).toBeTruthy()

  if (method === 'Escape') fireEvent.keyDown(window, { key: 'Escape' })
  else if (method === 'close button') fireEvent.click(close)
  else if (method === 'backdrop') fireEvent.click(document.querySelector('.sidebar-backdrop'))
  else fireEvent.click(within(drawer).getByRole('link', { name: 'Tra cứu tài liệu' }))

  expect(trigger.getAttribute('aria-expanded')).toBe('false')
  expect(trigger.closest('[inert]')).toBeNull()
  expect(document.activeElement).toBe(trigger)
})

it('keeps Tab and Shift+Tab inside the mobile drawer', async () => {
  render(<App />)
  await waitFor(() => expect(screen.getByRole('button', { name: /Đăng nhập \/ Đăng ký/ }).disabled).toBe(false))
  fireEvent.click(screen.getByRole('button', { name: 'Mở điều hướng' }))
  const drawer = screen.getByRole('dialog', { name: 'Điều hướng thư viện' })
  const first = within(drawer).getByRole('button', { name: 'Đóng điều hướng' })
  const last = within(drawer).getByRole('button', { name: /Đăng nhập \/ Đăng ký/ })
  fireEvent.keyDown(window, { key: 'Tab', shiftKey: true })
  expect(document.activeElement).toBe(last)
  fireEvent.keyDown(window, { key: 'Tab' })
  expect(document.activeElement).toBe(first)
})
