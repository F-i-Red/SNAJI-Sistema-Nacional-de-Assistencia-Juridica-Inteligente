
from app.rag.bm25_retriever import BM25Retriever
from app.rag.embedding_retriever import EmbeddingRetriever

class HybridRetriever:

    def __init__(self):

        self.bm25 = BM25Retriever()
        self.embedding = EmbeddingRetriever()

    def search(self, query: str):

        bm25_results = self.bm25.search(query)

        embedding_results = self.embedding.search(query)

        combined = bm25_results + embedding_results

        combined.sort(
            key=lambda x: x["score"],
            reverse=True
        )

        return combined
