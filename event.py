from typing import List, Callable, TypeVar, Generic


T = TypeVar("T")


class Event(Generic[T]):
    EventHandler = Callable[[object, T], None]

    def __init__(self):
        self.subscribers: List[Event.EventHandler] = []

    def __add__(self, other: EventHandler):
        self.add(other)
        return self

    def __sub__(self, other: EventHandler):
        self.remove(other)
        return self

    def add(self, handler: EventHandler):
        self.subscribers.append(handler)

    def remove(self, handler: EventHandler):
        self.subscribers.remove(handler)

    def invoke(self, sender: object, event_args: T) -> None:
        for subscriber in self.subscribers:
            subscriber(sender, event_args)

    def bind_invoke(self, sender: object, event_args: T) -> Callable[[object, T], None]:
        return lambda: self.invoke(sender, event_args)

    def bind_invoke_empty(self, sender: object, event_args: T) -> Callable[[object, T], None]:
        return lambda *_: self.invoke(sender, event_args)
