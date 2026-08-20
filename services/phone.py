import re


_PHONE_PATTERN = re.compile(r"^\+91[6-9]\d{9}$")


def normalize_phone(value):
    """Normalize Indian mobile input to one E.164 representation."""
    compact = re.sub(r"[\s().-]", "", (value or "").strip())
    if compact.startswith("0") and len(compact) == 11:
        compact = "+91" + compact[1:]
    elif compact.isdigit() and len(compact) == 10:
        compact = "+91" + compact
    if not _PHONE_PATTERN.fullmatch(compact):
        raise ValueError("Enter a valid Indian mobile number in E.164 format.")
    return compact
