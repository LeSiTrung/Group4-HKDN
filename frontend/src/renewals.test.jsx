// @vitest-environment jsdom
import React from 'react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import RenewalAdmin from './components/RenewalAdmin.jsx'

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(cleanup)
const row = { idempotency_key: 'test-renewal-key', user_id: 5, loan_id: 'loan-5', state: 'uncertain', result: null }

it('never preselects successful reconciliation and requires an operator reference', async () => {
  const mutate = vi.fn().mockResolvedValue({ ok: true })
  render(<RenewalAdmin rows={[row]} onMutate={mutate} />)
  fireEvent.click(screen.getByRole('button', { name: 'Đối soát' }))
  const state = screen.getByLabelText('Kết quả đã xác nhận')
  expect(state.value).toBe('')
  expect(screen.getByLabelText('Hạn trả được thư viện xác nhận').disabled).toBe(true)
  fireEvent.change(state, { target: { value: 'failed' } })
  fireEvent.change(screen.getByLabelText('Tham chiếu đối soát'), { target: { value: 'Xác nhận thử từ đầu mối thư viện' } })
  fireEvent.click(screen.getByRole('checkbox', { name: /Tôi đã kiểm tra/ }))
  fireEvent.click(screen.getByRole('button', { name: 'Ghi nhận kết quả đối soát' }))
  await waitFor(() => expect(mutate).toHaveBeenCalled())
  expect(mutate).toHaveBeenCalledWith('renewals/test-renewal-key/reconcile', expect.objectContaining({ body: { state: 'failed', confirmation: true, reference: 'Xác nhận thử từ đầu mối thư viện' } }))
})

it('requires the actual new due date only for confirmed successful renewals', () => {
  render(<RenewalAdmin rows={[row]} onMutate={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Đối soát' }))
  fireEvent.change(screen.getByLabelText('Kết quả đã xác nhận'), { target: { value: 'succeeded' } })
  expect(screen.getByLabelText('Hạn trả được thư viện xác nhận').required).toBe(true)
  expect(screen.getByLabelText('Hạn trả được thư viện xác nhận').disabled).toBe(false)
})

it('offers no reconciliation action on already resolved renewals', () => {
  render(<RenewalAdmin rows={[{ ...row, state: 'succeeded', result: { due_date: '2026-11-01' } }]} onMutate={vi.fn()} />)
  expect(screen.queryByRole('button', { name: 'Đối soát' })).toBeNull()
})
