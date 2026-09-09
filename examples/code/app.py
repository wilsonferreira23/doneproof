def greet(name):
    name = name.strip()
    if not name:
        raise ValueError("empty name")
    return "Hello, " + name
