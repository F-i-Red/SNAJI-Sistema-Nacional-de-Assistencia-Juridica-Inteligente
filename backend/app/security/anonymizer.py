
import re

class LegalAnonymizer:

    def anonymize(self, text: str):

        text = re.sub(r'\b\d{9}\b', '[NIF_REDACTED]', text)

        text = re.sub(
            r'[A-Z][a-z]+\s[A-Z][a-z]+',
            '[NOME_REDACTED]',
            text
        )

        return text
