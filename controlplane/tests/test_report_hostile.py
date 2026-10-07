"""Reports must survive hostile/dirty text: terminal escapes, control characters, RTL marks,
markup, absurd lengths. python-docx raises on XML-illegal characters, which used to stop every
template (and with it the automatic review) on a single ANSI code in scanner output."""
import io
import os
import sys

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "report"))

from docx import Document  # noqa: E402

import generator  # noqa: E402

JOB = {"id": "j-hostile", "target": "http://t.example", "submitter": "acme\x00corp"}
DIRTY = [
    {"name": "SQLi \x1b[31mred\x1b[0m", "severity": "critical", "host": "h\x0bost", "url": "/a?x=\x00\x01",
     "evidence": "line1\x00\x08line2\x1b[0m emoji \U0001F600 rtl ‮ end", "description": "d\x0c",
     "impact": "<script>alert(1)</script> & \"quotes\" ]]>", "remediation": "fix\x7f", "cwe": "CWE-89",
     "cvss": 9.8, "tool": "sqlmap", "verdict": "tp"},
    {"name": "", "severity": "not-a-severity", "host": None, "url": None, "evidence": None, "tool": None},
    {"name": "N" * 20000, "severity": "low", "host": "h", "evidence": "E" * 200000},
]


def _text(data: bytes) -> str:
    d = Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            parts += [c.text for c in row.cells]
    return "\n".join(parts)


def test_every_template_survives_dirty_content():
    for template in generator.TEMPLATES:
        data = generator.generate(JOB, DIRTY, template)
        assert data[:2] == b"PK", f"{template} did not produce a docx"


def test_escapes_and_control_characters_are_removed_not_left_as_junk():
    text = _text(generator.generate(JOB, DIRTY, "Full Technical"))
    assert "\x1b" not in text and "\x00" not in text and "[31m" not in text
    assert "SQLi red" in text                         # the words survive, the colour codes do not
    assert "<script>alert(1)</script>" in text        # markup is shown as text, never interpreted


def test_absurdly_long_fields_are_truncated_not_dumped_into_the_report():
    text = _text(generator.generate(JOB, DIRTY, "Full Technical"))
    assert "[truncated]" in text
    assert len(text) < 60000, "a 200 KB evidence blob must not balloon the document"


def test_client_form_fields_are_cleaned_too(tmp_path):
    import db
    db.reset_for_test(str(tmp_path / "t.db"))
    pid = db.create_proposal({"submitter": "acme", "target": "http://t.example", "division": "IT\x00\x0bDiv",
                              "purpose": "pre\x1b[1mrelease", "authorization_attested": True, "org_id": "org-acme"})
    db.update_proposal(pid, status="approved", job_id="j-hostile")
    text = _text(generator.generate({**JOB, "submitter": "acme"}, DIRTY[:1], "Formal Handover"))
    assert "ITDiv" in text and "prerelease" in text
