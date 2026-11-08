# NOTE(krishan711): mirrors shortFormatNumber in @kibalabs/core so server-written text reads like the app
def short_format_number(value: float) -> str:
    if value >= 1e9:  # noqa: PLR2004
        return f'{value / 1e9:.0f}B'
    if value >= 1e7:  # noqa: PLR2004
        return f'{value / 1e6:.0f}M'
    if value >= 1e6:  # noqa: PLR2004
        return f'{value / 1e6:.1f}M'
    if value >= 1e4:  # noqa: PLR2004
        return f'{value / 1e3:.0f}K'
    if value >= 1e3:  # noqa: PLR2004
        return f'{value / 1e3:.1f}K'
    if value > 100:  # noqa: PLR2004
        return f'{value:.0f}'
    if value > 1:
        return f'{value:.1f}'
    return f'{value:.2f}'
