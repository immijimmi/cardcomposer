from operator import add, mul, sub, truediv


class Constants:
    DEFERRED_TYPE_KEY = "deferred_type"

    CALCULATIONS_LOOKUP = {
        "+": add,
        "*": mul,
        "-": sub,
        "/": truediv,
        "round": round,
        "sum": sum,
        "min": min,
        "max": max,
        "index": (lambda container, key: container[key])
    }
