const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

export async function api(path, { body, ...options } = {}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 90000)
  try {
    const response = await fetch(`${API_BASE_URL}${path === '/health' ? '' : '/api'}${path}`, {
      ...options,
      signal: options.signal || controller.signal,
      credentials: 'include',
      headers: { 'X-Requested-With': 'D7', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    const data = response.status === 204 ? null : await response.json().catch(() => null)
    if (!response.ok) {
      const detail = data?.detail
      const error = new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map(item => item.msg).join('. ') : `Yêu cầu chưa thực hiện được (${response.status}).`)
      error.status = response.status
      error.search_url = data?.search_url
      throw error
    }
    if (data === null && response.status !== 204) throw new Error('Máy chủ trả về dữ liệu không hợp lệ. Vui lòng thử lại.')
    return data
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('Máy chủ chưa phản hồi kịp. Hãy kiểm tra trạng thái trước khi gửi lại thao tác.')
    if (error instanceof TypeError) throw new Error('Không thể kết nối máy chủ. Câu hỏi của bạn vẫn được giữ lại.')
    throw error
  } finally { clearTimeout(timeout) }
}

export function safeUrl(value) {
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined
  } catch { return undefined }
}

export const sendMessage = (message, conversationId, history) => api('/chat', { method: 'POST', body: { message, ...(conversationId ? { conversation_id: conversationId } : {}), ...(history?.length ? { history } : {}) } })
