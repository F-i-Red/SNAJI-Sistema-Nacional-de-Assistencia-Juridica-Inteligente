
class APIHardening:

    BLOCKED_PATTERNS = [
        "DROP TABLE",
        "DELETE FROM",
        "--",
        ";"
    ]

    def inspect(self, payload: str):

        for pattern in self.BLOCKED_PATTERNS:

            if pattern.lower() in payload.lower():
                return False

        return True
