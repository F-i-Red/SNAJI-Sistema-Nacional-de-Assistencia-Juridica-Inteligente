
class LegalReranker:

    def rerank(self, results):

        reranked = sorted(
            results,
            key=lambda x: x["score"],
            reverse=True
        )

        return reranked
