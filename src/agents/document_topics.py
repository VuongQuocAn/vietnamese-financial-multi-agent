"""Bounded topic extraction and conjunctions shared by document and fusion routing."""

import re

from ..evidence.search import normalize_search

# These are source topics, not accounting rules or evidence of an answer.
_TOPICS = (
    ("doanh thu bán hàng", ("doanh thu ban hang",)),
    ("ghi nhận doanh thu", ("ghi nhan doanh thu",)),
    ("chi phí đi vay", ("chi phi di vay",)),
    ("vay và nợ thuê tài chính", ("vay va no thue tai chinh", "khoan vay", "phan loai vay")),
    ("hàng tồn kho", ("hang ton kho",)),
    ("các khoản giảm trừ doanh thu", ("khoan giam tru doanh thu",)),
)


def requirement_spans(question):
    """Do not split the conjunction inside a single accounting noun phrase."""
    protected = question
    for phrase in (
        r"vay\s+và\s+nợ thuê tài chính",
        r"tài sản cố định hữu hình\s+và\s+khấu hao",
        r"tài sản cố định vô hình\s+và\s+khấu hao",
        r"ngắn hạn\s+và\s+dài hạn",
    ):
        protected = re.sub(
            phrase, lambda m: re.sub(r"\s+và\s+", " § ", m[0], flags=re.I), protected, flags=re.I
        )
    return [
        span.replace(" § ", " và ").strip()
        for span in re.split(r"[.?;!\n]+|\s+(?:và|đồng thời|kèm theo)\s+", protected, flags=re.I)
        if span.strip()
    ]


def source_topics(question):
    """Extract the subject, retaining unknown subjects rather than inventing one."""
    parts = requirement_spans(question)
    topics = []
    for part in parts:
        if not re.search(r"\b(thuyet minh|chinh sach|noi dung b09)\b", normalize_search(part)):
            continue
        topic = re.split(r"\bvề\s+", part, flags=re.I)[-1].strip(" .?")
        text = normalize_search(topic)
        matched = []
        for label, aliases in _TOPICS:
            if any(re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text) for alias in aliases):
                # The specific sales policy takes precedence over its generic label.
                if label == "ghi nhận doanh thu" and "doanh thu bán hàng" in matched:
                    continue
                matched.append(label)
        if not matched:
            if "nhan vien quan ly chu chot" in text:
                continue  # Existing exact-text requirement already covers this subject.
            topic = re.sub(r"^(?:các\s+)?khoản\s+", "", topic, flags=re.I)
            topic = re.sub(r"\s+(?:không|như thế nào|thế nào|ra sao).*$", "", topic, flags=re.I)
            if topic == part.strip(" .?"):
                topic = re.sub(r"^.*?chính sách\s+", "", topic, flags=re.I)
                topic = re.sub(r"\s+được thuyết minh.*$", "", topic, flags=re.I)
            matched = [re.sub(r"^chính sách\s+", "", topic, flags=re.I)]
        topics.extend(t for t in matched if t not in topics)
    return topics
