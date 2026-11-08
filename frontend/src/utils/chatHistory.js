// Preserve whole successful Q/A pairs, within the backend's context limits.
export function successfulHistory(turns, question = '') {
  const pairs = []
  let size = question.length
  for (const turn of [...turns].reverse()) {
    if (turn.status !== 'success' || !turn.question?.trim() || !turn.answer?.trim()) continue
    if (turn.question.length > 6000 || turn.answer.length > 6000) continue
    const pairSize = turn.question.length + turn.answer.length
    if (size + pairSize > 60000 || pairs.length === 10) break
    size += pairSize
    pairs.unshift([
      { role: 'user', content: turn.question },
      { role: 'assistant', content: turn.answer }
    ])
  }
  return pairs.flat()
}
