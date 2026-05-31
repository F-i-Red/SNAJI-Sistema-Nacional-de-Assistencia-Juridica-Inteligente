
class DocumentManager:

    def export_pdf(self, process_id):

        return {
            "process_id": process_id,
            "exported": "pdf"
        }

    def export_docx(self, process_id):

        return {
            "process_id": process_id,
            "exported": "docx"
        }
