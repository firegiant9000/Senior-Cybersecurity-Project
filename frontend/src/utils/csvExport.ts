/**
 * Triggers a browser download of a CSV file built from `rows`.
 * Each row is an array of values in the same order as `headers`.
 * Values are quoted and internal quotes are escaped.
 */
export function downloadCsv(
  filename: string,
  headers: string[],
  rows: (string | number | boolean | null | undefined)[][],
): void {
  const escape = (v: string | number | boolean | null | undefined): string => {
    const s = v === null || v === undefined ? '' : String(v)
    // Wrap in quotes if the value contains a comma, newline, or double-quote
    if (s.includes('"') || s.includes(',') || s.includes('\n')) {
      return `"${s.replace(/"/g, '""')}"`
    }
    return s
  }

  const lines = [
    headers.map(escape).join(','),
    ...rows.map(row => row.map(escape).join(',')),
  ]

  const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
