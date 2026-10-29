# -*- coding: utf-8 -*-
"""End-to-end API smoke test against a running backend.

Usage (backend started with an isolated data dir):

    uvicorn app.main:app --port 8123   # one shell
    python scripts/smoke_e2e.py        # another shell

Env: SMOKE_BASE (default http://127.0.0.1:8123/api), SMOKE_DB (default
smoke/data/smoke.db) for the archive-path cross-check.

Walks the full lifecycle: cases -> device -> environment (credential ref) ->
project -> run -> results -> evidence (auto-parse) -> defect -> regression ->
CLOSED -> dual-mode reports -> archive -> integrity checks.
Prints one line per step; exits non-zero on any failure.
"""
import io
import json
import sys
import zipfile

import requests

import os
BASE = os.environ.get("SMOKE_BASE", "http://127.0.0.1:8123/api")
SMOKE_DB = os.environ.get("SMOKE_DB", "smoke/data/smoke.db")
FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {label}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


def req(method: str, path: str, expect: int = 200, **kwargs):
    r = requests.request(method, BASE + path, timeout=30, **kwargs)
    if r.status_code != expect:
        print(f"  !! {method} {path} -> {r.status_code}: {r.text[:300]}")
    return r


import time  # noqa: E402

SUFFIX = str(int(time.time()))[-6:]


# ---------------------------------------------------------------- 1. cases
case1 = req("POST", "/test-cases", 201, json={
    "case_code": "SMK-001-" + SUFFIX, "title": "冒烟-PON上线O5校验 " + SUFFIX, "device_type": "ONU",
    "category": "FUNCTIONAL", "priority": "P0",
    "description": "被测设备 ONU（型号不限，本次 XPON UN-769XR）；测试设备 OLT 华为 MA5800-X7。",
    "preconditions": "光路连接正常",
    "steps": [
        {"action": "OLT 下 display ont info 查看ONT状态", "expected_result": "ONT Phase=working, O5"},
    ],
}).json()
case2 = req("POST", "/test-cases", 201, json={
    "case_code": "SMK-002-" + SUFFIX, "title": "冒烟-WAN连通性 " + SUFFIX, "device_type": "ONU",
    "category": "FUNCTIONAL", "priority": "P0",
    "description": "ONU WAN 口 IPoE 拨号并 ping 外网。",
    "steps": [
        {"action": "ONU WAN 建立 IPoE 连接", "expected_result": "连接成功"},
        {"action": "ping 外网 4 包", "expected_result": "0% 丢包"},
    ],
}).json()
check("create test cases", len(case1["id"]) > 0 and len(case2["id"]) > 0)

# ---------------------------------------------------------------- 2. device
device = req("POST", "/devices", 201, json={
    "device_type": "ONU", "vendor": "XPON", "model": "UN-769XR",
    "serial_number": "SMK-SN-" + SUFFIX, "software_version": "V2.1.7",
}).json()
check("create device with full profile", device["model"] == "UN-769XR")

# ------------------------------------------------- 3. env + credential ref
cred = req("PUT", "/local-credentials/olt_root_smoke", 200,
           json={"secret": "smoke-secret-do-not-use"})
check("store credential in keyring-backed store", cred.status_code == 200, cred.text[:200])

env = req("POST", "/environment-profiles", 201, json={
    "name": "冒烟环境 " + SUFFIX, "enabled": True,
    "parameters": [
        {"section": "OLT", "param_key": "manage_ip", "param_value": "192.168.87.204", "display_order": 1},
        {"section": "OLT", "param_key": "root_password", "param_value": "credential:olt_root_smoke", "display_order": 1},
    ],
}).json()
check("create env profile with credential reference",
      any(p["param_value"] == "credential:olt_root_smoke" for p in env["parameters"]))

# plaintext password must be rejected at model layer
bad = req("POST", "/environment-profiles", 422, json={
    "name": "坏环境 " + SUFFIX, "enabled": True,
    "parameters": [
        {"section": "OLT", "param_key": "super_password", "param_value": "YnQtcG9u", "display_order": 1},
    ],
})
check("plaintext password rejected", bad.status_code == 422, f"got {bad.status_code}")

# ------------------------------------------------------------- 4. project
project = req("POST", "/test-projects", 201, json={
    "name": "冒烟项目 " + SUFFIX, "version": "V1.0.0-smoke",
    "case_source_ids": [case1["id"], case2["id"]],
}).json()
check("create project", len(project.get("id", "")) > 0)

# ------------------------------------------------------------------ 5. run
run = req("POST", f"/test-projects/{project['id']}/runs", 201, json={
    "device_source_id": device["id"],
    "environment_profile_id": env["id"],
}).json()
results = run["results"]
check("run created with 2 results", len(results) == 2, json.dumps(run)[:200])

r_pon = next(r for r in results if r["case_source_id"] == case1["id"])
r_wan = next(r for r in results if r["case_source_id"] == case2["id"])

