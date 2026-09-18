from app.local_runner.contracts import ActionHandler


class UnknownLocalActionError(Exception):
    pass


class DuplicateActionRegistrationError(Exception):
    pass


class LocalActionRegistry:
    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str], ActionHandler] = {}

    def register(
        self, plugin_code: str, action_code: str, handler: ActionHandler
    ) -> None:
        key = (plugin_code, action_code)
        if key in self._handlers:
            raise DuplicateActionRegistrationError(
                f"Action is already registered: {plugin_code}/{action_code}"
            )
        self._handlers[key] = handler

    def resolve(self, plugin_code: str, action_code: str) -> ActionHandler:
        try:
            return self._handlers[(plugin_code, action_code)]
        except KeyError as exception:
            raise UnknownLocalActionError(
                f"Action is not allow-listed: {plugin_code}/{action_code}"
            ) from exception

