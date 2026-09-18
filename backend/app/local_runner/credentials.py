from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol


REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


class InvalidCredentialReferenceError(Exception):
    pass


class UnavailableCredentialError(Exception):
    pass


@dataclass(frozen=True, repr=False)
class SecretValue:
    _value: str

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue([REDACTED])"

    def __str__(self) -> str:
        return "[REDACTED]"


class CredentialStore(Protocol):
    def get_password(self, service_name: str, reference: str) -> str | None: ...

    def set_password(
        self, service_name: str, reference: str, value: str
    ) -> None: ...

    def delete_password(self, service_name: str, reference: str) -> None: ...


class KeyringCredentialStore:
    def get_password(self, service_name: str, reference: str) -> str | None:
        import keyring

        return keyring.get_password(service_name, reference)

    def set_password(self, service_name: str, reference: str, value: str) -> None:
        import keyring

        keyring.set_password(service_name, reference, value)

    def delete_password(self, service_name: str, reference: str) -> None:
        import keyring
        from keyring.errors import PasswordDeleteError

        try:
            keyring.delete_password(service_name, reference)
        except PasswordDeleteError:
            return


class FakeCredentialStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, service_name: str, reference: str) -> str | None:
        return self.values.get((service_name, reference))

    def set_password(self, service_name: str, reference: str, value: str) -> None:
        self.values[(service_name, reference)] = value

    def delete_password(self, service_name: str, reference: str) -> None:
        self.values.pop((service_name, reference), None)


class CredentialResolver:
    def __init__(
        self,
        store: CredentialStore,
        service_name: str = "ONU Test Workbench",
    ) -> None:
        self.store = store
        self.service_name = service_name

    def resolve(self, reference: str) -> SecretValue:
        self._validate(reference)
        value = self.store.get_password(self.service_name, reference)
        if value is None:
            raise UnavailableCredentialError(reference)
        return SecretValue(value)

    def enroll(self, reference: str, value: str) -> None:
        self._validate(reference)
        if not value:
            raise ValueError("Credential value is required")
        self.store.set_password(self.service_name, reference, value)

    def available(self, reference: str) -> bool:
        self._validate(reference)
        return self.store.get_password(self.service_name, reference) is not None

    def delete(self, reference: str) -> None:
        self._validate(reference)
        self.store.delete_password(self.service_name, reference)

    @staticmethod
    def _validate(reference: str) -> None:
        if not REFERENCE_PATTERN.fullmatch(reference):
            raise InvalidCredentialReferenceError(reference)

