
class NormValidator:

    VALID_DIPLOMAS = [
        "CRP",
        "Código Civil",
        "Código Penal",
        "CPP",
        "CPC"
    ]

    def validate_reference(self, diploma: str, artigo: str):

        if diploma not in self.VALID_DIPLOMAS:
            return False

        return True
