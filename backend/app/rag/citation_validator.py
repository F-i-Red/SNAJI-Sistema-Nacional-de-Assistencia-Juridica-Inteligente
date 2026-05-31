
class CitationValidator:

    VALID_REFERENCES = {
        "CRP": ["1", "2", "13", "18", "20"]
    }

    def validate(self, diploma, artigo):

        artigos = self.VALID_REFERENCES.get(diploma, [])

        return artigo in artigos
