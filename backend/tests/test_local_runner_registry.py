import pytest

from app.local_runner.contracts import ActionContext, ActionOutcome
from app.local_runner.registry import (
    DuplicateActionRegistrationError,
    LocalActionRegistry,
    UnknownLocalActionError,
)


class PassingHandler:
    def execute(self, context: ActionContext) -> ActionOutcome:
        return ActionOutcome(status="PASS", observations=(), artifacts=())


def test_registry_resolves_only_exact_allow_list_matches(tmp_path) -> None:
    registry = LocalActionRegistry()
    handler = PassingHandler()
    registry.register("onu-local", "preflight", handler)

    assert registry.resolve("onu-local", "preflight") is handler
    with pytest.raises(UnknownLocalActionError):
        registry.resolve("onu-local", "preflight; erase")
    with pytest.raises(UnknownLocalActionError):
        registry.resolve("other", "preflight")


def test_registry_rejects_duplicate_action_identity() -> None:
    registry = LocalActionRegistry()
    registry.register("onu-local", "preflight", PassingHandler())

    with pytest.raises(DuplicateActionRegistrationError):
        registry.register("onu-local", "preflight", PassingHandler())

