"""Streamlit entrypoint for the Who Provenance demo application.

The app is split into two pages: database page for database state view and management, 
and a query page that runs SQL against the current demo state and lets
the user inspect query output.
"""

import streamlit as st

from db_client import *
from action_dialogs import *
from helper import *

if "initialized" not in st.session_state:
    # Trigger state reset on initialization
    st.session_state.initialized = True
    reset_demo_state()
    st.session_state.query_rows = None

st.title("Who Provenance Demo")


TABLE_FIELDS = {
    "people": ["x", "y"],
    "memberships": ["y", "z"],
}


def render_table(table_name, label, container=st):
    """Render a named table in the given Streamlit container."""
    container.markdown(f"### {label}")
    _, rows = load_table_rows(table_name)
    if rows is not None:
        container.dataframe(rows, width="stretch", hide_index=True)
    else:
        container.info("No rows found.")


def database_page():
    """Render the database page."""
    st.title("Database")
    control_cols = st.columns(2)
    with control_cols[0]:
        if st.button("Set to default state", use_container_width=True):
            try:
                reset_demo_state()
                # seed_demo_state()
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

    render_table("audit_log", "Audit Log")


def query_page():
    """Render the SQL query page and persist the result set."""
    st.title("Query")
    with st.form("query_form"):
        window_start = st.text_input(
            "Window start", value="2024-12-01 00:00:00Z")
        query = st.text_area("SQL Query",
                             value="""SELECT r.x, r.y
FROM people AS r
JOIN memberships AS s ON r.y = s.y
GROUP BY r.x, r.y"""
                             )
        submitted = st.form_submit_button("Run Query")
        if submitted:
            try:
                st.session_state.query_rows = submit_query(
                    TABLE_FIELDS, query, window_start)
            except Exception as exc:
                st.error(f"Query failed: {exc}")
                st.session_state.query_rows = None

    rows = st.session_state.query_rows

    event = None
    if rows is not None:
        st.markdown(f"**Results (limit 200)**")
        event = st.dataframe(rows.style.apply(style_active_rows, axis=1),
                             width="stretch",
                             on_select="rerun",
                             key="q_results",
                             selection_mode="single-row",
                             column_config={
                                 "tmp_annotation": None, "tmp_alive": None},
                             hide_index=True)

        if event is not None and len(event.selection.rows) > 0:
            show_row_details(rows.iloc[event.selection.rows[0]])

    else:
        st.info("No results.")


pg = st.navigation([st.Page(database_page, title="Database"),
                   st.Page(query_page, title="Query")], position='top')
pg.run()
