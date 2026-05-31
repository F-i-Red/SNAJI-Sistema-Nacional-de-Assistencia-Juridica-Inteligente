
from app.rag.chunker import LegalChunker

class LegalIngestionPipeline:

    def __init__(self):

        self.chunker = LegalChunker()

    def ingest(self, texto: str):

        chunks = self.chunker.split_document(texto)

        return {
            "chunks_created": len(chunks),
            "chunks": chunks
        }
