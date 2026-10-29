"""Ghi snapshot JSON nguyên tử cho local single-writer storage."""

import json
import os
import tempfile


def atomic_json(path, payload):
    """Flush trước replace cùng thư mục; caller giữ writer lock."""
    descriptor, name = tempfile.mkstemp(prefix=".snapshot-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
