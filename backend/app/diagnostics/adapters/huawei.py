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


class HuaweiSelectorError(Exception):
    def __init__(
        self,
        stage: str,
        selectors: tuple[str, ...],
        detail: str | None = None,
    ) -> None:
        self.stage = stage
        self.selectors = selectors
        message = f"Huawei selector stage {stage} failed"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)


_PACKETS = re.compile(
    r"sent\s*[=:]\s*(?P<sent>\d+)\s+received\s*[=:]\s*(?P<received>\d+)"
    r"\s+loss\s*[=:]\s*(?P<loss>\d+(?:\.\d+)?)%",
    re.IGNORECASE,
)
_BUSYBOX_PACKETS = re.compile(
    r"(?P<sent>\d+)\s+packets?\s+transmitted,\s*"
    r"(?P<received>\d+)\s+packets?\s+received",
    re.IGNORECASE,
)
_LATENCY = re.compile(
    r"min\s*[=:]\s*(?P<min>\d+(?:\.\d+)?)ms\s+"
    r"avg\s*[=:]\s*(?P<avg>\d+(?:\.\d+)?)ms\s+"
    r"max\s*[=:]\s*(?P<max>\d+(?:\.\d+)?)ms",
    re.IGNORECASE,
)
_BUSYBOX_LATENCY = re.compile(
    r"(?:round-trip|rtt)[^=]*=\s*"
    r"(?P<min>\d+(?:\.\d+)?)/(?P<avg>\d+(?:\.\d+)?)/"
    r"(?P<max>\d+(?:\.\d+)?)\s*ms",
    re.IGNORECASE,
)
_SECRET = re.compile(r"(?i)(password\s*[=:]\s*)([^\s&]+)")


