
class ApprovalSystem:

    def approve(
        self,
        actor,
        process_id
    ):

        return {
            "approved_by": actor,
            "process_id": process_id,
            "approved": True
        }
