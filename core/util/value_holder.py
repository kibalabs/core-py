import contextvars


class ValueHolder[T]:
    def __init__(self, value: T) -> None:
        super().__init__()
        self._value = value

    def get_value(self) -> T:
        return self._value


class SettableValueHolder[T](ValueHolder[T]):
    def __init__(self, value: T) -> None:
        super().__init__(value=value)

    def set_value(self, value: T) -> None:
        self._value = value


class ContextSettableValueHolder[T](ValueHolder[T]):
    def __init__(self, defaultValue: T) -> None:
        super().__init__(value=defaultValue)
        self._valueContext = contextvars.ContextVar[T]('_valueContext')

    def set_value(self, value: T) -> None:
        self._valueContext.set(value)

    def get_value(self) -> T:
        try:
            return self._valueContext.get()
        except LookupError:
            pass
        return super().get_value()


class RequestIdHolder(ContextSettableValueHolder[str | None]):
    def __init__(self, defaultValue: str | None = None, separator: str = '-') -> None:
        super().__init__(defaultValue=defaultValue)
        self.separator = separator
        self._requestCounterContext = contextvars.ContextVar[int]('_requestCounterContext')

    def set_value(self, value: str | None) -> None:
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
