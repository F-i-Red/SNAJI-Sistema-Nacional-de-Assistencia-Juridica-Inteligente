
class GovernancePolicy:

    def validate(self, operation):

        return {
            "operation": operation,
            "approved": True,
            "policy_version": "1.0"
        }
