import { useCallback, useEffect, useState } from 'react'
import {
  fetchBookmarks,
  addBookmark,
  removeBookmark,
  checkBookmark,
  fetchCollections,
  createCollection,
  deleteCollection,
  type Bookmark,
  type Collection,
} from '@/lib/api'

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [bookmarkedSet, setBookmarkedSet] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [bms, cols] = await Promise.all([fetchBookmarks(), fetchCollections()])
      setBookmarks(bms)
      setCollections(cols)
      setBookmarkedSet(new Set(bms.map((b) => `${b.briefing_date}:${b.article_number}`)))
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const isBookmarked = useCallback(
    (date: string, num: number) => bookmarkedSet.has(`${date}:${num}`),
    [bookmarkedSet],
  )

  const toggle = useCallback(async (date: string, num: number) => {
    const key = `${date}:${num}`
    if (bookmarkedSet.has(key)) {
      await removeBookmark(date, num)
      setBookmarkedSet((s) => { const n = new Set(s); n.delete(key); return n })
      setBookmarks((bms) => bms.filter((b) => !(b.briefing_date === date && b.article_number === num)))
    } else {
      await addBookmark(date, num)
      setBookmarkedSet((s) => new Set(s).add(key))
      await load()
    }
  }, [bookmarkedSet, load])

  const addCollection = useCallback(async (name: string) => {
    await createCollection(name)
    await load()
  }, [load])

  const removeCollection = useCallback(async (id: number) => {
    await deleteCollection(id)
    await load()
  }, [load])

  return { bookmarks, collections, loading, isBookmarked, toggle, addCollection, removeCollection, refresh: load }
}
