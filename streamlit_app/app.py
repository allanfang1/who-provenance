from datetime import datetime

import streamlit as st

from db_client import *
from action_dialogs import *

if "initialized" not in st.session_state:
    st.session_state.initialized = True
    reset_demo_state()
    st.success("Initialized!")

st.title("Who Provenance Demo")

database_tab, query_tab = st.tabs(["Database", "Query"])


TABLE_FIELDS = {
    "people": ["x", "y"],
    "memberships": ["y", "z"],
}


def render_table(table_name, label, container=st):
    container.markdown(f"### {label}")
    _, rows = load_table_rows(table_name)
    if rows is not None:
        container.dataframe(rows, width="stretch", hide_index=True)
    else:
        container.info("No rows found.")


with database_tab:
    control_cols = st.columns(2)
    with control_cols[0]:
        if st.button("Set to default state", use_container_width=True):
            try:
                reset_demo_state()
                seed_demo_state()
                # st.success("Demo database reset and seeded.")
                st.rerun()
            except Exception as exc:
                st.error(f"Reset failed: {exc}")
    with control_cols[1]:
        if st.button("Clear all tables", use_container_width=True):
            try:
                clear_demo_state()
                # st.success("All tables cleared.")
                st.rerun()
            except Exception as exc:
                st.error(f"Clear failed: {exc}")

    control_cols_two = st.columns(3)
    with control_cols_two[0]:
        if st.button("INSERT", use_container_width=True):
            try:
                insert_dialog(get_users(), TABLE_FIELDS)
            except Exception as exc:
                st.error(f"Insert failed: {exc}")
    with control_cols_two[1]:
        if st.button("UPDATE", use_container_width=True):
            try:
                update_dialog(get_users(), TABLE_FIELDS)
            except Exception as exc:
                st.error(f"Update failed: {exc}")
    with control_cols_two[2]:
        if st.button("DELETE", use_container_width=True):
            try:
                delete_dialog(get_users(), TABLE_FIELDS)
            except Exception as exc:
                st.error(f"Delete failed: {exc}")

    st.divider()

    render_table("people", "People")
    render_table("memberships", "Memberships")

    birth_col, death_col = st.columns(2)
    render_table("audit_log_pos",
                 "Birth Log", container=birth_col)
    render_table("audit_log_neg",
                 "Death Log", container=death_col)


with query_tab:
    st.write("Query UI goes here.")
    # for row in rows:
    #     c1, c2, c3, c4 = st.columns([1, 3, 2, 1])

    #     c1.write(row["id"])
    #     c2.write(row["name"])
    #     c3.write(row["role"])

    #     if c4.button("✏️", key=f"edit_{row['id']}"):
    #         edit_row(row)
