from typing import Protocol

from app.local_runner.contracts import ActionContext, ActionOutcome
from app.local_runner.credentials import SecretValue


class ONUWebAuthenticationError(Exception):
    pass


class ONUWebUnavailableError(Exception):
    pass


class ONUWebSelectorError(Exception):
    def __init__(self, stage: str, detail: str | None = None):
        self.stage = stage
        self.detail = detail
        super().__init__(f"ONU Web selector failed at {stage}" + (f": {detail}" if detail else ""))


class ONUWebWanNotVisibleError(Exception):
    pass


class ONUWebSurface(Protocol):
    def authenticate(self, username: SecretValue, password: SecretValue) -> None: ...
    def open_wan_page(self) -> None: ...
    def select_wan(self, wan_mode: str) -> None: ...
    def read_wan_fields(self) -> dict[str, str]: ...
    def open_ping_page(self) -> None: ...
    def run_ping(self, target: str, packet_count: int) -> str: ...
    def mask_sensitive_controls(self) -> None: ...
    def page_text(self) -> str: ...
    def screenshot(self) -> bytes: ...
    def close(self) -> None: ...


class ONUWebAdapter(Protocol):
    def capture_wan(self, context: ActionContext, wan_mode: str) -> ActionOutcome: ...
    def run_ping(
        self,
        context: ActionContext,
        wan_mode: str,
        target: str,
        packet_count: int,
    ) -> ActionOutcome: ...

