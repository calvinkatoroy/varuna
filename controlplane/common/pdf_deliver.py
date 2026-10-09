"""Protected-PDF delivery (v2): convert the approved review docx to PDF and encrypt it with a
password so the client gets a read-only file (no redaction; the content is full detail).

docx->PDF conversion shells out to LibreOffice headless (`soffice`), which lives in the
controlplane image. The converter is a module-level hook (`CONVERT`) so tests inject a fake
that produces a real PDF via reportlab, exercising the pypdf encryption without LibreOffice.
"""
from __future__ import annotations

import io
import os
import pathlib
import secrets
import subprocess
import tempfile
import threading


# LibreOffice headless shares one user profile: two conversions at once make one of them fail
# (seen as a 502 when several reports were delivered together). Serialize them, and give each
# run its own throwaway profile so a stale lock from a crashed run can never block the next.
_CONVERT_LOCK = threading.Lock()


def _soffice_convert(docx_bytes: bytes) -> bytes:
    """docx bytes -> pdf bytes via LibreOffice headless."""
    with _CONVERT_LOCK, tempfile.TemporaryDirectory() as d:
        docx_path = os.path.join(d, "report.docx")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        profile = pathlib.Path(d, "lo-profile").as_uri()
        subprocess.run(
            ["soffice", f"-env:UserInstallation={profile}", "--headless", "--convert-to", "pdf",
             "--outdir", d, docx_path],
            check=True, capture_output=True, timeout=180,
        )
        with open(os.path.join(d, "report.pdf"), "rb") as f:
            return f.read()


# Override in tests to avoid needing LibreOffice.
CONVERT = _soffice_convert


def encrypt_pdf(pdf_bytes: bytes, password: str) -> bytes:
    """AES-256. `password` is the USER password the recipient types. The owner password is random and discarded, so
    the recipient cannot lift the print-only permissions (the old code used one string for both)."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.constants import UserAccessPermissions
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password, owner_password=secrets.token_urlsafe(24),
                   permissions_flag=UserAccessPermissions.PRINT, algorithm="AES-256")
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def deliver(docx_bytes: bytes, password: str, convert=None) -> bytes:
    """Full docx -> encrypted PDF pipeline. Returns the protected PDF bytes."""
    convert = convert or CONVERT
    return encrypt_pdf(convert(docx_bytes), password)


if __name__ == "__main__":
    from reportlab.pdfgen import canvas
    def _fake(_):
        b = io.BytesIO(); c = canvas.Canvas(b); c.drawString(72, 720, "stub"); c.showPage(); c.save()
        return b.getvalue()
    out = deliver(b"x", "s3cret", convert=_fake)
    from pypdf import PdfReader
    assert PdfReader(io.BytesIO(out)).is_encrypted, "delivered PDF must be encrypted"
    print("pdf_deliver.py self-check OK")
