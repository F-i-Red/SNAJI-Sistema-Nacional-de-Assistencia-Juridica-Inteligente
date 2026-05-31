
class HallucinationGuard:

    def inspect(self, response):

        issues = []

        if "artigo 999" in response.lower():
            issues.append("Possível artigo inexistente")

        return {
            "safe": len(issues) == 0,
            "issues": issues
        }
