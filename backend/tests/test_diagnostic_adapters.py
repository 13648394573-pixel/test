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
