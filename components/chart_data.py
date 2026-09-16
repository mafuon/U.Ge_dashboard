import pandas as pd
import streamlit as st


def show_chart_data(data: pd.DataFrame, key: str, label: str = "元データを表示") -> None:
    """Show the aggregated values used by a chart in a collapsed table."""
    if data.empty:
        return
    with st.expander(label, expanded=False):
        st.dataframe(data.reset_index(drop=True), hide_index=True, width="stretch", key=f"chart-data-{key}")
