"""Ghi snapshot JSON nguyên tử cho local single-writer storage."""

import json
import os
import tempfile


def atomic_json(path, payload):
    """Flush trước replace cùng thư mục; caller giữ writer lock."""
    descriptor, name = tempfile.mkstemp(prefix=".snapshot-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            # dumps uses the C encoder and one stream write. dump iterates and
            # writes every nested proof fragment in Python. Keep identical JSON
            # semantics and the existing flush/fsync/atomic replace boundary.
            stream.write(json.dumps(payload, ensure_ascii=False, allow_nan=False))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
