import sys
import tempfile
from pathlib import Path
from product import read_protected, save_value

mode = sys.argv[1]
if mode in ("behavior", "integration"):
    assert read_protected("operator") == "protected"
if mode in ("negative", "integration"):
    try:
        read_protected("guest")
    except PermissionError:
        pass
    else:
        raise AssertionError("guest was allowed")
if mode in ("readback", "integration"):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "value.txt"
        save_value(path, "actual persisted value")
        assert path.read_text() == "actual persisted value"
assert mode in ("behavior", "negative", "readback", "integration")
print("executed acceptance assertions:", mode)
