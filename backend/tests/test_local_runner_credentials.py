import pytest

from app.local_runner.credentials import (
    CredentialResolver,
    FakeCredentialStore,
    InvalidCredentialReferenceError,
    SecretValue,
    UnavailableCredentialError,
)


def test_secret_value_never_reveals_itself_in_text() -> None:
    secret = SecretValue("lab-value-123")
    assert "lab-value-123" not in repr(secret)
    assert "lab-value-123" not in str(secret)
    assert secret.reveal() == "lab-value-123"


def test_resolver_uses_reference_only_and_fake_store() -> None:
    store = FakeCredentialStore()
    resolver = CredentialResolver(store)
    resolver.enroll("olt.lab.primary", "lab-value-123")

    resolved = resolver.resolve("olt.lab.primary")
    assert resolved.reveal() == "lab-value-123"
    assert resolver.available("olt.lab.primary") is True
    resolver.delete("olt.lab.primary")
    with pytest.raises(UnavailableCredentialError):
        resolver.resolve("olt.lab.primary")


@pytest.mark.parametrize("reference", ["../olt", "olt account", "a/b", "line\nbreak", ""])
def test_resolver_rejects_unsafe_references(reference: str) -> None:
    with pytest.raises(InvalidCredentialReferenceError):
        CredentialResolver(FakeCredentialStore()).available(reference)

