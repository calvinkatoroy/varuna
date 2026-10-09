import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
import pdf_deliver  # noqa: E402
from pypdf import PdfReader, PasswordType  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402


def _fake_convert(_docx_bytes):
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.drawString(72, 720, "stub report")
    c.showPage()
    c.save()
    return b.getvalue()


def test_deliver_produces_encrypted_pdf():
    out = pdf_deliver.deliver(b"docx-bytes", "s3cret", convert=_fake_convert)
    assert PdfReader(io.BytesIO(out)).is_encrypted


def test_password_required_to_open():
    out = pdf_deliver.deliver(b"docx-bytes", "s3cret", convert=_fake_convert)
    assert PdfReader(io.BytesIO(out)).decrypt("wrong") == PasswordType.NOT_DECRYPTED
    assert PdfReader(io.BytesIO(out)).decrypt("s3cret") != PasswordType.NOT_DECRYPTED


def test_pdf_is_aes256_with_a_throwaway_owner_password():
    out = pdf_deliver.deliver(b"docx-bytes", "s3cret", convert=_fake_convert)
    reader = PdfReader(io.BytesIO(out))
    assert int(reader.trailer["/Encrypt"].get_object()["/V"]) == 5          # AES-256 (V5); RC4 would be 1 or 2
    assert reader.decrypt("s3cret") == PasswordType.USER_PASSWORD           # the recipient only ever gets the user role
