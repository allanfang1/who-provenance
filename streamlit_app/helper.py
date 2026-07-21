"""Formatting helpers used by the Streamlit UI."""


def style_active_rows(row):
    """Color active result rows green and inactive rows red."""
    if row.get("tmp_alive") == True:
        return ["color: green"] * len(row)
    return ["color: red"] * len(row)
