import pytest
from types import SimpleNamespace
from playwright.sync_api import sync_playwright
from app.diagnostics.adapters.huawei import HuaweiOutputError

from app.local_runner.credentials import SecretValue
from app.local_runner.ma5800.actions import build_ipoe_command, build_pppoe_command, ParameterValidationError
from app.local_runner.ma5800.parsers import parse_wan_info
from app.local_runner.onu_web.neutral import NeutralPlaywrightSurface
from app.local_runner.evidence import GeneratedEvidenceWriter


TARGET = {"frame": 0, "slot": 2, "pon_port": 9, "ont_id": 12, "onu_serial_number": "AABBCCDDEEFF0011", "ipoe_vlan": 1000, "pppoe_vlan": 1000}


def test_wan_commands_use_explicit_distinct_host_indexes():
    params = {**TARGET, "ipoe_ip_index": 0, "pppoe_ip_index": 1}
    assert build_ipoe_command(params).text == "ont ipconfig 9 12 ip-index 0 dhcp vlan 1000 priority 0"
    assert build_pppoe_command(params, username=SecretValue("test-user"), password=SecretValue("test-pass")).text == "ont ipconfig 9 12 ip-index 1 pppoe user-account username test-user password test-pass vlan 1000"


def test_wan_builder_rejects_shared_ip_host():
    with pytest.raises(ParameterValidationError):
        build_pppoe_command({**TARGET, "ipoe_ip_index": 0, "pppoe_ip_index": 0}, username=SecretValue("test-user"), password=SecretValue("test-pass"))


def test_real_olt_index_format_preserves_both_wan_statuses():
    text = """Index : 1
Name : nas0_0
IPv4 Connection status : Connected
IPv4 access type : DHCP
IPv4 address : 192.0.2.10
Default gateway : 192.0.2.1
Manage VLAN : 1000
Index : 2
Name : nas0_1
IPv4 Connection status : Connected
IPv4 access type : PPPoE
IPv4 address : 198.51.100.10
Default gateway : 198.51.100.1
Manage VLAN : 1000
MA5800-X7(config-if-gpon-0/2)#"""
    items = parse_wan_info(text)
    assert [(x.mode, x.status, x.vlan, x.gateway) for x in items] == [("IPOE", "CONNECTED", 1000, "192.0.2.1"), ("PPPOE", "CONNECTED", 1000, "198.51.100.1")]


@pytest.fixture
def surface():
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True)
        page = browser.new_page()
        page.route("**/*", lambda route: route.fulfill(body="<body>fixture</body>", content_type="text/html"))
        page.set_default_timeout(2000)
        adapter = NeutralPlaywrightSurface("http://192.168.1.1")
        adapter.page = page
        yield adapter
        browser.close()


def test_status_navigation_and_ipv4_table_reading(surface):
    status = """<h2>IPv4 WAN Configuration</h2><table><tr><th>Interface</th><th>VLAN ID</th><th>MAC</th><th>Connection Type</th><th>Protocol</th><th>IP Address</th><th>Gateway</th><th>Lease Time</th><th>Status</th></tr><tr><td>nas0_0</td><td>1000</td><td>00:11:22:33:44:55</td><td>TR069</td><td>IPoE</td><td>192.0.2.10</td><td>192.0.2.1</td><td>7000 sec</td><td>up</td></tr><tr><td>ppp0_nas0_1</td><td>1000</td><td>00:11:22:33:44:55</td><td>INTERNET</td><td>PPPoE</td><td>198.51.100.10</td><td>198.51.100.1</td><td></td><td>up 00:02:00</td></tr></table><h2>IPv6 WAN Configuration</h2><table><tr><td>ppp0_nas0_1</td><td>1000</td><td>00:11:22:33:44:55</td><td>INTERNET</td><td>PPPoE</td><td></td><td>down</td></tr></table>"""
    surface.page.route("**/status_wan.asp", lambda route: route.fulfill(body=status, content_type="text/html"))
    surface.page.set_content('<a href="http://192.168.1.1/config_wan.asp">WAN</a><a href="http://192.168.1.1/status_wan.asp" target="contentIframe">WAN</a><iframe name="contentIframe"></iframe>')
    surface.open_wan_page()
    surface.select_wan("PPPOE")
    fields = surface.read_wan_fields()
    assert fields["status"] == "up 00:02:00"
    assert fields["ip_address"] == "198.51.100.10"
    assert fields["gateway"] == "198.51.100.1"
    assert fields["vlan"] == "1000"


