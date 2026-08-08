import re
from collections.abc import Mapping
from decimal import Decimal
from ipaddress import ip_address
from typing import Any, Callable
from urllib.parse import urlparse

from app.diagnostics.contracts import (
    DiagnosticContext,
    PingExecutor,
    PingObservation,
    PingRequest,
)


class HuaweiOutputError(Exception):
    pass


class HuaweiExecutorConfigurationError(Exception):
    pass


_PACKETS = re.compile(
    r"sent\s*[=:]\s*(?P<sent>\d+)\s+received\s*[=:]\s*(?P<received>\d+)"
    r"\s+loss\s*[=:]\s*(?P<loss>\d+(?:\.\d+)?)%",
    re.IGNORECASE,
)
_LATENCY = re.compile(
    r"min\s*[=:]\s*(?P<min>\d+(?:\.\d+)?)ms\s+"
    r"avg\s*[=:]\s*(?P<avg>\d+(?:\.\d+)?)ms\s+"
    r"max\s*[=:]\s*(?P<max>\d+(?:\.\d+)?)ms",
    re.IGNORECASE,
)
_SECRET = re.compile(r"(?i)(password\s*[=:]\s*)([^\s&]+)")


class HuaweiWebPingExecutor:
    def __init__(
        self,
        username: str,
        password: str,
        *,
        runner: Callable[[str, str, str, str, PingRequest], str] | None = None,
    ) -> None:
        self.username = username
        self.password = password
        self.runner = runner or self._playwright_runner

    def __call__(self, context: DiagnosticContext, request: PingRequest) -> str:
        url = self._management_url(context.environment_snapshot)
        return self.runner(url, self.username, self.password, context.wan_mode, request)

    @staticmethod
    def _management_url(snapshot: Mapping[str, Any] | None) -> str:
        parameters = snapshot.get("parameters", []) if snapshot else []
        value = next(
            (
                str(item.get("param_value", "")).strip()
                for item in parameters
                if item.get("param_key") == "onu_management_url"
            ),
            "",
        )
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise HuaweiExecutorConfigurationError("Valid onu_management_url is required")
        try:
            address = ip_address(parsed.hostname)
        except ValueError as exception:
            raise HuaweiExecutorConfigurationError("ONU management host must be an IP address") from exception
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise HuaweiExecutorConfigurationError("ONU management address must be local")
        return value.rstrip("/")

    @staticmethod
    def _playwright_runner(
        url: str,
        username: str,
        password: str,
        wan_mode: str,
        request: PingRequest,
    ) -> str:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1920, "height": 1080})
                page.goto(url, wait_until="networkidle")
                username_input = page.locator("#username, input[name='username']").first
                if username_input.count() and username_input.is_visible():
                    if not username or not password:
                        raise HuaweiExecutorConfigurationError("Huawei Web credentials are required")
                    username_input.fill(username)
                    page.locator("#password, input[name='password']").first.fill(password)
                    page.locator("#loginBtn, input[type='submit'], button[type='submit']").first.click()
                    page.wait_for_timeout(1500)
                page.locator("a:has-text('Diagnostics'), a:has-text('诊断')").first.click()
                page.wait_for_timeout(500)
                surface = page.frame(name="contentIframe") or page
                wan_select = surface.locator("select[name*='wan' i], select[id*='wan' i]").first
                if wan_select.count():
                    try:
                        wan_select.select_option(label=wan_mode)
                    except Exception:
                        wan_select.select_option(value=wan_mode)
                surface.locator("input[type='text']").first.fill(request.target)
                surface.locator("input[value='Start'], button:has-text('Start'), button:has-text('开始')").first.click()
                page.wait_for_timeout((request.timeout_seconds + 1) * 1000)
                return surface.locator("body").inner_text()
            finally:
                browser.close()


class HuaweiPingAdapter:
    key = "huawei-ping"
    version = "1"

    def __init__(self, executor: PingExecutor) -> None:
        self._executor = executor

    def supports(self, device_snapshot: Mapping[str, Any]) -> bool:
        return str(device_snapshot.get("vendor", "")).strip().casefold() == "huawei"

    def ping(self, context: DiagnosticContext, request: PingRequest) -> PingObservation:
        raw_output = _SECRET.sub(r"\1[REDACTED]", self._executor(context, request))[:65536]
        packet_match = _PACKETS.search(raw_output)
        if packet_match is None:
            raise HuaweiOutputError("Huawei Ping output is not complete")
        sent = int(packet_match.group("sent"))
        received = int(packet_match.group("received"))
        loss = Decimal(packet_match.group("loss"))
        latency_match = _LATENCY.search(raw_output)
        latency = (
            (
                Decimal(latency_match.group("min")),
                Decimal(latency_match.group("avg")),
                Decimal(latency_match.group("max")),
            )
            if latency_match
            else (None, None, None)
        )
        return PingObservation(
            status="PASS" if sent > 0 and received == sent and loss == 0 else "FAIL",
            packets_sent=sent,
            packets_received=received,
            loss_percent=loss,
            latency_min_ms=latency[0],
            latency_avg_ms=latency[1],
            latency_max_ms=latency[2],
            raw_output=raw_output,
        )
