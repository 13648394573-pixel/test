from decimal import Decimal

import pytest


def test_registry_matches_huawei_device_case_insensitively() -> None:
    from app.diagnostics.adapters.huawei import HuaweiPingAdapter
    from app.diagnostics.registry import AdapterRegistry

    adapter = HuaweiPingAdapter(lambda _context, _request: "sent=3 received=3 loss=0% avg=1.2ms")
    registry = AdapterRegistry([adapter])

    assert registry.match({"vendor": "HUAWEI", "model": "HG8245"}) is adapter
    assert registry.match({"vendor": "Other", "model": "HG8245"}) is None


def test_registry_rejects_explicit_adapter_that_does_not_support_device() -> None:
    from app.diagnostics.adapters.huawei import HuaweiPingAdapter
    from app.diagnostics.registry import AdapterMismatchError, AdapterRegistry

    registry = AdapterRegistry([HuaweiPingAdapter(lambda _context, _request: "")])
    with pytest.raises(AdapterMismatchError):
        registry.match({"vendor": "ZTE", "model": "F660"}, "huawei-ping")


def test_huawei_adapter_parses_success_and_passes_wan_mode() -> None:
    from app.diagnostics.adapters.huawei import HuaweiPingAdapter
    from app.diagnostics.contracts import DiagnosticContext, PingRequest

    captured = {}

    def execute(context, request):
        captured["wan_mode"] = context.wan_mode
        captured["target"] = request.target
        return "sent=3 received=3 loss=0% min=1.0ms avg=1.5ms max=2.0ms"

    observation = HuaweiPingAdapter(execute).ping(
        DiagnosticContext({"vendor": "Huawei"}, None, "PPPOE"),
        PingRequest("DOMAIN", "example.com", 3, 5),
    )

    assert captured == {"wan_mode": "PPPOE", "target": "example.com"}
    assert observation.status == "PASS"
    assert observation.packets_received == 3
    assert observation.loss_percent == Decimal("0")
    assert observation.latency_avg_ms == Decimal("1.5")


def test_huawei_ping_parser_is_reusable_by_local_runner() -> None:
    from app.diagnostics.adapters.huawei import parse_huawei_ping_output

    observation = parse_huawei_ping_output(
        "sent=4 received=4 loss=0% min=2ms avg=3ms max=5ms"
    )
    assert observation.status == "PASS"
    assert observation.packets_sent == 4
    assert observation.latency_avg_ms == Decimal("3")


def test_huawei_adapter_marks_packet_loss_failed_and_redacts_credentials() -> None:
    from app.diagnostics.adapters.huawei import HuaweiPingAdapter
    from app.diagnostics.contracts import DiagnosticContext, PingRequest

    output = "username=admin password=secret sent=3 received=0 loss=100%"
    observation = HuaweiPingAdapter(lambda _context, _request: output).ping(
        DiagnosticContext({"vendor": "Huawei"}, None, "IPOE"),
        PingRequest("PUBLIC_IP", "1.1.1.1", 3, 5),
    )

    assert observation.status == "FAIL"
    assert observation.packets_received == 0
    assert "secret" not in observation.raw_output
    assert "password=[REDACTED]" in observation.raw_output


def test_huawei_adapter_rejects_unparseable_output() -> None:
    from app.diagnostics.adapters.huawei import HuaweiOutputError, HuaweiPingAdapter
    from app.diagnostics.contracts import DiagnosticContext, PingRequest

    with pytest.raises(HuaweiOutputError):
        HuaweiPingAdapter(lambda _context, _request: "pending").ping(
            DiagnosticContext({"vendor": "Huawei"}, None, "IPOE"),
            PingRequest("GATEWAY", "192.168.1.1", 3, 5),
        )


def test_huawei_adapter_parses_busybox_packet_summary() -> None:
    from app.diagnostics.adapters.huawei import HuaweiPingAdapter
    from app.diagnostics.contracts import DiagnosticContext, PingRequest

    output = "3 packets transmitted, 3 packets received."
    observation = HuaweiPingAdapter(lambda _context, _request: output).ping(
        DiagnosticContext({"vendor": "Huawei"}, None, "IPOE"),
        PingRequest("PUBLIC_IP", "1.1.1.1", 3, 5),
    )

    assert observation.status == "PASS"
    assert observation.packets_sent == 3
    assert observation.packets_received == 3
    assert observation.loss_percent == Decimal("0")


class _LocatorStub:
    def __init__(self, *, visible=False, enabled=True):
        self.visible = visible
        self.enabled = enabled

    @property
    def first(self):
        return self

    def count(self):
        return 1

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled


