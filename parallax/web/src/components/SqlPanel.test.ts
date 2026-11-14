import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import compare from '../../../contract/examples/compare.json'
import type { Statement } from '../api'
import SqlPanel from './SqlPanel.vue'

describe('SqlPanel', () => {
  it('renders the statements of contract/examples/compare.json with time, rows and index', () => {
    const w = mount(SqlPanel, { props: { statements: compare.sql as Statement[], source: 'GET /api/compare' } })
    const items = w.findAll('[data-testid="sql-statement"]')
    expect(items).toHaveLength(compare.sql.length)
    const first = items[0].text()
    expect(first).toContain(`${compare.sql[0].ms.toFixed(1)} ms`)
    expect(first).toContain(`${compare.sql[0].rows} rows`)
    expect(first).toContain('vector index')
    expect(first).toContain('FOR SYSTEM_TIME AS OF TIMESTAMP')
    expect(items[0].findAll('.sql-panel__kw').map((b) => b.text())).toContain('VEC_DISTANCE_COSINE')
    expect(w.find('summary').text()).toContain('GET /api/compare')
  })
})
