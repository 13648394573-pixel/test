from .configuration import RunnerConfig
from .credentials import CredentialResolver, SecretValue, UnavailableCredentialError


class PairedAccessResolver:
    def __init__(self, config: RunnerConfig, resolver: CredentialResolver):
        self.config = config
        self.resolver = resolver

    def available(self, reference: str) -> bool:
        pair = self.config.access_bindings.get(reference)
        return bool(pair and self.resolver.available(pair.username_ref)
                    and self.resolver.available(pair.password_ref))

    def resolve(self, reference: str, expected_kind: str) -> tuple[SecretValue, SecretValue]:
        pair = self.config.access_bindings.get(reference)
        if pair is None or pair.kind != expected_kind:
            raise UnavailableCredentialError('ACCESS_BINDING_UNAVAILABLE')
        return self.resolver.resolve(pair.username_ref), self.resolver.resolve(pair.password_ref)
