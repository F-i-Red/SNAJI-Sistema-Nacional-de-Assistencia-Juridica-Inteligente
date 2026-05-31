
class LegalKnowledgeStore:

    def __init__(self):
        self.documents = []

    def add(self, document):

        self.documents.append(document)

    def search(self, query):

        return self.documents
