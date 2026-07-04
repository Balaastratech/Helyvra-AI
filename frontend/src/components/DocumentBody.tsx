import { cn } from '@/lib/utils'

/**
 * Renders a source record's extracted text as an actual-looking document
 * (letterhead, section headings, patient info strip, lab-result table)
 * instead of one flat pre-wrapped text blob. Heuristic, not a real PDF/CSV
 * parser — good enough for the synthetic fixtures this demo ingests, and
 * degrades to plain paragraphs when a line doesn't match a known shape.
 */

type Block =
  | { kind: 'heading'; text: string }
  | { kind: 'para'; text: string }
  | { kind: 'kv'; items: [string, string][] }
  | { kind: 'table'; rows: string[][] }

const FLAG_WORDS = new Set(['HIGH', 'LOW', 'NORMAL', 'CRITICAL', 'ABNORMAL', 'BORDERLINE'])
const KV_LINE_RE = /^[A-Z][A-Za-z ]{1,24}:\s*\S/
const KV_PAIR_RE = /([A-Z][A-Za-z ]{1,24}):\s*([^:]+?)(?=(?:\s{2,}[A-Z][A-Za-z ]{1,24}:)|$)/g

function isHeadingLine(line: string): boolean {
  if (!line || KV_LINE_RE.test(line)) return false
  if (line.endsWith('.') || line.endsWith(',')) return false
  if (line.length > 60) return false
  return /^[A-Z0-9]/.test(line) && line.split(/\s+/).length <= 9
}

/** Metadata pairs (Patient/MRN/DOB) are short tokens — reject anything that
 * reads like a narrative clause (long, or chains another sentence) so prose
 * doesn't get chopped into a bogus label/value chip. */
function isMetadataValue(value: string): boolean {
  return value.length <= 40 && !value.includes('. ')
}

function splitLetterhead(text: string): { title?: string; subtitle?: string; rest: string } {
  const lines = text.split('\n')
  let i = 0
  while (i < lines.length && lines[i].trim() === '') i++
  const first = lines[i]?.trim()
  const second = lines[i + 1]?.trim()
  if (first && isHeadingLine(first) && second && !KV_LINE_RE.test(second)) {
    return { title: first, subtitle: second, rest: lines.slice(i + 2).join('\n') }
  }
  return { rest: text }
}

function parseBlocks(text: string): Block[] {
  const lines = text.split('\n')
  const blocks: Block[] = []
  let para: string[] = []
  let kv: [string, string][] = []

  const flushPara = () => {
    if (para.length) {
      blocks.push({ kind: 'para', text: para.join(' ').replace(/\s+/g, ' ').trim() })
      para = []
    }
  }
  const flushKv = () => {
    if (kv.length) {
      blocks.push({ kind: 'kv', items: kv })
      kv = []
    }
  }

  let i = 0
  while (i < lines.length) {
    const line = lines[i].trim()
    if (!line) {
      flushPara()
      flushKv()
      i++
      continue
    }

    // Lab-style result table: "Test" header line followed by "Result", then
    // 5-column rows (name/result/units/reference range/flag) until the flag
    // stops looking like a flag word.
    if (/^test$/i.test(line) && /^result$/i.test(lines[i + 1]?.trim() ?? '')) {
      flushPara()
      flushKv()
      i += 5
      const rows: string[][] = []
      while (i + 4 < lines.length) {
        const row = [0, 1, 2, 3, 4].map((o) => lines[i + o]?.trim() ?? '')
        if (!FLAG_WORDS.has(row[4].toUpperCase())) break
        rows.push(row)
        i += 5
      }
      blocks.push({ kind: 'table', rows })
      continue
    }

    if (KV_LINE_RE.test(line)) {
      const pairs = [...line.matchAll(KV_PAIR_RE)].map((m) => [m[1].trim(), m[2].trim()] as [string, string])
      if (pairs.length && pairs.every(([, v]) => isMetadataValue(v))) {
        flushPara()
        kv.push(...pairs)
        i++
        continue
      }
    }
    flushKv()

    if (isHeadingLine(line)) {
      flushPara()
      blocks.push({ kind: 'heading', text: line })
      i++
      continue
    }

    para.push(line)
    i++
  }
  flushPara()
  flushKv()
  return blocks
}

function parseCsv(text: string): string[][] {
  return text
    .trim()
    .split(/\r?\n/)
    .filter((l) => l.length > 0)
    .map((line) => line.split(','))
}

function DataTable({ headers, rows, flagCol }: { headers: string[]; rows: string[][]; flagCol?: number }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="bg-raised">
            {headers.map((h, i) => (
              <th key={i} className="border-b border-border px-2.5 py-1.5 text-left font-semibold capitalize text-text-muted">
                {h.replace(/_/g, ' ')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="border-b border-border/60 last:border-0">
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className={cn(
                    'px-2.5 py-1.5',
                    flagCol === ci && cell.toUpperCase() !== 'NORMAL' ? 'font-semibold text-warning' : 'text-text',
                  )}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function DocumentBody({ title, text }: { title: string; text: string }) {
  if (/\.csv$/i.test(title)) {
    const rows = parseCsv(text)
    if (rows.length === 0) return null
    const [header, ...body] = rows
    return <DataTable headers={header} rows={body} />
  }

  const { title: heading, subtitle, rest } = splitLetterhead(text)
  const blocks = parseBlocks(rest)

  return (
    <div className="space-y-2.5">
      {heading && (
        <div>
          <p className="text-sm font-semibold text-text">{heading}</p>
          {subtitle && <p className="text-[11px] text-text-faint">{subtitle}</p>}
        </div>
      )}
      {blocks.map((b, i) => {
        if (b.kind === 'heading') {
          return (
            <h4 key={i} className="pt-1 text-[11px] font-semibold uppercase tracking-wide text-active">
              {b.text}
            </h4>
          )
        }
        if (b.kind === 'kv') {
          return (
            <div key={i} className="flex flex-wrap gap-x-4 gap-y-1 rounded-lg border border-border bg-raised/60 px-3 py-2 text-xs">
              {b.items.map(([k, v], j) => (
                <span key={j}>
                  <span className="text-text-faint">{k}:</span> <span className="font-medium text-text">{v}</span>
                </span>
              ))}
            </div>
          )
        }
        if (b.kind === 'table') {
          return <DataTable key={i} headers={['Test', 'Result', 'Units', 'Reference range', 'Flag']} rows={b.rows} flagCol={4} />
        }
        return (
          <p key={i} className="text-sm leading-relaxed text-text">
            {b.text}
          </p>
        )
      })}
    </div>
  )
}
