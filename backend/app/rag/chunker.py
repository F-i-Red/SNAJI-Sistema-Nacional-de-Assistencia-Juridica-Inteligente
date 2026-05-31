
class LegalChunker:

    def split_document(self, texto: str):

        artigos = texto.split("Artigo")

        chunks = []

        for artigo in artigos:
            artigo = artigo.strip()

            if artigo:
                chunks.append({
                    "content": artigo,
                    "metadata": {
                        "tipo": "artigo"
                    }
                })

        return chunks
