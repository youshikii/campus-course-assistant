import { test } from 'node:test'
import assert from 'node:assert/strict'
import { successfulHistory } from '../src/utils/chatHistory.js'

test('only complete successful turns become follow-up history', () => {
  const turns = ['success', 'error', 'stopped', 'running'].map((status) => ({
    status,
    question: `问题-${status}`,
    answer: `回答-${status}`
  }))
  assert.deepEqual(successfulHistory(turns), [
    { role: 'user', content: '问题-success' },
    { role: 'assistant', content: '回答-success' }
  ])
  assert.deepEqual(successfulHistory([{ status: 'success', question: 'x', answer: '' }]), [])
})

test('history keeps the latest ten whole pairs in original order', () => {
  const turns = Array.from({ length: 13 }, (_, i) => ({
    status: 'success',
    question: `q${i}`,
    answer: `a${i}`
  }))
  const history = successfulHistory(turns)
  assert.equal(history.length, 20)
  assert.equal(history[0].content, 'q3')
  assert.equal(history.at(-1).content, 'a12')
})

test('history respects per-message and total context limits including the new question', () => {
  const turns = Array.from({ length: 10 }, () => ({
    status: 'success',
    question: 'q'.repeat(6000),
    answer: 'a'.repeat(6000)
  }))
  const history = successfulHistory(turns, 'x'.repeat(6000))
  assert.equal(history.length, 8)
  assert.ok(history.reduce((sum, message) => sum + message.content.length, 6000) <= 60000)
  assert.deepEqual(
    successfulHistory([{ status: 'success', question: 'q', answer: 'a'.repeat(6001) }]),
    []
  )
})
