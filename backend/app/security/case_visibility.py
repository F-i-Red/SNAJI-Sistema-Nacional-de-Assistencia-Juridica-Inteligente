
class CaseVisibilityManager:

    LEVELS = [
        "public",
        "institutional",
        "restricted"
    ]

    def is_valid_level(self, level):

        return level in self.LEVELS
