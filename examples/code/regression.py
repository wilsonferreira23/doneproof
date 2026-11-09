from app import greet

# The same entry point must preserve normalization and invalid-input rejection.
assert greet(" Ada ") == "Hello, Ada"
try:
    greet("  ")
except ValueError:
    pass
else:
    raise AssertionError("empty name accepted")
print("2 regression cases executed")
