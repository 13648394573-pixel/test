import pytest

from app.local_runner.contracts import ActionContext
from app.local_runner.credentials import SecretValue
from app.local_runner.onu_web.contracts import (
    ONUWebAuthenticationError,
    ONUWebSelectorError,
    ONUWebUnavailableError,
    ONUWebWanNotVisibleError,
)
from app.local_runner.onu_web.neutral import NeutralONUWebAdapter, NeutralPlaywrightSurface
from app.local_runner.onu_web.selectors import (
    ONUWebAdapterRegistry,
    UnknownONUWebAdapterError,
)


class FakeSurface:
    def __init__(self, *, error=None, ping_control_error=None, ping_text=None):
        self.error = error
        self.ping_control_error = ping_control_error
        self.ping_text = ping_text or (
            "sent=3 received=3 loss=0% min=1.0ms avg=1.5ms max=2.0ms"
        )
        self.selected = None
        self.masked = False
        self.opened_pages = []
        self.ping_controls_checked = False
        self.ping_runs = 0

    def authenticate(self, username, password):
        assert username.reveal() == "operator"
        assert password.reveal() == "local-value"
        if isinstance(self.error, ONUWebAuthenticationError):
            raise self.error
        if isinstance(self.error, ONUWebUnavailableError):
            raise self.error

    def open_wan_page(self):
        if isinstance(self.error, ONUWebSelectorError):
            raise self.error
        self.opened_pages.append("wan")

    def select_wan(self, wan_mode):
        self.selected = wan_mode
        if isinstance(self.error, ONUWebWanNotVisibleError):
            raise self.error

    def read_wan_fields(self):
        return {
            "status": "Connected",
            "ip_address": "192.0.2.10",
            "subnet_mask": "255.255.255.0",
            "gateway": "192.0.2.1",
            "primary_dns": "203.0.113.53",
            "vlan": "1000",
            "service_type": "INTERNET",
        }

    def open_ping_page(self):
        self.opened_pages.append("ping")

    def assert_ping_controls(self):
        if self.ping_control_error is not None:
            raise self.ping_control_error
        self.ping_controls_checked = True

    def run_ping(self, target, packet_count):
        self.ping_runs += 1
        assert target == "example.com"
        assert packet_count == 3
        return self.ping_text

    def mask_sensitive_controls(self):
        self.masked = True

    def page_text(self):
        return "Status Connected Password: local-value"

    def screenshot(self):
        assert self.masked is True
        return b"\x89PNG\r\n\x1a\nmasked-page"

    def close(self):
        return None


def context(wan_mode="IPOE") -> ActionContext:
    return ActionContext(
        session_id="session-1",
        action_code="capture_wan",
        parameters={"onu_web_url": "http://192.168.1.1", "wan_mode": wan_mode},
        secrets={
            "onu_web_username": SecretValue("operator"),
            "onu_web_password": SecretValue("local-value"),
        },
    )


def observation(outcome, key):
    return next(item.value for item in outcome.observations if item.fact_key == key)


def test_capture_wan_returns_address_and_two_redacted_artifacts() -> None:
    surface = FakeSurface()
    outcome = NeutralONUWebAdapter(lambda _context: surface).capture_wan(
        context("IPOE"), "IPOE"
    )

    assert outcome.status == "PASS"
    assert surface.selected == "IPOE"
    assert observation(outcome, "ipoe.ip_address") == "192.0.2.10"
    assert observation(outcome, "ipoe.vlan") == 1000
    assert {item.media_type for item in outcome.artifacts} == {
        "image/png",
        "text/plain",
    }
    text = next(item.content for item in outcome.artifacts if item.media_type == "text/plain")
    assert b"local-value" not in text
    assert all(item.redacted for item in outcome.artifacts)


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (ONUWebAuthenticationError(), "BLOCKED", "ONU_WEB_CREDENTIAL_REJECTED"),
        (ONUWebUnavailableError(), "BLOCKED", "ONU_WEB_UNREACHABLE"),
        (ONUWebSelectorError("WAN_NAV"), "BLOCKED", "ONU_WEB_SELECTOR_UNSUPPORTED"),
        (ONUWebWanNotVisibleError(), "FAIL", "WAN_NOT_VISIBLE"),
    ],
)
def test_capture_wan_maps_failures_precisely(error, status, code) -> None:
    outcome = NeutralONUWebAdapter(
        lambda _context: FakeSurface(error=error)
    ).capture_wan(context(), "IPOE")
    assert outcome.status == status
    assert outcome.error_code == code


