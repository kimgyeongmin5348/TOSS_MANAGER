"""Display formatting without UI or dataframe dependencies."""


def currency(value: float, market: str) -> str:
    return f"${value:,.2f}" if market == "US" else f"₩{value:,.0f}"


def percentage(value: float | int | None) -> float:
    """Convert API ratio values such as 0.03 to percentage points."""
    return float(value or 0) * 100


def percentage_text(value: float | int | None) -> str:
    return f"{percentage(value):+.2f}%"
