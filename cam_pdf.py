def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_cam_pdf_bytes(cam_text: str, title: str = "Credit Appraisal Memo") -> bytes:
    """
    Minimal PDF generator for plain-text CAM content without external dependencies.
    Uses Helvetica font and A4 portrait layout.
    """
    lines = [line.rstrip() for line in (cam_text or "").splitlines()]
    if not lines:
        lines = ["CAM content unavailable."]

    # A4 points
    width = 595
    height = 842
    margin_x = 42
    margin_top = 56
    line_height = 14
    max_lines = int((height - margin_top - 50) / line_height)

    chunks = []
    for i in range(0, len(lines), max_lines):
        chunks.append(lines[i:i + max_lines])

    objects: list[bytes] = []

    def add_obj(content: str | bytes) -> int:
        if isinstance(content, str):
            content = content.encode("latin-1", errors="replace")
        objects.append(content)
        return len(objects)

    # Font object
    font_obj = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_objs = []
    content_objs = []

    for page_idx, chunk in enumerate(chunks, start=1):
        text_ops = ["BT", "/F1 11 Tf"]
        y = height - margin_top
        for idx, line in enumerate(chunk):
            safe_line = _pdf_escape(line)
            if idx == 0:
                text_ops.append(f"{margin_x} {y} Td")
            else:
                text_ops.append(f"0 -{line_height} Td")
            text_ops.append(f"({safe_line}) Tj")
        text_ops.append("ET")
        stream = "\n".join(text_ops).encode("latin-1", errors="replace")
        content_obj = add_obj(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream"
        )
        content_objs.append(content_obj)
        page_obj = add_obj(
            f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 {width} {height}] "
            f"/Contents {content_obj} 0 R /Resources << /Font << /F1 {font_obj} 0 R >> >> >>"
        )
        page_objs.append(page_obj)

    kids_ref = " ".join(f"{pid} 0 R" for pid in page_objs)
    pages_obj = add_obj(f"<< /Type /Pages /Kids [{kids_ref}] /Count {len(page_objs)} >>")

    # Patch page parent references
    for page_id in page_objs:
        raw = objects[page_id - 1].decode("latin-1")
        objects[page_id - 1] = raw.replace("/Parent 0 0 R", f"/Parent {pages_obj} 0 R").encode("latin-1")

    catalog_obj = add_obj(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")
    info_obj = add_obj(f"<< /Title ({_pdf_escape(title)}) /Producer (CreditMind) >>")

    # Build file
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    body = bytearray(header)
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body.extend(f"{i} 0 obj\n".encode("latin-1"))
        body.extend(obj)
        body.extend(b"\nendobj\n")

    xref_offset = len(body)
    body.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    body.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        body.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    body.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_obj} 0 R /Info {info_obj} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("latin-1")
    )
    return bytes(body)
