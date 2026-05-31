
import hashlib

class ImmutableHashChain:

    def hash_record(self, content: str):

        return hashlib.sha256(
            content.encode()
        ).hexdigest()