def test_ping_reads_new_nested_frame_result_not_parent_form(surface):
    surface.page.set_content("""<input name='pingAddr'><input type='submit' value='Go' onclick="document.querySelector('iframe').srcdoc='<pre>4 packets transmitted, 4 packets received, 0% packet loss\\nround-trip min/avg/max = 1.0/2.0/3.0 ms</pre>'"><iframe srcdoc='<pre>4 packets transmitted, 0 packets received, 100% packet loss</pre>'></iframe>""")
    surface.surface = surface.page
    text = surface.run_ping("example.com", 4)
    assert "4 packets received" in text
    assert "0 packets received" not in text
    assert "4 packets received" in surface.page_text()


def test_huawei_mac_is_removed_from_rendered_evidence(tmp_path):
    writer = GeneratedEvidenceWriter(tmp_path)
    artifacts = writer.write_text_and_png("mac", title="OLT", text="MAC address : 0011-2233-4455")
    assert "0011-2233-4455" not in (tmp_path / artifacts[0].storage_path).read_text(encoding="utf-8")


def test_status_identifiers_are_masked_before_real_screenshot(surface):
    surface.page.set_content('<table><tr><td>0011-2233-4455</td><td>AABBCCDDEEFF0011</td></tr></table>')
    surface.surface = surface.page
    surface.mask_sensitive_controls()
    text = surface.page_text()
    assert "0011-2233-4455" not in text
    assert "AABBCCDDEEFF0011" not in text


@pytest.mark.parametrize("old_result", [
    "4 packets transmitted, 4 packets received, 0% packet loss",
    "ping: unknown host old-target.invalid",
])
def test_running_label_does_not_make_old_ping_output_current(surface, monkeypatch, old_result):
    from app.local_runner.onu_web import neutral
    surface.page.set_content(
        "<input name='pingAddr'><span id='state'>Idle</span>"
        "<input type='submit' value='Go' onclick=\"document.getElementById('state').textContent='Running...'\">"
        f"<pre>{old_result}</pre>"
    )
    surface.surface = surface.page
    ticks = iter([0, 0, 31])
    monkeypatch.setattr(neutral, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
    with pytest.raises(HuaweiOutputError):
        surface.run_ping("different-target.invalid", 4)


def test_cached_ping_text_is_redacted_with_dom(surface):
    surface.page.set_content("""<input name='pingAddr'><input type='submit' value='Go' onclick="document.querySelector('iframe').srcdoc='<pre>SN AABBCCDDEEFF0011 MAC 0011-2233-4455\\n4 packets transmitted, 4 packets received, 0% packet loss</pre>'"><iframe></iframe>""")
    surface.surface = surface.page
    surface.run_ping("example.com", 4)
    surface.mask_sensitive_controls()
    text = surface.page_text()
    assert "AABBCCDDEEFF0011" not in text
    assert "0011-2233-4455" not in text
    assert "4 packets received" in text


def test_identical_result_is_current_after_result_frame_navigation(surface):
    surface.page.set_content("""<input name='pingAddr'><input type='submit' value='Go' onclick="document.querySelector('iframe').srcdoc='<pre>4 packets transmitted, 4 packets received, 0% packet loss</pre>'"><iframe srcdoc='<pre>4 packets transmitted, 4 packets received, 0% packet loss</pre>'></iframe>""")
    surface.surface = surface.page
    assert "4 packets received" in surface.run_ping("example.com", 4)


def test_identical_in_place_result_is_current_after_old_summary_clears(surface):
    surface.page.set_content("""<input name='pingAddr'><input type='submit' value='Go' onclick="document.querySelector('pre').textContent='Running...'; setTimeout(() => document.querySelector('pre').textContent='4 packets transmitted, 4 packets received, 0% packet loss', 800)"><pre>4 packets transmitted, 4 packets received, 0% packet loss</pre>""")
    surface.surface = surface.page
    assert "4 packets received" in surface.run_ping("example.com", 4)
