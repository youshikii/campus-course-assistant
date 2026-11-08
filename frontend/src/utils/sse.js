// POST + fetch carries the JWT header; native EventSource only supports GET.
export async function readSSE(body, onEvent) {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const dispatch = (block) => {
    let name = 'message'
    const lines = []
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) name = line.slice(6).trim()
      if (line.startsWith('data:')) lines.push(line.slice(5).replace(/^ /, ''))
    }
    if (lines.length) onEvent(name, JSON.parse(lines.join('\n')))
  }
  try {
    while (true) {
      const { value, done } = await reader.read()
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true })
      // Keep an incomplete CRLF intact between reads.
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary
      while ((boundary = buffer.indexOf('\n\n')) >= 0) {
        dispatch(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
      }
      if (done) {
        if (buffer.trim()) dispatch(buffer)
        break
      }
    }
  } finally {
    await reader.cancel().catch(() => {})
    reader.releaseLock()
  }
}
