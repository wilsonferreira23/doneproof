from app import greet
assert greet(" Ada ") == "Hello, Ada"
try:
    greet("  ")
except ValueError:
    pass
else:
    raise AssertionError("empty name accepted")
print("2 acceptance cases executed")
