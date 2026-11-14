// One line per demo step: "passed" or "FAILED" with the first line of the error, then a total. Used by make demo-check.
import type { FullResult, Reporter, TestCase, TestResult } from '@playwright/test/reporter'

export default class DemoReporter implements Reporter {
  private passed = 0
  private total = 0

  onTestEnd(test: TestCase, result: TestResult) {
    this.total++
    if (result.status === 'passed') {
      this.passed++
      console.log(`passed  ${test.title} (${result.duration} ms)`)
    } else if (result.status === 'skipped') {
      console.log(`skipped ${test.title}`)
    } else {
      const why = (result.error?.message ?? result.status).split('\n')[0].replace(/\u001b\[[0-9;]*m/g, '')
      console.log(`FAILED  ${test.title}: ${why}`)
    }
  }

  onEnd(result: FullResult) {
    console.log(`demo-check: ${this.passed} of ${this.total} steps passed (${result.status})`)
  }
}
