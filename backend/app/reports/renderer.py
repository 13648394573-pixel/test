from html import escape
from typing import Any


REPORT_MODES = ("formal", "internal")


def _text(value: Any) -> str:
    if value is None:
        return "—"
    return escape(str(value))


def _result_badge(result: Any) -> str:
    css = {
        "PASS": "badge pass",
        "FAIL": "badge fail",
        "BLOCKED": "badge blocked",
    }.get(str(result), "badge")
    return f'<span class="{css}">{_text(result)}</span>'


def _summary_bar(summary: dict[str, Any]) -> str:
    total = summary.get("total", 0) or 0
    passed = summary.get("pass", 0) or 0
    failed = summary.get("fail", 0) or 0
    blocked = summary.get("blocked", 0) or 0
    ratio = round(passed / total * 100) if total else 0
    return (
        '<div class="summary">'
        f"<span><b>{total}</b>用例总数</span>"
        f'<span class="pass-text"><b>{passed}</b>通过</span>'
        f'<span class="fail-text"><b>{failed}</b>失败</span>'
        f'<span class="blocked-text"><b>{blocked}</b>阻塞</span>'
        f"<span><b>{ratio}%</b>通过率</span>"
        "</div>"
        '<div class="bar">'
        f'<span class="seg-pass" style="width:{(passed / total * 100) if total else 0:.1f}%"></span>'
        f'<span class="seg-fail" style="width:{(failed / total * 100) if total else 0:.1f}%"></span>'
        f'<span class="seg-blocked" style="width:{(blocked / total * 100) if total else 0:.1f}%"></span>'
        "</div>"
    )


CHECK_LABELS = {
    "ont_online": "ONT 在线",
    "onu_o5": "O5 状态",
    "rx_power_above_threshold": "光功率达标",
    "no_packet_loss": "零丢包",
    "avg_rtt_below_limit": "时延达标",
}


def _check_badges(parsed_meta: dict[str, Any] | None) -> str:
    if not parsed_meta:
        return ""
    checks = parsed_meta.get("checks") or {}
    badges = []
    for key, label in CHECK_LABELS.items():
        if key not in checks:
            continue
        passed = bool(checks[key])
        badges.append(
            f'<span class="check {"check-ok" if passed else "check-bad"}">'
            f"{'✓' if passed else '✗'} {label}</span>"
        )
    return f'<div class="checks">{"".join(badges)}</div>' if badges else ""


def _evidence_cell(evidences: list[dict[str, Any]]) -> str:
    if not evidences:
        return "—"
    parts = []
    for ev in evidences:
        name = _text(ev.get("original_name"))
        digest = _text(str(ev.get("sha256"))[:12])
        checks = _check_badges(ev.get("parsed_metadata"))
        data_uri = ev.get("data_uri")
        if data_uri:
            parts.append(
                f'<div class="ev"><a href="{data_uri}" target="_blank">'
                f'<img class="shot" src="{data_uri}" alt="{name}"></a>'
                f"<small>截图 {_text(ev.get('category'))} · {name}"
                f"<br>SHA256 {digest}…</small>{checks}</div>"
            )
        else:
            parts.append(
                f'<div class="ev">{name}'
                f"<small>{_text(ev.get('category'))} · SHA256 {digest}…</small>"
                f"{checks}</div>"
            )
    return "".join(parts)


