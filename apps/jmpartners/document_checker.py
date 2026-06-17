class DocumentChecker:
    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".xlsx"}

    def is_valid(self, filename: str) -> bool:
        import os

        _, ext = os.path.splitext(filename.lower())
        return ext in self.ALLOWED_EXTENSIONS
