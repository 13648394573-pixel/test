from html import escape
from typing import Any


REPORT_MODES = ("formal", "internal")


def _text(value: Any) -> str:
    if value is None:
        return "—"
    return escape(str(value))


# 用户模板样式（reports/reports/.../report.html），仅追加证据截图所需的最小规则。
STYLE = (
    "<style>body{font-family:Arial,sans-serif;margin:32px}"
    "table{border-collapse:collapse;width:100%;margin:16px 0}"
    "th,td{border:1px solid #ccc;padding:8px;text-align:left;"
    "vertical-align:top}"
    ".summary{display:flex;gap:20px}"
    ".ev{margin:6px 0}.ev small{color:#666}"
    ".shot{max-width:320px;border:1px solid #ccc;display:block;margin:4px 0}"
    "</style>"
)


def _evidence_cell(evidences: list[dict[str, Any]]) -> str:
    if not evidences:
        return "—"
    parts = []
    for ev in evidences:
        name = _text(ev.get("original_name"))
        data_uri = ev.get("data_uri")
        if data_uri:
            parts.append(
                f'<div class="ev"><a href="{data_uri}" target="_blank">'
                f'<img class="shot" src="{data_uri}" alt="{name}"></a>'
                f"<small>{name}</small></div>"
            )
        else:
            parts.append(f'<div class="ev"><small>{name}</small></div>')
    return "".join(parts)


def _results_table(snapshot: dict[str, Any]) -> str:
    rows = []
    for item in snapshot["results"]:
        case = item["case_snapshot"]
        rows.append(
            "<tr>"
            f"<td>{_text(case.get('case_code'))}</td>"
            f"<td>{_text(case.get('title'))}</td>"
            f"<td>{_text(item['result'])}</td>"
            f"<td>{_text(item['actual_result'])}</td>"
            f"<td>{_text(item['blocked_reason'])}</td>"
            f"<td>{_evidence_cell(item.get('evidences') or [])}</td>"
            "</tr>"
        )
    return (
        "<h2>测试结果</h2>"
        "<table><thead><tr><th>用例</th><th>标题</th><th>结果</th>"
        "<th>实际结果</th><th>阻塞原因</th><th>证据</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _defects_table(snapshot: dict[str, Any]) -> str:
    defects = snapshot.get("defects") or []
    rows = []
    for item in defects:
        rows.append(
            "<tr>"
            f"<td>{_text(item.get('defect_code'))}</td>"
            f"<td>{_text(item.get('title'))}</td>"
            f"<td>{_text(item.get('severity'))}</td>"
            f"<td>{_text(item.get('status'))}</td>"
            "</tr>"
        )
    return (
        "<h2>缺陷</h2>"
        "<table><thead><tr><th>编号</th><th>标题</th><th>严重级</th>"
        "<th>状态</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_report_html(snapshot: dict[str, Any], mode: str = "formal") -> str:
    if mode not in REPORT_MODES:
        raise ValueError(f"unsupported report mode: {mode}")
    # 正式验收 / 内部存档公用同一版式（用户模板），mode 仅用于归档标记。
    project = snapshot["project"]
    summary = snapshot["summary"]
    device = snapshot["device_snapshot"]
    environment = snapshot.get("environment_snapshot") or {}
    profile_name = (environment.get("profile_snapshot") or {}).get("profile_name")
    title = snapshot.get("report_title") or project["name"]
    summary_bar = (
        '<div class="summary">'
        f"<strong>总数 {summary.get('total', 0)}</strong>"
        f"<strong>通过 {summary.get('pass', 0)}</strong>"
        f"<strong>失败 {summary.get('fail', 0)}</strong>"
        f"<strong>阻塞 {summary.get('blocked', 0)}</strong>"
        f"<strong>缺陷 {summary.get('defects', 0)}</strong>"
        "</div>"
    )
    return (
        "<!doctype html><html><head>"
        '<meta charset="utf-8">'
        f"<title>{_text(title)}</title>"
        f"{STYLE}</head><body>"
        f"<h1>{_text(title)}</h1>"
        f"<p>{_text(project['name'])} · 版本 {_text(project['version'])}"
        f" · 客户代码 {_text(snapshot.get('customer_code'))}</p>"
        f"<p>生成时间：{_text(snapshot.get('generated_at'))}</p>"
        f"<p>被测设备：{_text(device.get('model'))} / "
        f"{_text(device.get('serial_number'))}</p>"
        f"<p>测试环境：{_text(profile_name)}</p>"
        f"{summary_bar}"
        f"{_results_table(snapshot)}"
        f"{_defects_table(snapshot)}"
        "</body></html>"
    )
