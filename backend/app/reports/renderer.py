from html import escape
from typing import Any


def _text(value: Any) -> str:
    if value is None:
        return "—"
    return escape(str(value))


def render_report_html(snapshot: dict[str, Any]) -> str:
    project = snapshot["project"]
    summary = snapshot["summary"]
    device = snapshot["device_snapshot"]
    environment = snapshot["environment_snapshot"]
    result_rows = "".join(
        "<tr>"
        f"<td>{_text(item['case_snapshot'].get('case_code'))}</td>"
        f"<td>{_text(item['case_snapshot'].get('title'))}</td>"
        f"<td>{_text(item['result'])}</td>"
        f"<td>{_text(item['actual_result'])}</td>"
        f"<td>{_text(item['blocked_reason'])}</td>"
        "</tr>"
        for item in snapshot["results"]
    )
    defect_rows = "".join(
        "<tr>"
        f"<td>{_text(item['defect_code'])}</td>"
        f"<td>{_text(item['title'])}</td>"
        f"<td>{_text(item['severity'])}</td>"
        f"<td>{_text(item['status'])}</td>"
        "</tr>"
        for item in snapshot["defects"]
    )
    environment_name = (
        environment["profile_snapshot"].get("profile_name")
        if environment is not None
        else "Historical run without environment snapshot"
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Test Report</title>"
        "<style>body{font-family:Arial,sans-serif;margin:32px}"
        "table{border-collapse:collapse;width:100%;margin:16px 0}"
        "th,td{border:1px solid #ccc;padding:8px;text-align:left}"
        ".summary{display:flex;gap:20px}</style></head><body>"
        f"<h1>{_text(snapshot.get('report_title', project['name']))}</h1>"
        f"<p>{_text(project['name'])} {_text(project['version'])}</p>"
        f"<p>Generated: {_text(snapshot['generated_at'])}</p>"
        f"<p>Device: {_text(device.get('vendor'))} "
        f"{_text(device.get('model'))} / "
        f"{_text(device.get('serial_number'))}</p>"
        f"<p>Environment: {_text(environment_name)}</p>"
        "<div class=\"summary\">"
        f"<strong>Total {summary['total']}</strong>"
        f"<strong>PASS {summary['pass']}</strong>"
        f"<strong>FAIL {summary['fail']}</strong>"
        f"<strong>BLOCKED {summary['blocked']}</strong>"
        f"<strong>Defects {summary['defects']}</strong></div>"
        "<h2>Results</h2><table><thead><tr><th>Case</th><th>Title</th>"
        "<th>Result</th><th>Actual</th><th>Blocked reason</th></tr></thead>"
        f"<tbody>{result_rows}</tbody></table>"
        "<h2>Defects</h2><table><thead><tr><th>Code</th><th>Title</th>"
        "<th>Severity</th><th>Status</th></tr></thead>"
        f"<tbody>{defect_rows}</tbody></table></body></html>"
    )