# ------------------------------------------------------------ 6. evidence first
cli_log = (
    "huawei(config)# display ont info 0 2 10 48\n"
    "  F/S/P                : 0/2/10\n"
    "  ONT-ID               : 48\n"
    "  Run state            : online\n"
    "  Config state         : normal\n"
    "  Match state          : match\n"
    "  Authentic type       : SN\n"
    "  Last down cause      : LOSi\n"
)
png1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8cfc000000301010018dd8db00000000049"
    "454e44ae426082")
ev1 = req("POST", f"/run-results/{r_pon['id']}/evidences", 201,
          files={"file": ("ont-info.txt", io.BytesIO(cli_log.encode()), "text/plain")},
          data={"category": "LOG", "description": "ONT 状态 CLI"})
ev2 = req("POST", f"/run-results/{r_wan['id']}/evidences", 201,
          files={"file": ("wan.png", io.BytesIO(png1x1), "image/png")},
          data={"category": "SCREENSHOT", "description": "WAN 截图"})
check("upload text evidence", ev1.status_code == 201, ev1.text[:200])
check("upload screenshot evidence", ev2.status_code == 201, ev2.text[:200])

parsed = ev1.json().get("parsed_metadata") if ev1.status_code == 201 else None
if isinstance(parsed, str):
    parsed = json.loads(parsed)
check("evidence auto-parsed on upload", isinstance(parsed, dict) and bool(parsed),
      f"parsed={parsed}")
if isinstance(parsed, dict):
    blob = json.dumps(parsed, ensure_ascii=False)
    check("parse extracted ONT/O5 facts", "O5" in blob or "ont" in blob.lower(), blob[:250])

# evidence on a locked result must be rejected
req("PUT", f"/test-runs/{run['id']}/results/{r_pon['id']}", 200, json={
    "result": "PASS", "actual_result": "ONT 48, O5", "test_notes": "smoke pass"})
req("PUT", f"/test-runs/{run['id']}/results/{r_wan['id']}", 200, json={
    "result": "FAIL", "actual_result": "丢包 50%", "test_notes": "smoke fail"})
for r in (r_pon, r_wan):
    lk = req("POST", f"/test-runs/{run['id']}/results/{r['id']}/lock", 200)
    check("lock result", lk.status_code == 200, lk.text[:150])
late = req("POST", f"/run-results/{r_pon['id']}/evidences", 409,
           files={"file": ("late.txt", io.BytesIO(b"x"), "text/plain")},
           data={"category": "LOG"})
check("locked result rejects new evidence", late.status_code == 409, f"got {late.status_code}")

# ----------------------------------------------- 8. defect -> regression
defect = req("POST", "/defects", 201, json={
    "source_run_result_id": r_wan["id"],
    "title": "冒烟-WAN丢包 " + SUFFIX, "description": "ping 丢包 50%",
    "reproduction_steps": "拨号后 ping 114.114.114.114",
    "severity": "S2",
}).json()
check("defect created OPEN", defect["status"] == "OPEN", defect.get("status"))

# generic PUT must not be able to change lifecycle fields
full_payload = {
    "title": "冒烟-WAN丢包 " + SUFFIX, "description": "ping 丢包 50%（改）",
    "reproduction_steps": "拨号后 ping", "severity": "S2",
    "status": "CLOSED", "resolved_at": "2026-01-01T00:00:00",
}
shot = req("PUT", f"/defects/{defect['id']}", 200, json=full_payload)
after = req("GET", f"/defects/{defect['id']}").json()
check("generic PUT cannot close/backdate a defect",
      after["status"] == "OPEN" and after.get("resolved_at") is None,
      f"status={after['status']} resolved_at={after.get('resolved_at')} put={shot.status_code}")

# second run: same project/device/env, WAN now passes -> regression evidence
run2 = req("POST", f"/test-projects/{project['id']}/runs", 201, json={
    "device_source_id": device["id"],
    "environment_profile_id": env["id"],
}).json()
r_wan2 = next(r for r in run2["results"] if r["case_source_id"] == case2["id"])
r_pon2 = next(r for r in run2["results"] if r["case_source_id"] == case1["id"])
req("PUT", f"/test-runs/{run2['id']}/results/{r_wan2['id']}", 200, json={
    "result": "PASS", "actual_result": "丢包 0%", "test_notes": "回归通过"})
req("PUT", f"/test-runs/{run2['id']}/results/{r_pon2['id']}", 200, json={
    "result": "PASS", "actual_result": "O5", "test_notes": "回归通过"})
ev3 = req("POST", f"/run-results/{r_pon2['id']}/evidences", 201,
          files={"file": ("ont-info.txt", io.BytesIO(cli_log.encode()), "text/plain")},
          data={"category": "LOG", "description": "ONT 状态 CLI（回归）"})
