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
  const [prevLeft, setPrevLeft] = useState<string | null>(dateLeft)
  const [prevRight, setPrevRight] = useState<string | null>(dateRight)

  if (dateLeft !== prevLeft) {
    setPrevLeft(dateLeft)
    if (!dateLeft) setLeft(null)
    else setLoading(true)
  }
  if (dateRight !== prevRight) {
    setPrevRight(dateRight)
    if (!dateRight) setRight(null)
    else setLoading(true)
  }

  useEffect(() => {
    if (!dateLeft) return
    fetchBriefing(dateLeft).then(setLeft).catch(() => setLeft(null)).finally(() => setLoading(false))
  }, [dateLeft])

  useEffect(() => {
    if (!dateRight) return
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
