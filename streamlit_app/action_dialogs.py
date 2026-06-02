import streamlit as st

from db_client import *


@st.dialog("INSERT")
def insert_dialog(users, table_props):
    with st.form("insert_form"):
        exec_user = st.selectbox("Edit as user:", users)
        time_override = st.text_input(
            "Time override i.e., 2025-01-01 10:00:00Z (default: current time)"
        )
        table_name = st.selectbox("Table", list(table_props.keys()))
        for col in table_props[table_name]:
            st.text_input(f"{col}", key=f"{table_name}_{col}")
        submitted = st.form_submit_button("Submit")
        if submitted:
            values = {
                col: st.session_state[f"{table_name}_{col}"]
                for col in table_props[table_name]
            }
            try:
                insert_action(table_name, values, exec_user, time_override)
                st.rerun()
            except Exception as exc:
                st.error(f"Insert failed: {exc}")


@st.dialog("DELETE")
def delete_dialog(users, table_props):
    with st.form("delete_form"):
        exec_user = st.selectbox("Edit as user:", users)
        time_override = st.text_input(
            "Time override i.e., 2025-01-01 10:00:00Z (default: current time)"
        )
        table_name = st.selectbox("Table", list(table_props.keys()))
        for col in table_props[table_name]:
            st.text_input(f"{col}", key=f"{table_name}_{col}")
        submitted = st.form_submit_button("Submit")
        if submitted:
            values = {
                col: st.session_state[f"{table_name}_{col}"]
                for col in table_props[table_name]
            }
            try:
                delete_action(table_name, values, exec_user, time_override)
                st.rerun()
            except Exception as exc:
                st.error(f"Delete failed: {exc}")


@st.dialog("UPDATE")
def update_dialog(users, table_props):
    with st.form("update_form"):
        exec_user = st.selectbox("Edit as user:", users)
        time_override = st.text_input(
            "Time override i.e., 2025-01-01 10:00:00Z (default: current time)"
        )
        table_name = st.selectbox("Table", list(table_props.keys()))
        change_cols = st.columns(2)
        with change_cols[0]:
            st.markdown("#### Current values (WHERE)")
            for col in table_props[table_name]:
                st.text_input(f"{col}", key=f"where_{table_name}_{col}")
        with change_cols[1]:
            st.markdown("#### New values (SET)")
            for col in table_props[table_name]:
                st.text_input(f"{col}", key=f"set_{table_name}_{col}")
        submitted = st.form_submit_button("Submit")
        if submitted:
            old_values = {
                col: st.session_state[f"where_{table_name}_{col}"]
                for col in table_props[table_name]
            }
            new_values = {
                col: st.session_state[f"set_{table_name}_{col}"]
                for col in table_props[table_name]
            }
            try:
                update_action(table_name, old_values, new_values,
                              exec_user, time_override)
                st.rerun()
            except Exception as exc:
                st.error(f"Update failed: {exc}")
