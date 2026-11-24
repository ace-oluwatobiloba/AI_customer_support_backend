from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile

from docx import Document
from pypdf import PdfReader


# Define the file formats supported by the ingestion pipeline.
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class DocumentExtractionError(Exception):
    """Raised when a document cannot be extracted successfully."""


def extract_text(file_source, filename: str | None = None) -> str:
    """Extract text from a filesystem path or an opened binary file."""

    # Support existing filesystem-path callers without breaking current tests.
    if isinstance(file_source, (str, Path)):
        path = Path(file_source)
        filename = path.name

        # Reject missing files before attempting extraction.
        if not path.is_file():
            raise DocumentExtractionError(
                f"Document does not exist: {path}"
            )

        try:
            # Read the file as bytes so all formats use the same extraction path.
            with path.open("rb") as source:
                file_content = source.read()
        except OSError as exc:
            raise DocumentExtractionError(
                f"Could not read document: {path.name}."
            ) from exc

    else:
        # Require a filename because file-like objects may not expose one.
        if not filename:
            raise DocumentExtractionError(
                "A filename is required for file-like objects."
            )

        try:
            # Read the file through the storage-provided file object.
            file_source.seek(0)
            file_content = file_source.read()
        except Exception as exc:
            raise DocumentExtractionError(
                "Could not read the stored document."
            ) from exc

    # Determine the format from the filename, not the storage key's location.
    extension = Path(filename).suffix.lower()

    # Reject unsupported formats before invoking a document parser.
    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentExtractionError(
            f"Unsupported file format: {extension or 'unknown'}"
        )

    try:
        # Parse PDFs directly from an in-memory binary stream.
        if extension == ".pdf":
            reader = PdfReader(BytesIO(file_content))

            # Reject encrypted documents because this pipeline does not decrypt them.
            if reader.is_encrypted:
                raise DocumentExtractionError(
                    "Encrypted PDF documents are not supported."
                )

            extracted_text = "\n".join(
                page.extract_text() or "" for page in reader.pages
            )

        # Parse Word documents from a temporary binary file.
        elif extension == ".docx":
            # A spooled file can stay in memory and spill to disk when necessary.
            with SpooledTemporaryFile() as temporary_file:
                temporary_file.write(file_content)
                temporary_file.seek(0)

                # python-docx accepts a file-like object.
                document = Document(temporary_file)

            # Extract non-empty paragraph content.
            paragraphs = [
                paragraph.text
                for paragraph in document.paragraphs
                if paragraph.text.strip()
            ]

            # Include text stored inside Word tables.
            table_text = [
                cell.text
                for table in document.tables
                for row in table.rows
                for cell in row.cells
                if cell.text.strip()
            ]

            extracted_text = "\n".join(paragraphs + table_text)

        else:
            # Decode plain text and support files containing a UTF-8 BOM.
            extracted_text = file_content.decode("utf-8-sig")

    except DocumentExtractionError:
        # Preserve explicit validation errors for callers.
        raise
    except Exception as exc:
        # Normalize parser errors without exposing internal exception details.
        raise DocumentExtractionError(
            f"Could not extract text from {filename}."
        ) from exc

    # Remove NUL characters and surrounding whitespace from extracted content.
    extracted_text = extracted_text.replace("\x00", "").strip()

    # Reject files that contain no usable text.
    if not extracted_text:
        raise DocumentExtractionError(
            f"No extractable text found in {filename}."
        )

    return extracted_text