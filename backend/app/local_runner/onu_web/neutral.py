from __future__ import annotations

from decimal import Decimal
from ipaddress import ip_address
import re
from typing import Callable
from urllib.parse import urlparse

from app.diagnostics.adapters.huawei import (
    HuaweiOutputError,
    HuaweiSelectorError,
    HuaweiSelectorStrategy,
    parse_huawei_ping_output,
)
from app.local_runner.contracts import (
    ActionContext,
    ActionOutcome,
    ArtifactPayload,
    Observation,
)
from app.local_runner.credentials import SecretValue
from app.local_runner.onu_web.contracts import (
    ONUWebAuthenticationError,
    ONUWebSelectorError,
    ONUWebSurface,
    ONUWebUnavailableError,
    ONUWebWanNotVisibleError,
    ONUWebCompatibilityResult,
)
from app.local_runner.onu_web.selectors import NEUTRAL_V1


_SECRET_FIELD = re.compile(
    r"(?i)((?:password|passwd|pwd|token|secret|loid|user(?:name)?)\s*[:=]\s*)(\S+)"
)


class NeutralONUWebAdapter:
    key = "neutral-v1"

    def __init__(
        self,
        surface_factory: Callable[[ActionContext], ONUWebSurface] | None = None,
    ) -> None:
        self.surface_factory = surface_factory or self._default_surface

    def capture_wan(self, context: ActionContext, wan_mode: str) -> ActionOutcome:
        mode = self._mode(wan_mode)
        surface = None
        try:
            surface = self.surface_factory(context)
            self._authenticate(surface, context)
            surface.open_wan_page()
            surface.select_wan(mode)
            fields = surface.read_wan_fields()
            if not fields or not fields.get("status"):
                raise ONUWebWanNotVisibleError(mode)
            prefix = mode.lower()
            observations = tuple(
                Observation(f"{prefix}.{key}", self._field_value(key, value), "ONU_WEB")
                for key, value in fields.items()
            )
            artifacts = self._capture_artifacts(surface, context, f"{prefix}-wan")
            return ActionOutcome("PASS", observations, artifacts)
        except ONUWebAuthenticationError:
            return ActionOutcome("BLOCKED", (), (), "ONU_WEB_CREDENTIAL_REJECTED")
        except ONUWebUnavailableError:
            return ActionOutcome("BLOCKED", (), (), "ONU_WEB_UNREACHABLE")
        except (ONUWebSelectorError, HuaweiSelectorError) as exception:
            stage = getattr(exception, "stage", "UNKNOWN")
            return ActionOutcome("BLOCKED", (), (), "ONU_WEB_SELECTOR_UNSUPPORTED", f"Selector stage: {stage}")
        except ONUWebWanNotVisibleError:
            return ActionOutcome("FAIL", (), (), "WAN_NOT_VISIBLE")
        finally:
            if surface is not None:
                surface.close()

    def run_ping(
        self,
        context: ActionContext,
        wan_mode: str,
        target: str,
        packet_count: int,
    ) -> ActionOutcome:
        mode = self._mode(wan_mode)
        if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", target):
            return ActionOutcome("BLOCKED", (), (), "INVALID_PING_TARGET")
        if not 1 <= packet_count <= 10:
            return ActionOutcome("BLOCKED", (), (), "INVALID_PACKET_COUNT")
        surface = None
        try:
            surface = self.surface_factory(context)
            self._authenticate(surface, context)
            surface.open_ping_page()
            surface.select_wan(mode)
            parsed = parse_huawei_ping_output(surface.run_ping(target, packet_count))
            prefix = mode.lower()
            observations = (
                Observation(f"{prefix}.ping.packets_sent", parsed.packets_sent, "ONU_WEB"),
                Observation(f"{prefix}.ping.packets_received", parsed.packets_received, "ONU_WEB"),
                Observation(f"{prefix}.ping.loss_percent", str(parsed.loss_percent), "ONU_WEB"),
                Observation(f"{prefix}.ping.latency_avg_ms", self._decimal(parsed.latency_avg_ms), "ONU_WEB"),
            )
            artifacts = self._capture_artifacts(surface, context, f"{prefix}-ping")
            return ActionOutcome(
                parsed.status,
                observations,
                artifacts,
                None if parsed.status == "PASS" else "PING_THRESHOLD_FAILED",
            )
        except ONUWebAuthenticationError:
            return ActionOutcome("BLOCKED", (), (), "ONU_WEB_CREDENTIAL_REJECTED")
        except ONUWebUnavailableError:
            return ActionOutcome("BLOCKED", (), (), "ONU_WEB_UNREACHABLE")
        except (ONUWebSelectorError, HuaweiSelectorError) as exception:
            stage = getattr(exception, "stage", "UNKNOWN")
            return ActionOutcome("BLOCKED", (), (), "ONU_WEB_SELECTOR_UNSUPPORTED", f"Selector stage: {stage}")
        except ONUWebWanNotVisibleError:
            return ActionOutcome("FAIL", (), (), "WAN_NOT_VISIBLE")
        except HuaweiOutputError as exception:
            return ActionOutcome("BLOCKED", (), (), "ONU_WEB_PING_OUTPUT_INCOMPLETE", str(exception))
        finally:
            if surface is not None:
                surface.close()

    def check_compatibility(
        self, context: ActionContext
    ) -> ONUWebCompatibilityResult:
        surface = None
        try:
            surface = self.surface_factory(context)
            self._authenticate(surface, context)
            try:
                surface.open_wan_page()
                wan = ActionOutcome(
                    "PASS",
                    (Observation("onu_web.wan_page_available", True, "ONU_WEB"),),
                    self._capture_artifacts(surface, context, "onu-wan-page"),
                )
            except (ONUWebSelectorError, HuaweiSelectorError) as exception:
                stage = getattr(exception, "stage", "WAN_NAVIGATION")
                wan = ActionOutcome(
                    "BLOCKED",
                    (),
                    self._capture_failure_artifacts(surface, context, "onu-wan-page-blocked"),
                    "ONU_WEB_SELECTOR_UNSUPPORTED",
                    f"Selector stage: {stage}",
                )
                return ONUWebCompatibilityResult(
                    wan,
                    ActionOutcome(
                        "BLOCKED", (), (), "ONU_WEB_PREREQUISITE_BLOCKED", "WAN page navigation failed"
                    ),
                )

            try:
                surface.open_ping_page()
                surface.assert_ping_controls()
                ping = ActionOutcome(
                    "PASS",
                    (Observation("onu_web.ping_page_available", True, "ONU_WEB"),),
                    self._capture_artifacts(surface, context, "onu-ping-page"),
                )
            except (ONUWebSelectorError, HuaweiSelectorError) as exception:
                stage = getattr(exception, "stage", "PING_PAGE")
                ping = ActionOutcome(
                    "BLOCKED",
                    (),
                    self._capture_failure_artifacts(surface, context, "onu-ping-page-blocked"),
                    "ONU_WEB_SELECTOR_UNSUPPORTED",
                    f"Selector stage: {stage}",
                )
            return ONUWebCompatibilityResult(wan, ping)
        except ONUWebAuthenticationError:
            blocked = ActionOutcome("BLOCKED", (), (), "ONU_WEB_CREDENTIAL_REJECTED")
            return ONUWebCompatibilityResult(blocked, blocked)
        except ONUWebUnavailableError:
            blocked = ActionOutcome("BLOCKED", (), (), "ONU_WEB_UNREACHABLE")
            return ONUWebCompatibilityResult(blocked, blocked)
        finally:
            if surface is not None:
                surface.close()

    @staticmethod
    def _mode(value: str) -> str:
        mode = value.upper()
        if mode not in {"IPOE", "PPPOE"}:
            raise ValueError("WAN mode must be IPOE or PPPOE")
        return mode

    @staticmethod
    def _authenticate(surface: ONUWebSurface, context: ActionContext) -> None:
        username = context.secrets.get("onu_web_username")
        password = context.secrets.get("onu_web_password")
        if username is None or password is None:
            raise ONUWebAuthenticationError("ONU Web credential is unavailable")
        surface.authenticate(username, password)

    def _capture_artifacts(
        self, surface: ONUWebSurface, context: ActionContext, stem: str
    ) -> tuple[ArtifactPayload, ArtifactPayload]:
        surface.mask_sensitive_controls()
        text = surface.page_text()
        for secret in context.secrets.values():
            text = text.replace(secret.reveal(), "[REDACTED]")
        text = _SECRET_FIELD.sub(r"\1[REDACTED]", text)
        return (
            ArtifactPayload(f"{stem}.png", "image/png", content=surface.screenshot(), redacted=True),
            ArtifactPayload(f"{stem}.txt", "text/plain", content=text.encode("utf-8"), redacted=True),
        )

    def _capture_failure_artifacts(
        self, surface: ONUWebSurface, context: ActionContext, stem: str
    ) -> tuple[ArtifactPayload, ...]:
        try:
            return self._capture_artifacts(surface, context, stem)
        except Exception:
            return ()

    @staticmethod
    def _field_value(key: str, value: str):
        stripped = value.strip()
        if key == "vlan" and stripped.isdigit():
            return int(stripped)
        return stripped

    @staticmethod
    def _decimal(value: Decimal | None) -> str | None:
        return str(value) if value is not None else None

    @staticmethod
    def _default_surface(context: ActionContext) -> ONUWebSurface:
        value = str(context.parameters.get("onu_web_url", "")).strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ONUWebUnavailableError("Invalid ONU Web URL")
        try:
            address = ip_address(parsed.hostname)
        except ValueError as exception:
            raise ONUWebUnavailableError("ONU Web host must be a local IP address") from exception
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ONUWebUnavailableError("ONU Web URL must be local")
        return NeutralPlaywrightSurface(value)


