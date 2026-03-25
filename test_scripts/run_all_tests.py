"""
run_all_tests.py — Run all Library Agent System test suites
Outputs results to the console AND saves an HTML report to test_results/

Run from project root:
    python test_scripts/run_all_tests.py

Options:
    --agent librarian       Run only librarian tests
    --agent space_manager   Run only space manager tests
    --agent navigator       Run only navigator tests
    --agent maintenance     Run only maintenance tests
"""

import argparse
import io
import os
import sys
import unittest
from datetime import datetime


# ---------------------------------------------------------------------------
# HTML report builder
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Library Agent System — Test Report</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #1a1a2e; }}

    header {{
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
      color: #fff;
      padding: 36px 40px 28px;
    }}
    header h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: 0.5px; }}
    header p  {{ margin-top: 6px; font-size: 0.9rem; opacity: 0.75; }}

    .badge-row {{ display: flex; gap: 12px; margin-top: 20px; flex-wrap: wrap; }}
    .badge {{
      padding: 6px 16px; border-radius: 20px; font-size: 0.78rem;
      font-weight: 600; letter-spacing: 0.3px;
    }}
    .badge.pass  {{ background: #22c55e; color: #fff; }}
    .badge.fail  {{ background: #ef4444; color: #fff; }}
    .badge.total {{ background: rgba(255,255,255,0.15); color: #fff; }}
    .badge.time  {{ background: rgba(255,255,255,0.10); color: #ccc; }}

    main {{ max-width: 1000px; margin: 32px auto; padding: 0 20px 60px; }}

    .suite {{
      background: #fff;
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.07);
      margin-bottom: 24px;
      overflow: hidden;
    }}
    .suite-header {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 16px 24px;
      background: #f8f9fb;
      border-bottom: 1px solid #e8eaf0;
    }}
    .suite-header h2 {{ font-size: 1rem; font-weight: 700; }}
    .suite-meta {{ font-size: 0.8rem; color: #666; }}
    .suite-pill {{
      padding: 3px 12px; border-radius: 12px; font-size: 0.75rem; font-weight: 700;
    }}
    .suite-pill.pass {{ background: #dcfce7; color: #15803d; }}
    .suite-pill.fail {{ background: #fee2e2; color: #b91c1c; }}

    table {{ width: 100%; border-collapse: collapse; }}
    th {{
      text-align: left; padding: 10px 24px;
      font-size: 0.72rem; text-transform: uppercase;
      letter-spacing: 0.6px; color: #888;
      border-bottom: 1px solid #e8eaf0;
    }}
    td {{ padding: 11px 24px; font-size: 0.85rem; border-bottom: 1px solid #f3f4f6; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafbff; }}

    .status {{ font-weight: 700; font-size: 0.78rem; }}
    .status.PASS {{ color: #16a34a; }}
    .status.FAIL {{ color: #dc2626; }}
    .status.ERROR {{ color: #d97706; }}

    .test-name {{ font-family: 'Consolas', 'Courier New', monospace; color: #374151; }}
    .test-class {{ color: #9ca3af; margin-right: 6px; }}

    .error-block {{
      background: #fff7f7; border-left: 3px solid #ef4444;
      margin: 0 24px 12px; padding: 10px 14px;
      border-radius: 0 6px 6px 0;
      font-family: monospace; font-size: 0.78rem;
      color: #7f1d1d; white-space: pre-wrap; word-break: break-all;
    }}

    footer {{
      text-align: center; font-size: 0.78rem; color: #aaa;
      padding: 20px;
    }}
  </style>
</head>
<body>

<header>
  <h1>Library Agent System — Test Report</h1>
  <p>Generated {timestamp}</p>
  <div class="badge-row">
    <span class="badge total">Total: {total}</span>
    <span class="badge pass">Passed: {passed}</span>
    <span class="badge fail">Failed: {failed}</span>
    <span class="badge time">Duration: {duration}s</span>
    <span class="badge {overall_class}">{overall_label}</span>
  </div>
</header>

<main>
  {suites_html}
</main>

<footer>Library Agent System &mdash; Test Report &mdash; {timestamp}</footer>
</body>
</html>
"""

SUITE_TEMPLATE = """
<div class="suite">
  <div class="suite-header">
    <div>
      <h2>{suite_label}</h2>
      <span class="suite-meta">{passed}/{total} passed &nbsp;&bull;&nbsp; {duration}s</span>
    </div>
    <span class="suite-pill {pill_class}">{pill_label}</span>
  </div>
  <table>
    <thead>
      <tr>
        <th>Status</th>
        <th>Test</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>
"""


def _escape(text):
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


class HTMLReporter(unittest.TestResult):
    """Collects results per test for HTML output."""

    def __init__(self):
        super().__init__()
        self.results = []  # (status, test_id, message)
        self._start = None

    def startTest(self, test):
        super().startTest(test)
        self._start = datetime.now()

    def _record(self, status, test, message=""):
        duration = (datetime.now() - self._start).total_seconds() if self._start else 0
        self.results.append((status, str(test), message, round(duration, 3)))

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record("PASS", test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record("FAIL", test, self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._record("ERROR", test, self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record("SKIP", test, reason)


def build_suite_html(label, reporter, duration):
    total  = len(reporter.results)
    passed = sum(1 for r in reporter.results if r[0] == "PASS")
    failed = total - passed
    pill_class = "pass" if failed == 0 else "fail"
    pill_label = "ALL PASSED" if failed == 0 else f"{failed} FAILED"

    rows = []
    for status, test_id, message, _ in reporter.results:
        # test_id looks like: TestClassName.test_method_name (module.ClassName...)
        parts = test_id.split(".")
        class_part = parts[-2] if len(parts) >= 2 else ""
        method_part = parts[-1] if parts else test_id
        method_display = method_part.replace("_", " ").strip()

        row = f"""
        <tr>
          <td><span class="status {status}">{status}</span></td>
          <td class="test-name">
            <span class="test-class">{_escape(class_part)} &rsaquo;</span>{_escape(method_display)}
          </td>
        </tr>"""
        rows.append(row)

        if message and status in ("FAIL", "ERROR"):
            rows.append(f'<tr><td colspan="2"><div class="error-block">{_escape(message)}</div></td></tr>')

    return SUITE_TEMPLATE.format(
        suite_label=label,
        passed=passed,
        total=total,
        duration=round(duration, 2),
        pill_class=pill_class,
        pill_label=pill_label,
        rows_html="\n".join(rows),
    ), passed, failed


# ---------------------------------------------------------------------------
# Suite definitions & runner
# ---------------------------------------------------------------------------

SUITES = {
    "librarian":     ("test_librarian",     "Semantic Librarian Agent"),
    "space_manager": ("test_space_manager", "Space Manager Agent"),
    "navigator":     ("test_navigator",     "Digital Resource Navigator Agent"),
    "maintenance":   ("test_maintenance",   "Maintenance & Inventory Agent"),
}


def run(agent_filter=None):
    targets = (
        {k: v for k, v in SUITES.items() if k == agent_filter}
        if agent_filter else SUITES
    )

    if not targets:
        print(f"[ERROR] Unknown agent '{agent_filter}'. Choose from: {', '.join(SUITES)}")
        sys.exit(1)

    suites_html   = []
    grand_total   = 0
    grand_passed  = 0
    grand_failed  = 0
    report_start  = datetime.now()

    for key, (module, label) in targets.items():
        print()
        print("=" * 60)
        print(f"  {label.upper()}")
        print("=" * 60)

        suite   = unittest.defaultTestLoader.loadTestsFromName(module)
        reporter = HTMLReporter()

        t0 = datetime.now()
        # Also stream to console
        stream  = io.StringIO()
        console = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
        console_result = console.run(suite)

        # Re-run silently to capture structured results for HTML
        suite2   = unittest.defaultTestLoader.loadTestsFromName(module)
        suite2.run(reporter)

        duration = (datetime.now() - t0).total_seconds()
        html, passed, failed = build_suite_html(label, reporter, duration)

        suites_html.append(html)
        grand_total  += len(reporter.results)
        grand_passed += passed
        grand_failed += failed

    total_duration = round((datetime.now() - report_start).total_seconds(), 2)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Write HTML report
    report_dir  = os.path.join(os.getcwd(), "test_results")
    os.makedirs(report_dir, exist_ok=True)
    filename    = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    report_path = os.path.join(report_dir, filename)
    latest_path = os.path.join(report_dir, "latest.html")

    html_content = HTML_TEMPLATE.format(
        timestamp=timestamp,
        total=grand_total,
        passed=grand_passed,
        failed=grand_failed,
        duration=total_duration,
        overall_class="pass" if grand_failed == 0 else "fail",
        overall_label="ALL PASSED" if grand_failed == 0 else f"{grand_failed} FAILED",
        suites_html="\n".join(suites_html),
    )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print()
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Total   : {grand_total}")
    print(f"  Passed  : {grand_passed}")
    print(f"  Failed  : {grand_failed}")
    print(f"  Result  : {'ALL PASSED' if grand_failed == 0 else 'SOME FAILURES'}")
    print(f"  Report  : test_results/{filename}")
    print("=" * 60)

    sys.exit(0 if grand_failed == 0 else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Library Agent System tests")
    parser.add_argument(
        "--agent",
        choices=list(SUITES.keys()),
        help="Run tests for a specific agent only",
    )
    args = parser.parse_args()
    run(agent_filter=args.agent)
