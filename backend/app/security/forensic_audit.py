
from datetime import datetime

class ForensicAuditLogger:

    def create_entry(
        self,
        actor,
        action,
        metadata=None
    ):

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "actor": actor,
            "action": action,
            "metadata": metadata or {}
        }
