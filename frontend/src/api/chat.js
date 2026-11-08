import { getToken, logout } from '@/utils/auth'
import router from '@/router'
import { readSSE } from '@/utils/sse'

export async function streamChat(sessionId, message, signal, onEvent) {
  return postStream(`/api/chat/sessions/${sessionId}/stream`, { message }, signal, onEvent)
}

export async function streamQuestion(question, history, signal, onEvent) {
  return postStream(
    '/api/chat/stream',
    { question, history },
    signal,
    onEvent,
    '连接已中断，本轮回答未完成，请重试'
  )
}

async function postStream(
  path,
  body,
  signal,
  onEvent,
  incompleteMessage = '连接已中断，请重新打开会话检查结果后再试'
) {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || ''}${path}`, {
    method: 'POST',
    signal,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${getToken()}`
    },
    body: JSON.stringify(body)
  })
  if (!response.ok) {
    if (response.status === 401) {
      logout()
      router.push('/login')
    }
    const error = await response.json().catch(() => ({}))
    throw new Error(error.message || '无法连接智能助手')
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('服务器未返回流式回答，请检查服务配置')
  }
  let completed = null
  await readSSE(response.body, (name, payload) => {
    if (name === 'done') completed = payload
    if (name === 'error' && payload.code === 401) {
      logout()
      router.push('/login')
    }
    onEvent(name, payload)
  })
  if (!completed) throw new Error(incompleteMessage)
  return completed
}
