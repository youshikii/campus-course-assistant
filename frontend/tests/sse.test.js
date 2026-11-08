import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readSSE } from '../src/utils/sse.js'

function streamChunks(chunks) {
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(chunk))
      controller.close()
    }
  })
}

test('SSE handles arbitrary byte boundaries, Chinese Unicode, CRLF and heartbeats', async () => {
  const bytes = new TextEncoder().encode(
    ': heartbeat\r\n\r\nevent: token\r\ndata: {"text":"你好，课程"}\r\n\r\nevent: done\r\ndata: {"success":true}\r\n\r\n'
  )
  const events = []
  await readSSE(streamChunks(Array.from(bytes, (byte) => Uint8Array.of(byte))), (name, data) =>
    events.push([name, data])
  )
  assert.deepEqual(events, [
    ['token', { text: '你好，课程' }],
    ['done', { success: true }]
  ])
})

test('SSE handles multi-line data and a final frame without blank line', async () => {
  const text =
    'event: sources\ndata: {"sources":\ndata: []}\n\nevent: done\ndata: {"success":false}'
  const events = []
  await readSSE(streamChunks([new TextEncoder().encode(text)]), (name, data) =>
    events.push([name, data])
  )
  assert.deepEqual(events, [
    ['sources', { sources: [] }],
    ['done', { success: false }]
  ])
})

test('malformed SSE data fails instead of silently losing messages', async () => {
  await assert.rejects(
    readSSE(streamChunks([new TextEncoder().encode('data: broken\n\n')]), () => {}),
    SyntaxError
  )
})
