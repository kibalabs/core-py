import contextvars
from typing import Generic
from typing import Optional
from typing import TypeVar

T = TypeVar('T')


class ValueHolder(Generic[T]):

    def __init__(self, value: T) -> None:
        super().__init__()
        self._value = value

    def get_value(self) -> T:
        return self._value


class SettableValueHolder(ValueHolder[T]):

    def __init__(self, value: T) -> None:
        super().__init__(value=value)

    def set_value(self, value: T) -> None:
        self._value = value


class ContextSettableValueHolder(ValueHolder[T]):

    def __init__(self, defaultValue: T) -> None:
        super().__init__(value=defaultValue)
        self._valueContext = contextvars.ContextVar[T]("_valueContext")

    def set_value(self, value: T) -> None:
        self._valueContext.set(value)

    def get_value(self) -> T:
        try:
            return self._valueContext.get()
        except LookupError:
            pass
        return super().get_value()


class RequestIdHolder(ContextSettableValueHolder[Optional[str]]):

    def __init__(self, defaultValue: Optional[str] = None, separator: str = '-') -> None:
        super().__init__(defaultValue=defaultValue)
        self.separator = separator
        self._requestCounterContext = contextvars.ContextVar[int]("_requestCounterContext")

    def set_value(self, value: Optional[str]) -> None:
        super().set_value(value=value)
        self._requestCounterContext.set(0)

    def get_request_id(self, shouldIncrementCounter: bool = True) -> str:
        requestCounterValue = self._requestCounterContext.get()
        requestId = f'{super().get_value()}{self.separator}{requestCounterValue}'
        if shouldIncrementCounter:
            self.increment_request_counter()
        return requestId

    def increment_request_counter(self) -> None:
        self._requestCounterContext.set(self._requestCounterContext.get() + 1)