def test_run_ping_uses_reusable_parser_and_captures_evidence() -> None:
    surface = FakeSurface(
        ping_text="sent=3 received=2 loss=33.33% min=1ms avg=2ms max=4ms"
    )
    outcome = NeutralONUWebAdapter(lambda _context: surface).run_ping(
        context("PPPOE"), "PPPOE", "example.com", 3
    )
    assert outcome.status == "FAIL"
    assert outcome.error_code == "PING_THRESHOLD_FAILED"
    assert observation(outcome, "pppoe.ping.packets_received") == 2
    assert observation(outcome, "pppoe.ping.loss_percent") == "33.33"
    assert len(outcome.artifacts) == 2


def test_registry_rejects_unknown_firmware_family() -> None:
    adapter = NeutralONUWebAdapter(lambda _context: FakeSurface())
    registry = ONUWebAdapterRegistry({"neutral-v1": adapter})
    assert registry.resolve("neutral-v1") is adapter
    with pytest.raises(UnknownONUWebAdapterError):
        registry.resolve("guessed-family")


def test_invalid_or_remote_management_url_is_blocked_before_browser_start() -> None:
    invalid = context()
    invalid = ActionContext(
        session_id=invalid.session_id,
        action_code=invalid.action_code,
        parameters={**invalid.parameters, "onu_web_url": "https://example.com"},
        secrets=invalid.secrets,
    )
    outcome = NeutralONUWebAdapter().capture_wan(invalid, "IPOE")
    assert outcome.status == "BLOCKED"
    assert outcome.error_code == "ONU_WEB_UNREACHABLE"


def test_compatibility_probe_checks_pages_without_running_ping() -> None:
    surface = FakeSurface()

    result = NeutralONUWebAdapter(
        lambda _context: surface
    ).check_compatibility(context())

    assert result.wan_outcome.status == "PASS"
    assert result.ping_page_outcome.status == "PASS"
    assert surface.opened_pages == ["wan", "ping"]
    assert surface.ping_controls_checked is True
    assert surface.ping_runs == 0
    assert {
        artifact.original_name
        for outcome in (result.wan_outcome, result.ping_page_outcome)
        for artifact in outcome.artifacts
    } == {
        "onu-wan-page.png",
        "onu-wan-page.txt",
        "onu-ping-page.png",
        "onu-ping-page.txt",
    }


def test_compatibility_probe_preserves_wan_when_ping_selector_is_missing() -> None:
    surface = FakeSurface(
        ping_control_error=ONUWebSelectorError("PING_TARGET")
    )

    result = NeutralONUWebAdapter(
        lambda _context: surface
    ).check_compatibility(context())

    assert result.wan_outcome.status == "PASS"
    assert result.ping_page_outcome.status == "BLOCKED"
    assert result.ping_page_outcome.error_code == "ONU_WEB_SELECTOR_UNSUPPORTED"
    assert {item.media_type for item in result.ping_page_outcome.artifacts} == {
        "image/png",
        "text/plain",
    }
    assert surface.ping_runs == 0


class _SensitiveControl:
    def __init__(self) -> None:
        self.value = "customer-secret"

    def fill(self, value: str) -> None:
        self.value = value


class _LocatorList:
    def __init__(self, controls: list[_SensitiveControl]) -> None:
        self.controls = controls

    def count(self) -> int:
        return len(self.controls)

    def nth(self, index: int) -> _SensitiveControl:
        return self.controls[index]


class _SensitivePage:
    def __init__(self) -> None:
        self.pppoe_password = _SensitiveControl()
        self.pppoe_username = _SensitiveControl()

    def locator(self, selector: str) -> _LocatorList:
        if selector == "input[type='password']":
            return _LocatorList([self.pppoe_password])
        if selector == "input[name*='user' i]":
            return _LocatorList([self.pppoe_username])
        return _LocatorList([])


def test_playwright_surface_masks_wan_credentials_before_screenshot() -> None:
    surface = NeutralPlaywrightSurface("http://192.168.1.1")
    wan_page = _SensitivePage()
    surface.page = wan_page
    surface.surface = wan_page

    surface.mask_sensitive_controls()

    assert wan_page.pppoe_password.value == "[REDACTED]"
    assert wan_page.pppoe_username.value == "[REDACTED]"
