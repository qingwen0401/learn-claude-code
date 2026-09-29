"""Example module demonstrating type hints, docstrings, and a main guard."""


def greet(name: str) -> None:
    """Print a friendly greeting to the given name.

    Args:
        name: The person (or thing) to greet.
    """
    message = "Hello, " + name
    print(message)


if __name__ == "__main__":
    greet("Claude")
