import streamlit as st

from db_client import *
from datetime import datetime

from helper import *


@st.dialog("INSERT")
def insert_dialog(users, table_props):
    exec_user = st.selectbox("Edit as user:", users)
    time_override = st.text_input(
        "Time override i.e., 2025-01-01 10:00:00Z (default: current time)"
    )
    table_name = st.selectbox("Table", list(
        table_props.keys()), key="insert_table_select")
    for col in table_props[table_name]:
        st.text_input(f"{col}", key=f"{table_name}_{col}")
    if st.button("Submit", use_container_width=True):
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
    exec_user = st.selectbox("Edit as user:", users)
    time_override = st.text_input(
        "Time override i.e., 2025-01-01 10:00:00Z (default: current time)"
    )
    table_name = st.selectbox("Table", list(table_props.keys()))
    for col in table_props[table_name]:
        st.text_input(f"{col}", key=f"{table_name}_{col}")

    if st.button("Submit", use_container_width=True):
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

    if st.button("Submit", use_container_width=True):
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


@st.dialog("Result Tuple")
def show_row_details(row_data):
    st.dataframe(pd.DataFrame([row_data]).style.apply(style_active_rows, axis=1), hide_index=True, column_config={
                 "tmp_annotation": None, "tmp_alive": None})
    annotation = row_data.get("tmp_annotation")

    for i, exp in enumerate(annotation):
        left, right = st.columns([4, 1])

        with left:
            st.markdown(
                f":{'red' if exp[-1].get('pos_neg') == 'neg' else 'green'}[**Explanation {i}**]"
            )

        with right:
            see_more = st.button("Intervals", key=f"btn_{i}")

        st.dataframe(exp[-1].get("blame"), key=f"outer_{i}")

        if see_more:
            for bf in exp:
                prefix = "🟢" if bf.get("pos_neg") == "pos" else "🔴"

                start = bf.get("start")
                if start != "-infinity":
                    start = datetime.fromisoformat(
                        start).strftime("%b %-d, %Y, %H:%M")

                end = bf.get("end")
                if end != "infinity":
                    end = datetime.fromisoformat(
                        end).strftime("%b %-d, %Y, %H:%M")

                with st.expander(f"{prefix} {start} → {end}"):
                    st.dataframe(
                        bf.get("blame"), key=f"inner_{i}_{bf.get('start')}_{bf.get('end')}")

        st.divider()
