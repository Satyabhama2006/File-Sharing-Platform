from database import save_event


class EventSystem:

    def __init__(self):
        self.handlers = {}


    def subscribe(self, event_type, handler):

        if event_type not in self.handlers:
            self.handlers[event_type] = []

        self.handlers[event_type].append(handler)


    def publish(
        self,
        event_type,
        file_id=None,
        message=""
    ):

        save_event(
            event_type,
            file_id,
            message
        )

        print(
            f"[EVENT] {event_type} | "
            f"{file_id} | {message}"
        )

        if event_type in self.handlers:

            for handler in self.handlers[event_type]:
                handler(
                    event_type,
                    file_id,
                    message
                )


event_system = EventSystem()