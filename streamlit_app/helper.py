
def style_active_rows(row):
    if row.get("tmp_alive") == True:
        return ["color: green"] * len(row)
    return ["color: red"] * len(row)
