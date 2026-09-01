"""Small presentation helpers shared by the cogs."""


def fmt_number(value: int) -> str:
    """Render an integer with dots as thousand separators, Spanish style."""
    return f"{value:,}".replace(",", ".")