ev4 = req("POST", f"/run-results/{r_wan2['id']}/evidences", 201,
          files={"file": ("wan-pass.png", io.BytesIO(png1x1), "image/png")},
          data={"category": "SCREENSHOT", "description": "WAN 回归截图"})
check("upload evidence to run2 before lock",
      ev3.status_code == 201 and ev4.status_code == 201)
for r in (r_wan2, r_pon2):
    req("POST", f"/test-runs/{run2['id']}/results/{r['id']}/lock", 200)

# regression before RESOLVED must be rejected by the state machine
early = req("POST", f"/defects/{defect['id']}/regressions", 409, json={
    "verification_run_result_id": r_wan2["id"], "notes": "too early"})
check("regression rejected while defect still OPEN", early.status_code == 409,
      f"got {early.status_code}")

req("PUT", f"/defects/{defect['id']}/status", 200, json={"target_status": "IN_PROGRESS"})
resolved = req("PUT", f"/defects/{defect['id']}/status", 200, json={
    "target_status": "RESOLVED", "resolution_notes": "已修复，待回归"})
check("defect OPEN->IN_PROGRESS->RESOLVED", resolved.status_code == 200, resolved.text[:200])

reg = req("POST", f"/defects/{defect['id']}/regressions", 201, json={
    "verification_run_result_id": r_wan2["id"], "notes": "smoke regression"})
check("regression recorded", reg.status_code == 201, reg.text[:200])
defect2 = req("GET", f"/defects/{defect['id']}").json()
check("regression PASS auto-closes defect",
      defect2["status"] == "CLOSED" and bool(defect2.get("closed_at")),
      f"status={defect2['status']} closed_at={defect2.get('closed_at')}")
check("resolved_at >= original resolved time (no backdating)",
      bool(defect2.get("resolved_at")) and defect2["resolved_at"] >= "2026-10-29",
      f"resolved_at={defect2.get('resolved_at')}")

# --------------------------------------------- 9. dual-mode reports
rep_f = req("POST", f"/test-runs/{run2['id']}/reports", 201, json={
    "mode": "formal", "customer_code": "CUST-SMOKE-001"}).json()
rep_i = req("POST", f"/test-runs/{run2['id']}/reports", 201, json={
    "mode": "internal"}).json()
snap_f = rep_f.get("report_snapshot", {})
snap_i = rep_i.get("report_snapshot", {})
check("reports generated in both modes",
      snap_f.get("mode") == "formal" and snap_i.get("mode") == "internal",
      f"modes={snap_f.get('mode')}/{snap_i.get('mode')}")

html_f = req("GET", f"/reports/{rep_f['id']}/download").text
check("formal report has sign-off", "测试执行人" in html_f and "批准人" in html_f)
check("formal report shows customer code", "CUST-SMOKE-001" in html_f)
check("formal report inlines screenshot", "data:image/png;base64," in html_f)
check("formal report hides environment name", ("冒烟环境 " + SUFFIX) not in html_f)
check("formal report shows parsed judgement badge", "O5" in html_f or "光功率" in html_f)
html_i = req("GET", f"/reports/{rep_i['id']}/download").text
check("internal report keeps env snapshot reference", "冒烟环境 " + SUFFIX in html_i)

# ---------------------------------------------------- 10. archive integrity
arch = req("POST", f"/reports/{rep_f['id']}/archive", 201).json()
zip_resp = req("GET", f"/archives/{arch['id']}/download")
zf = zipfile.ZipFile(io.BytesIO(zip_resp.content))
names = zf.namelist()
manifest = json.loads(zf.read("manifest.json"))
files = manifest.get("files") or manifest.get("evidences") or []
check("archive zip contains report+manifest",
      "report.html" in names and "manifest.json" in names, str(names))
evidence_files = [f for f in files if isinstance(f, dict) and f.get("path") != "report.html"]
check("archive manifest evidence entries carry original_name + sha256",
      bool(evidence_files) and all(f.get("original_name") and f.get("sha256") for f in evidence_files),
      json.dumps(manifest, ensure_ascii=False)[:300])

# every archived evidence path must equal the database storage_path
import sqlite3
db = sqlite3.connect(SMOKE_DB)
db_paths = {row[0] for row in db.execute("select storage_path from evidences")}
db.close()
archived_paths = {f.get("path") for f in evidence_files}
expected_paths = {"evidence/" + path for path in db_paths}
check("archive evidence paths = 'evidence/' + DB storage_path",
      bool(archived_paths) and archived_paths <= expected_paths,
      f"archived={sorted(archived_paths)} unexpected={sorted(archived_paths - expected_paths)}")

# ------------------------------------------------------------------ summary
print()
if FAILURES:
    print(f"SMOKE FAILED: {len(FAILURES)} step(s): {FAILURES}")
    sys.exit(1)
print("SMOKE OK - all steps passed")
