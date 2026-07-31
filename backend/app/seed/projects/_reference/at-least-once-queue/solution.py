class MessageQueue:
    """An at-least-once queue with visibility timeouts and a DLQ."""

    def __init__(self, visibility_timeout: float = 30, max_receives: int = 3):
        self.visibility_timeout = visibility_timeout
        self.max_receives = max_receives
        self.messages: list[dict] = []
        self.dead_letters: list[dict] = []
        self._next_id = 1

    def publish(self, body) -> int:
        message_id = self._next_id
        self._next_id += 1
        self.messages.append(
            {"id": message_id, "body": body, "visible_at": 0, "receives": 0}
        )
        return message_id

    def receive(self, now: float):
        self._retire_exhausted(now)
        for message in self.messages:
            if message["visible_at"] > now:
                continue
            message["receives"] += 1
            message["visible_at"] = now + self.visibility_timeout
            return message["id"], message["body"]
        return None

    def ack(self, message_id: int) -> None:
        self.messages = [m for m in self.messages if m["id"] != message_id]

    def _retire_exhausted(self, now: float) -> None:
        """Move messages that came back one time too many to the DLQ.

        The check happens when a message becomes visible again: at that point
        it has been delivered `max_receives` times and never acked, so a
        further delivery would just block the queue behind it.
        """
        live = []
        for message in self.messages:
            exhausted = (
                message["receives"] >= self.max_receives
                and message["visible_at"] <= now
            )
            if exhausted:
                self.dead_letters.append(message)
            else:
                live.append(message)
        self.messages = live