class HuaweiSelectorStrategy:
    LOGIN_USERNAME = ("#username", "input[name='username']")
    LOGIN_PASSWORD = ("#password", "input[name='password']")
    LOGIN_SUBMIT = (
        "#loginBtn",
        "button[type='submit']",
        "input[type='submit']",
    )
    DIAGNOSTICS_NAV = (
        "a:has-text('Diagnostics')",
        "a:has-text('诊断')",
        "a[href*='ping' i]",
        "[onclick*='ping' i]",
    )
    WAN_INTERFACE = (
        "select[name='wanif']",
        "select[name*='wan' i]",
        "select[id*='wan' i]",
        "select[name*='interface' i]",
    )
    PING_TARGET = (
        "input[name='pingAddr']",
        "input[name*='ping' i][name*='addr' i]",
        "input[name*='target' i]",
        "input[id*='ping' i][type='text']",
    )
    PING_START = (
        "input[type='submit'][value*='Go' i]",
        "input[type='submit'][value*='Start' i]",
        "button:has-text('Start')",
        "button:has-text('开始')",
        "button[name*='ping' i]",
    )

    @classmethod
    def find_usable(cls, surface: Any, selectors: tuple[str, ...]):
        for selector in selectors:
            try:
                locator = surface.locator(selector).first
                if locator.count() and locator.is_visible() and locator.is_enabled():
                    return locator
            except Exception:
                continue
        return None

    @classmethod
    def first_usable(
        cls,
        surface: Any,
        selectors: tuple[str, ...],
        stage: str,
    ):
        locator = cls.find_usable(surface, selectors)
        if locator is None:
            raise HuaweiSelectorError(stage, selectors, "no visible enabled control")
        return locator

    @staticmethod
    def choose_wan_option(options: list[tuple[str, str]], wan_mode: str) -> str:
        normalized = [
            (value, f"{value} {label}".strip().casefold())
            for value, label in options
        ]
        if wan_mode == "PPPOE":
            match = next(
                (value for value, text in normalized if "ppp" in text),
                None,
            )
        else:
            match = next(
                (
                    value
                    for value, text in normalized
                    if any(
                        marker in text
                        for marker in ("ipoe", "dhcp", "nas", "veip")
                    )
                    and "ppp" not in text
                ),
                None,
            )
        if match is None:
            raise HuaweiSelectorError(
                "WAN_INTERFACE_OPTION",
                tuple(label for _value, label in options),
                f"no option matches {wan_mode}",
            )
        return match

    @classmethod
    def select_wan_interface(cls, surface: Any, wan_mode: str) -> None:
        selector = cls.first_usable(
            surface,
            cls.WAN_INTERFACE,
            "WAN_INTERFACE",
        )
        option_locators = selector.locator("option")
        options = [
            (
                option_locators.nth(index).get_attribute("value") or "",
                option_locators.nth(index).inner_text().strip(),
            )
            for index in range(option_locators.count())
        ]
        value = cls.choose_wan_option(options, wan_mode)
        try:
            selector.select_option(value=value)
        except Exception as exception:
            raise HuaweiSelectorError(
                "WAN_INTERFACE",
                cls.WAN_INTERFACE,
                "matching option could not be selected",
            ) from exception


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
            raise HuaweiExecutorConfigurationError(
                "Valid onu_management_url is required"
            )
        if parsed.username is not None or parsed.password is not None:
            raise HuaweiExecutorConfigurationError(
                "ONU management URL must not contain credentials"
            )
        try:
            address = ip_address(parsed.hostname)
        except ValueError as exception:
            raise HuaweiExecutorConfigurationError(
                "ONU management host must be an IP address"
            ) from exception
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise HuaweiExecutorConfigurationError(
                "ONU management address must be local"
            )
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
                username_input = HuaweiSelectorStrategy.find_usable(
                    page,
                    HuaweiSelectorStrategy.LOGIN_USERNAME,
                )
                if username_input is not None:
                    if not username or not password:
                        raise HuaweiExecutorConfigurationError(
                            "Huawei Web credentials are required"
                        )
                    username_input.fill(username)
                    HuaweiSelectorStrategy.first_usable(
                        page,
                        HuaweiSelectorStrategy.LOGIN_PASSWORD,
                        "LOGIN_PASSWORD",
                    ).fill(password)
                    HuaweiSelectorStrategy.first_usable(
                        page,
                        HuaweiSelectorStrategy.LOGIN_SUBMIT,
                        "LOGIN_SUBMIT",
                    ).click()
                    page.wait_for_timeout(1500)
                HuaweiSelectorStrategy.first_usable(
                    page,
                    HuaweiSelectorStrategy.DIAGNOSTICS_NAV,
                    "DIAGNOSTICS_NAV",
                ).click()
                page.wait_for_timeout(500)
                surface = page.frame(name="contentIframe") or page
                HuaweiSelectorStrategy.select_wan_interface(surface, wan_mode)
                HuaweiSelectorStrategy.first_usable(
                    surface,
                    HuaweiSelectorStrategy.PING_TARGET,
                    "PING_TARGET",
                ).fill(request.target)
                HuaweiSelectorStrategy.first_usable(
                    surface,
                    HuaweiSelectorStrategy.PING_START,
                    "PING_START",
                ).click()
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
        raw_output = _SECRET.sub(
            r"\1[REDACTED]",
            self._executor(context, request),
        )[:65536]
        packet_match = _PACKETS.search(raw_output)
        if packet_match is not None:
            sent = int(packet_match.group("sent"))
            received = int(packet_match.group("received"))
            loss = Decimal(packet_match.group("loss"))
        else:
            busybox_match = _BUSYBOX_PACKETS.search(raw_output)
            if busybox_match is None:
                raise HuaweiOutputError("Huawei Ping output is not complete")
            sent = int(busybox_match.group("sent"))
            received = int(busybox_match.group("received"))
            loss = (
                (
                    Decimal(sent - received)
                    * Decimal("100")
                    / Decimal(sent)
                ).quantize(Decimal("0.01"))
                if sent
                else Decimal("100")
            )
        latency_match = _LATENCY.search(raw_output) or _BUSYBOX_LATENCY.search(
            raw_output
        )
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