class _SurfaceStub:
    def __init__(self, locators):
        self.locators = locators

    def locator(self, selector):
        return self.locators.get(selector, _LocatorStub())


def test_huawei_selector_strategy_uses_first_usable_candidate() -> None:
    from app.diagnostics.adapters.huawei import HuaweiSelectorStrategy

    hidden = _LocatorStub(visible=False)
    visible = _LocatorStub(visible=True)
    surface = _SurfaceStub({"#fixed": hidden, "input[name='pingAddr']": visible})

    selected = HuaweiSelectorStrategy.first_usable(
        surface,
        ("#fixed", "input[name='pingAddr']"),
        "PING_TARGET",
    )

    assert selected is visible


def test_huawei_selector_strategy_returns_explicit_stage_error() -> None:
    from app.diagnostics.adapters.huawei import (
        HuaweiSelectorError,
        HuaweiSelectorStrategy,
    )

    with pytest.raises(HuaweiSelectorError, match="PING_START") as captured:
        HuaweiSelectorStrategy.first_usable(
            _SurfaceStub({}),
            ("#start", "input[value='Go']"),
            "PING_START",
        )

    assert captured.value.stage == "PING_START"


def test_huawei_selector_strategy_maps_wan_mode_to_interface_option() -> None:
    from app.diagnostics.adapters.huawei import HuaweiSelectorStrategy

    options = [("65535", "Any"), ("65536", "ppp0"), ("130817", "nas0_1")]

    assert HuaweiSelectorStrategy.choose_wan_option(options, "PPPOE") == "65536"
    assert HuaweiSelectorStrategy.choose_wan_option(options, "IPOE") == "130817"


def test_huawei_selector_strategy_rejects_non_internet_ipoe_options() -> None:
    from app.diagnostics.adapters.huawei import (
        HuaweiSelectorError,
        HuaweiSelectorStrategy,
    )

    options = [
        ("1", "Any"),
        ("2", "ppp0"),
        ("3", "TR069"),
        ("4", "VoIP"),
        ("5", "IPTV"),
    ]

    with pytest.raises(HuaweiSelectorError) as captured:
        HuaweiSelectorStrategy.choose_wan_option(options, "IPOE")

    assert captured.value.stage == "WAN_INTERFACE_OPTION"


def test_huawei_selector_strategy_does_not_use_arbitrary_text_input() -> None:
    from app.diagnostics.adapters.huawei import (
        HuaweiSelectorError,
        HuaweiSelectorStrategy,
    )

    surface = _SurfaceStub({"input[type='text']": _LocatorStub(visible=True)})

    with pytest.raises(HuaweiSelectorError):
        HuaweiSelectorStrategy.first_usable(
            surface,
            HuaweiSelectorStrategy.PING_TARGET,
            "PING_TARGET",
        )


def test_huawei_web_executor_rejects_management_url_userinfo() -> None:
    from app.diagnostics.adapters.huawei import (
        HuaweiExecutorConfigurationError,
        HuaweiWebPingExecutor,
    )
    from app.diagnostics.contracts import DiagnosticContext, PingRequest

    executor = HuaweiWebPingExecutor(
        "operator",
        "local-secret",
        runner=lambda *_args: "sent=3 received=3 loss=0%",
    )

    with pytest.raises(HuaweiExecutorConfigurationError):
        executor(
            DiagnosticContext(
                {"vendor": "Huawei"},
                {"parameters": [{
                    "param_key": "onu_management_url",
                    "param_value": "http://operator:secret@192.168.1.1",
                }]},
                "IPOE",
            ),
            PingRequest("GATEWAY", "192.168.87.1", 3, 5),
        )


def test_huawei_web_executor_uses_environment_management_url_and_wan() -> None:
    from app.diagnostics.adapters.huawei import HuaweiWebPingExecutor
    from app.diagnostics.contracts import DiagnosticContext, PingRequest

    captured = {}

    def runner(url, username, password, wan_mode, request):
        captured.update(
            url=url, username=username, password=password,
            wan_mode=wan_mode, target=request.target,
        )
        return "sent=3 received=3 loss=0%"

    executor = HuaweiWebPingExecutor("operator", "local-secret", runner=runner)
    output = executor(
        DiagnosticContext(
            {"vendor": "Huawei"},
            {"parameters": [{
                "param_key": "onu_management_url",
                "param_value": "http://192.168.1.1",
            }]},
            "PPPOE",
        ),
        PingRequest("DOMAIN", "example.com", 3, 5),
    )

    assert output == "sent=3 received=3 loss=0%"
    assert captured == {
        "url": "http://192.168.1.1",
        "username": "operator",
        "password": "local-secret",
        "wan_mode": "PPPOE",
        "target": "example.com",
    }
