import { useEffect, useState } from 'react'
import type { BriefingDetail } from '@/types'
import { fetchBriefing } from '@/lib/api'

export interface ConceptDiff {
  shared: string[]
  onlyLeft: string[]
  onlyRight: string[]
}

function extractConcepts(detail: BriefingDetail): Set<string> {
  const concepts = new Set<string>()
  for (const a of detail.articles) {
    for (const c of a.key_concepts) concepts.add(c.toLowerCase())
  }
  return concepts
}

export function useCompare(dateLeft: string | null, dateRight: string | null) {
  const [left, setLeft] = useState<BriefingDetail | null>(null)
  const [right, setRight] = useState<BriefingDetail | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!dateLeft) { setLeft(null); return }
    setLoading(true)
    fetchBriefing(dateLeft).then(setLeft).catch(() => setLeft(null)).finally(() => setLoading(false))
  }, [dateLeft])

  useEffect(() => {
    if (!dateRight) { setRight(null); return }
    setLoading(true)
    fetchBriefing(dateRight).then(setRight).catch(() => setRight(null)).finally(() => setLoading(false))
  }, [dateRight])

  const diff: ConceptDiff | null = left && right ? computeDiff(left, right) : null

  return { left, right, diff, loading }
}

function computeDiff(left: BriefingDetail, right: BriefingDetail): ConceptDiff {
  const lConcepts = extractConcepts(left)
  const rConcepts = extractConcepts(right)

  const shared: string[] = []
  const onlyLeft: string[] = []
  const onlyRight: string[] = []

  for (const c of lConcepts) {
    if (rConcepts.has(c)) shared.push(c)
    else onlyLeft.push(c)
  }
  for (const c of rConcepts) {
    if (!lConcepts.has(c)) onlyRight.push(c)
  }

  return { shared: shared.sort(), onlyLeft: onlyLeft.sort(), onlyRight: onlyRight.sort() }
}