class NeutralPlaywrightSurface:
    def __init__(self, url: str):
        self.url = url
        self._playwright = None
        self._browser = None
        self.page = None
        self.surface = None

    def authenticate(self, username: SecretValue, password: SecretValue) -> None:
        try:
            from playwright.sync_api import sync_playwright

            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            self.page = self._browser.new_page(viewport={"width": 1920, "height": 1080})
            self.page.goto(self.url, wait_until="networkidle")
        except Exception as exception:
            self.close()
            raise ONUWebUnavailableError(str(exception)) from exception
        username_input = HuaweiSelectorStrategy.find_usable(self.page, HuaweiSelectorStrategy.LOGIN_USERNAME)
        if username_input is not None:
            username_input.fill(username.reveal())
            HuaweiSelectorStrategy.first_usable(
                self.page, HuaweiSelectorStrategy.LOGIN_PASSWORD, "LOGIN_PASSWORD"
            ).fill(password.reveal())
            HuaweiSelectorStrategy.first_usable(
                self.page, HuaweiSelectorStrategy.LOGIN_SUBMIT, "LOGIN_SUBMIT"
            ).click()
            self.page.wait_for_timeout(1500)
            if HuaweiSelectorStrategy.find_usable(self.page, HuaweiSelectorStrategy.LOGIN_PASSWORD) is not None:
                raise ONUWebAuthenticationError("Login page is still visible")
        self.surface = self.page.frame(name="contentIframe") or self.page

    def open_wan_page(self) -> None:
        try:
            HuaweiSelectorStrategy.first_usable(
                self.page, NEUTRAL_V1.wan_navigation, "WAN_NAVIGATION"
            ).click()
            self.page.wait_for_timeout(500)
            self.surface = self.page.frame(name="contentIframe") or self.page
        except HuaweiSelectorError as exception:
            raise ONUWebSelectorError(exception.stage, str(exception)) from exception

    def select_wan(self, wan_mode: str) -> None:
        try:
            HuaweiSelectorStrategy.select_wan_interface(self.surface, wan_mode)
        except HuaweiSelectorError as exception:
            if exception.stage == "WAN_INTERFACE_OPTION":
                raise ONUWebWanNotVisibleError(wan_mode) from exception
            raise ONUWebSelectorError(exception.stage, str(exception)) from exception

    def read_wan_fields(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for key, selectors in NEUTRAL_V1.wan_fields.items():
            locator = HuaweiSelectorStrategy.find_usable(self.surface, selectors)
            if locator is not None:
                try:
                    values[key] = locator.input_value().strip()
                except Exception:
                    values[key] = locator.inner_text().strip()
        return values

    def open_ping_page(self) -> None:
        try:
            HuaweiSelectorStrategy.first_usable(
                self.page, NEUTRAL_V1.diagnostics_navigation, "DIAGNOSTICS_NAV"
            ).click()
            self.page.wait_for_timeout(500)
            self.surface = self.page.frame(name="contentIframe") or self.page
        except HuaweiSelectorError as exception:
            raise ONUWebSelectorError(exception.stage, str(exception)) from exception

    def assert_ping_controls(self) -> None:
        try:
            HuaweiSelectorStrategy.first_usable(
                self.surface, NEUTRAL_V1.ping_target, "PING_TARGET"
            )
            HuaweiSelectorStrategy.first_usable(
                self.surface, NEUTRAL_V1.ping_start, "PING_START"
            )
        except HuaweiSelectorError as exception:
            raise ONUWebSelectorError(exception.stage, str(exception)) from exception

    def run_ping(self, target: str, packet_count: int) -> str:
        try:
            HuaweiSelectorStrategy.first_usable(
                self.surface, NEUTRAL_V1.ping_target, "PING_TARGET"
            ).fill(target)
            count = HuaweiSelectorStrategy.find_usable(
                self.surface, ("input[name*='count' i]", "select[name*='count' i]")
            )
            if count is not None:
                try:
                    count.fill(str(packet_count))
                except Exception:
                    count.select_option(str(packet_count))
            HuaweiSelectorStrategy.first_usable(
                self.surface, NEUTRAL_V1.ping_start, "PING_START"
            ).click()
            self.page.wait_for_timeout(6000)
            return self.page_text()
        except HuaweiSelectorError as exception:
            raise ONUWebSelectorError(exception.stage, str(exception)) from exception

    def mask_sensitive_controls(self) -> None:
        selectors = (
            *HuaweiSelectorStrategy.LOGIN_USERNAME,
            *HuaweiSelectorStrategy.LOGIN_PASSWORD,
            "input[type='password']",
            "input[name*='password' i]",
            "input[name*='passwd' i]",
            "input[name*='pwd' i]",
            "input[name*='token' i]",
            "input[name*='secret' i]",
            "input[name*='loid' i]",
            "input[name*='user' i]",
        )
        scopes = []
        for candidate in (self.page, self.surface):
            if candidate is not None and all(candidate is not scope for scope in scopes):
                scopes.append(candidate)
        for scope in scopes:
            for selector in selectors:
                try:
                    locators = scope.locator(selector)
                    for index in range(locators.count()):
                        locators.nth(index).fill("[REDACTED]")
                except Exception:
                    continue

    def page_text(self) -> str:
        return self.surface.locator("body").inner_text()

    def screenshot(self) -> bytes:
        return self.page.screenshot(full_page=True)

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
