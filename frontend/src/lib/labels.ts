/**
 * Human-language copy (design-brief.md "Copy rewrite"). The UI must NEVER show
 * dev jargon. Fact/node labels come from the backend's plain-English `label`
 * field; these helpers cover the rest (status words, the assistant chips).
 */

/** "Active" / "Replaced" — never "superseded". */
export function plainStatus(status: string): string {
  if (status === 'active') return 'Active'
  if (status === 'superseded') return 'Replaced'
  if (status === 'retracted') return 'Removed'
  return status.charAt(0).toUpperCase() + status.slice(1)
}

/** Assistant search-type → human label + the tech term kept for the tooltip. */
export function searchTypeCopy(searchType: string): { label: string; tip: string } {
  const st = searchType.toUpperCase()
  if (st.includes('TEMPORAL') || st.includes('GRAPH')) {
    return { label: 'Time-aware memory', tip: `Cognee ${searchType}` }
  }
  return { label: 'No memory · plain lookup', tip: `Cognee ${searchType}` }
}
