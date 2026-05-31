
class WorkflowEngine:

    def next_stage(self, process_state):

        return {
            "current_stage": "analysis",
            "next_stage": "review"
        }
