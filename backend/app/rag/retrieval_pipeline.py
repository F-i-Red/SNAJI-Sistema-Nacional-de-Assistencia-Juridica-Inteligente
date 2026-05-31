
from app.rag.hybrid_retriever import HybridRetriever
from app.rag.reranker import LegalReranker

class RetrievalPipeline:

    def __init__(self):

        self.retriever = HybridRetriever()
        self.reranker = LegalReranker()

    def retrieve(self, query):

        results = self.retriever.search(query)

        reranked = self.reranker.rerank(results)

        return reranked
