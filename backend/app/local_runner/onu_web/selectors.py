from dataclasses import dataclass
from typing import Mapping

from app.diagnostics.adapters.huawei import HuaweiSelectorStrategy
from app.local_runner.onu_web.contracts import ONUWebAdapter


class UnknownONUWebAdapterError(Exception):
    pass


@dataclass(frozen=True)
class NeutralSelectorProfile:
    wan_navigation: tuple[str, ...] = (
        "a:has-text('WAN')",
        "a:has-text('Network')",
        "a[href*='wan' i]",
        "[onclick*='wan' i]",
    )
    diagnostics_navigation: tuple[str, ...] = HuaweiSelectorStrategy.DIAGNOSTICS_NAV
    wan_interface: tuple[str, ...] = HuaweiSelectorStrategy.WAN_INTERFACE
    ping_target: tuple[str, ...] = HuaweiSelectorStrategy.PING_TARGET
    ping_start: tuple[str, ...] = HuaweiSelectorStrategy.PING_START
    wan_fields: Mapping[str, tuple[str, ...]] = None

    def __post_init__(self):
        if self.wan_fields is None:
            object.__setattr__(self, "wan_fields", {
                "status": ("[data-field='status']", "#status", "[id*='status' i]"),
                "ip_address": ("[data-field='ip-address']", "#ipAddress", "[id*='ipaddr' i]"),
                "subnet_mask": ("[data-field='subnet-mask']", "#subnetMask", "[id*='mask' i]"),
                "gateway": ("[data-field='gateway']", "#gateway", "[id*='gateway' i]"),
                "primary_dns": ("[data-field='primary-dns']", "#primaryDns", "[id*='dns1' i]"),
                "vlan": ("[data-field='vlan']", "#vlanId", "[id*='vlan' i]"),
                "service_type": ("[data-field='service-type']", "#serviceType", "[id*='service' i]"),
            })


NEUTRAL_V1 = NeutralSelectorProfile()


class ONUWebAdapterRegistry:
    def __init__(self, adapters: Mapping[str, ONUWebAdapter]):
        self.adapters = dict(adapters)

    def resolve(self, adapter_key: str) -> ONUWebAdapter:
        try:
            return self.adapters[adapter_key]
        except KeyError as exception:
            raise UnknownONUWebAdapterError(adapter_key) from exception