def _results_table(snapshot: dict[str, Any], mode: str) -> str:
    rows = []
    for item in snapshot["results"]:
        case = item["case_snapshot"]
        internal_cells = ""
        if mode == "internal":
            internal_cells = (
                f"<td><small>执行: {_text(item.get('executed_at'))}<br>"
                f"锁定: {_text(item.get('locked_at'))}<br>"
                f"RunResult: <code>{_text(item.get('id'))}</code></small></td>"
            )
        rows.append(
            "<tr>"
            f"<td><code>{_text(case.get('case_code'))}</code><br>"
            f"<small>{_text(case.get('priority'))} · {_text(case.get('category'))}</small>"
            + (
                f"<br><small class='muted'>{_text(case.get('description'))}</small>"
                if case.get("description")
                else ""
            )
            + "</td>"
            f"<td>{_text(case.get('title'))}</td>"
            f"<td>{_result_badge(item['result'])}</td>"
            f"<td class='wrap'>{_text(item['actual_result'])}</td>"
            f"<td class='wrap'>{_text(item['blocked_reason'])}</td>"
            f"{internal_cells}"
            f"<td class='ev-cell'>{_evidence_cell(item.get('evidences') or [])}</td>"
            "</tr>"
        )
    internal_header = "<th>执行/锁定</th>" if mode == "internal" else ""
    return (
        "<h2>测试结果</h2>"
        "<table><thead><tr><th>用例</th><th>标题</th><th>结果</th>"
        "<th>实际结果</th><th>阻塞原因</th>"
        f"{internal_header}<th>证据（含截图）</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _defects_table(snapshot: dict[str, Any], mode: str) -> str:
    defects = snapshot.get("defects") or []
    if not defects:
        return "<h2>缺陷</h2><p>本次运行未关联缺陷。</p>"
    rows = []
    for item in defects:
        regression_rows = "".join(
            f"<li>{_text(reg['result'])} @ {_text(reg.get('executed_at'))} — {_text(reg.get('notes'))}</li>"
            for reg in item.get("regressions") or []
        )
        timeline = (
            f"创建 {_text(item.get('created_at'))} · "
            f"解决 {_text(item.get('resolved_at'))} · "
            f"关闭 {_text(item.get('closed_at'))}"
        )
        defect_images = "".join(
            f'<div class="ev"><a href="{ev["data_uri"]}" target="_blank">'
            f'<img class="shot" src="{ev["data_uri"]}" alt="{_text(ev.get("original_name"))}"></a>'
            f"<small>{_text(ev.get('original_name'))}</small></div>"
            for ev in item.get("evidences") or []
            if ev.get("data_uri")
        )
        extra = (
            f"<div class='defect-meta'>{_text(item.get('description'))}</div>"
            f"<div class='defect-meta'>{_text(item.get('resolution_notes'))}</div>"
            f"<div class='defect-meta'>{timeline}</div>"
            if mode == "internal"
            else f"<div class='defect-meta'>{timeline}</div>"
        )
        regression_html = (
            f"<ul class='regressions'>{regression_rows}</ul>" if regression_rows else ""
        )
        rows.append(
            "<tr>"
            f"<td><code>{_text(item['defect_code'])}</code></td>"
            f"<td>{_text(item['title'])}<br><small>严重级 {_text(item.get('severity'))}</small></td>"
            f"<td>{_result_badge(item['status'])}{extra}{regression_html}"
            + (
                f"<div class='defect-shots'>{defect_images}</div>"
                if defect_images
                else ""
            )
            + "</td>"
            "</tr>"
        )
    return (
        "<h2>缺陷与回归</h2>"
        "<table><thead><tr><th>编号</th><th>标题</th><th>状态/记录</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _document_block(snapshot: dict[str, Any], mode: str) -> str:
    doc_rows = (
        f"<tr><th>报告编号</th><td>{_text(snapshot.get('report_no'))}</td></tr>"
        f"<tr><th>报告版本</th><td>{_text(snapshot.get('report_version'))}</td></tr>"
        f"<tr><th>项目版本</th><td>{_text((snapshot.get('project') or {}).get('version'))}</td></tr>"
        f"<tr><th>客户代码</th><td>{_text(snapshot.get('customer_code'))}</td></tr>"
        f"<tr><th>快照版本</th><td>{_text(snapshot.get('snapshot_version'))}</td></tr>"
        f"<tr><th>生成时间</th><td>{_text(snapshot.get('generated_at'))}</td></tr>"
    )
    if mode == "formal":
        sign_rows = (
            "<tr><th>测试执行人</th><td class='sign'></td></tr>"
            "<tr><th>审核人</th><td class='sign'></td></tr>"
            "<tr><th>批准人</th><td class='sign'></td></tr>"
            "<tr><th>日期</th><td class='sign'></td></tr>"
        )
        return (
            "<h2>文档信息</h2><table class='doc'>"
            f"{doc_rows}{sign_rows}</table>"
            "<p class='muted small'>本报告基于不可变运行快照生成，结果经完整性锁定，"
            "证据文件以 SHA256 校验归档，测试设备信息见各用例说明。</p>"
        )
    environment = snapshot.get("environment_snapshot")
    env_line = (
        f"<tr><th>环境快照</th><td>{_text((environment or {}).get('profile_snapshot', {}).get('profile_name'))}"
        f" · v{_text((environment or {}).get('snapshot_version'))}</td></tr>"
        if environment is not None
        else ""
    )
    return (
        "<h2>文档信息</h2><table class='doc'>"
        f"{doc_rows}{env_line}"
        f"<tr><th>Run ID</th><td><code>{_text((snapshot.get('run') or {}).get('id'))}</code></td></tr>"
        "</table>"
    )


def _known_issues(snapshot: dict[str, Any]) -> str:
    notes = []
    for item in snapshot["results"]:
        if item["result"] == "BLOCKED" and item.get("blocked_reason"):
            notes.append(_text(item["blocked_reason"]))
    if not notes:
        return ""
    items = "".join(f"<li>{note}</li>" for note in notes)
    return f"<h2>已知问题与说明</h2><ul>{items}</ul>"


STYLE = (
    "<style>"
    ":root{--line:#d4d4d8;--muted:#71717a;--pass:#16a34a;--fail:#dc2626;"
    "--blocked:#d97706}"
    "*{box-sizing:border-box}"
    "body{font-family:'Segoe UI','Microsoft YaHei',Arial,sans-serif;margin:0;"
    "color:#18181b;font-size:14px;line-height:1.6}"
    ".page{max-width:1080px;margin:0 auto;padding:40px 32px}"
    "h1{font-size:24px;border-bottom:3px solid #18181b;padding-bottom:12px}"
    "h2{font-size:17px;margin-top:32px;border-left:4px solid #2563eb;"
    "padding-left:10px}"
    "table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}"
    "th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;"
    "vertical-align:top}"
    "th{background:#f4f4f5}"
    ".wrap{word-break:break-word;max-width:300px}"
    ".summary{display:flex;gap:28px;margin:16px 0 8px;font-size:14px}"
    ".summary span{color:var(--muted)}"
    ".summary b{font-size:20px;color:#18181b;margin-right:4px}"
    ".summary .pass-text b{color:var(--pass)}"
    ".summary .fail-text b{color:var(--fail)}"
    ".summary .blocked-text b{color:var(--blocked)}"
    ".bar{display:flex;height:10px;border-radius:5px;overflow:hidden;"
    "background:#e4e4e7;margin-bottom:8px}"
    ".bar span{height:100%}"
    ".seg-pass{background:var(--pass)}.seg-fail{background:var(--fail)}"
    ".seg-blocked{background:var(--blocked)}"
    ".badge{display:inline-block;padding:1px 10px;border-radius:10px;"
    "font-size:12px;font-weight:600;color:#fff}"
    ".badge.pass{background:var(--pass)}.badge.fail{background:var(--fail)}"
    ".badge.blocked{background:var(--blocked)}"
    "code{background:#f4f4f5;padding:0 4px;border-radius:3px;font-size:12px}"
    ".ev{margin:4px 0}.ev small{display:block;color:var(--muted)}"
    ".ev-cell{max-width:280px}"
    ".shot{width:240px;max-width:100%;border:1px solid var(--line);"
    "border-radius:4px;display:block;margin-bottom:2px}"
    ".defect-shots{display:flex;gap:8px;flex-wrap:wrap;margin-top:6px}"
    ".customer-code{display:inline-block;background:#eff6ff;color:#1d4ed8;"
    "font-weight:600;padding:2px 10px;border-radius:4px}"
    ".checks{margin-top:4px}"
    ".check{display:inline-block;font-size:11px;font-weight:600;"
    "padding:0 6px;border-radius:8px;margin:1px 2px 1px 0}"
    ".check-ok{background:#dcfce7;color:#15803d}"
    ".check-bad{background:#fee2e2;color:#b91c1c}"
    ".defect-meta{color:var(--muted);font-size:12px;margin-top:4px}"
    ".regressions{margin:4px 0 0;padding-left:18px;font-size:12px}"
    ".muted{color:var(--muted)}.small{font-size:12px}"
    ".doc th{width:140px;background:#fff;border:none;text-align:right;"
    "color:var(--muted)}"
    ".doc td{border:none;border-bottom:1px solid var(--line)}"
    ".doc .sign:empty{height:32px}"
    "@media print{.page{padding:0}details{display:block}}"
    "</style>"
)


def render_report_html(snapshot: dict[str, Any], mode: str = "formal") -> str:
    if mode not in REPORT_MODES:
        raise ValueError(f"unsupported report mode: {mode}")
    project = snapshot["project"]
    summary = snapshot["summary"]
    device = snapshot["device_snapshot"]
    mode_label = "正式验收报告" if mode == "formal" else "内部存档报告"
    return (
        "<!doctype html><html lang=\"zh-CN\"><head>"
        "<meta charset=\"utf-8\">"
        f"<title>{_text(snapshot.get('report_title', project['name']))}</title>"
        f"{STYLE}</head><body><div class=\"page\">"
        f"<h1>{_text(snapshot.get('report_title', project['name']))}</h1>"
        f"<p>{mode_label} · {_text(project['name'])} "
        f"版本 <code>{_text(project['version'])}</code>"
        f" · 客户代码 <span class=\"customer-code\">"
        f"{_text(snapshot.get('customer_code'))}</span></p>"
        f"<p><b>被测设备：</b>{_text(device.get('vendor'))} "
        f"{_text(device.get('model'))}"
        f"（SN: {_text(device.get('serial_number'))}）"
        "　<span class='muted small'>测试设备与环境信息见各用例说明</span></p>"
        f"{_summary_bar(summary)}"
        f"{_results_table(snapshot, mode)}"
        f"{_known_issues(snapshot)}"
        f"{_defects_table(snapshot, mode)}"
        f"{_document_block(snapshot, mode)}"
        "</div></body></html>"
    )
