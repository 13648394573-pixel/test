from collections.abc import Iterable, Mapping
from typing import Any

from app.diagnostics.contracts import PingAdapter


class AdapterMismatchError(Exception):
    pass


class AdapterRegistry:
    def __init__(self, adapters: Iterable[PingAdapter]) -> None:
        self._adapters = list(adapters)
        keys = [adapter.key for adapter in self._adapters]
        if len(keys) != len(set(keys)):
            raise ValueError("Diagnostic adapter keys must be unique")

    def match(
        self,
        device_snapshot: Mapping[str, Any],
        explicit_key: str | None = None,
    ) -> PingAdapter | None:
        if explicit_key is not None:
            adapter = next(
                (candidate for candidate in self._adapters if candidate.key == explicit_key),
                None,
            )
            if adapter is None or not adapter.supports(device_snapshot):
                raise AdapterMismatchError(explicit_key)
            return adapter
        return next(
            (adapter for adapter in self._adapters if adapter.supports(device_snapshot)),
            None,
        )
