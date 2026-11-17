"""Resolve lexical goal alternatives without selecting accounting meaning."""

import re

from .question_understanding import normalize


def target_groups(text):
    """Keep equal-span aliases as alternatives, never as extra requested indicators.

    An explicit longer catalog label still disambiguates the shorter phrase.
    The caller must retain ambiguity; these groups do not choose accounting meaning.
    """
    from ..outputs.qa_composer import (
        EXTRA_ALIASES,
        FORMULA_ALIASES,
        ITEM_RULES,
        QA_ALIASES,
        _targets,
    )

    targets = _targets(text)
    aliases = [("metric", key, names) for key, names in FORMULA_ALIASES.items()]
    aliases += [
        ("fact", key, (*rule.aliases, key, *EXTRA_ALIASES.get(key, ())))
        for key, rule in ITEM_RULES.items()
    ]
    aliases += [("fact", key, names) for key, names in QA_ALIASES.items()]
    spans = {}
    for kind, key, names in aliases:
        for name in names:
            for match in re.finditer(r"(?<!\w)" + re.escape(normalize(name)) + r"(?!\w)", text):
                spans.setdefault(match.span(), set()).add((kind, key))
    groups = []
    for (start, end), group in sorted(spans.items()):
        if any(a <= start and end <= b and b - a > end - start for a, b in spans):
            continue
        group &= set(targets)
        if group and group not in groups:
            groups.append(group)
    for target in targets:
        if not any(target in group for group in groups):
            groups.append({target})
    return groups
