from pathlib import Path

def read_protected(role):
    if role != "operator":
        raise PermissionError("not allowed")
    return "protected"

def save_value(path, value):
    Path(path).write_text(value)
