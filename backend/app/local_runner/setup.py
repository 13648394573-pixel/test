"""Interactive credential enrollment; never contacts a device."""
import argparse
import getpass
import sys
from pathlib import Path
from typing import Callable, Sequence

from app.core.config import get_settings
from .configuration import RunnerConfig, load_runner_config
from .credentials import CredentialResolver, KeyringCredentialStore


class SetupEnrollmentError(ValueError):
    pass


def enroll_access(config: RunnerConfig, access_ref: str, resolver: CredentialResolver,
                  read_secret: Callable[[str], str]) -> None:
    pair = config.access_bindings.get(access_ref)
    if pair is None:
        raise SetupEnrollmentError('ACCESS_BINDING_UNAVAILABLE')
    references = (pair.username_ref, pair.password_ref)
    try:
        previous = [resolver.resolve(ref).reveal() if resolver.available(ref) else None
                    for ref in references]
        values = [read_secret('Username (hidden): '), read_secret('Password (hidden): ')]
        if not all(values):
            raise SetupEnrollmentError('EMPTY_CREDENTIAL')
    except Exception:
        raise SetupEnrollmentError('CREDENTIAL_INPUT_FAILED') from None
    try:
        for ref, value in zip(references, values):
            resolver.enroll(ref, value)
    except Exception:
        restored = True
        for ref, value in zip(references, previous):
            try:
                if value is None:
                    resolver.delete(ref)
                else:
                    resolver.enroll(ref, value)
            except Exception:
                restored = False
        raise SetupEnrollmentError('ENROLLMENT_FAILED' if restored
                                   else 'ENROLLMENT_FAILED_MANUAL_RECOVERY_REQUIRED') from None


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise SetupEnrollmentError('INVALID_SETUP_ARGUMENTS')


def main(argv: Sequence[str] | None = None) -> int:
    parser = SafeParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--access-ref', required=True)
    try:
        args = parser.parse_args(argv)
        if not sys.stdin.isatty():
            raise SetupEnrollmentError('INTERACTIVE_TERMINAL_REQUIRED')
        config = load_runner_config(Path(args.config))
        resolver = CredentialResolver(KeyringCredentialStore(), get_settings().credential_service_name)
        enroll_access(config, args.access_ref, resolver, getpass.getpass)
    except (ValueError, KeyboardInterrupt, EOFError):
        print('Credential enrollment failed; check local configuration and credential store.', file=sys.stderr)
        return 2
    print('Credential pair enrolled.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
