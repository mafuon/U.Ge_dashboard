import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="U.Ge Dashboard", layout="wide")
st.title("U.Ge アンケート分析ダッシュボード")

uploaded_file = st.file_uploader("CSVファイルをアップロードしてください", type=["csv"])

if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        st.dataframe(df, width="stretch")

        required_columns = {"属性", "幸福度", "性別"}
        if required_columns.issubset(df.columns):
            fig = px.bar(df, x="属性", y="幸福度", color="性別")
            st.plotly_chart(fig, width="stretch")
        else:
            missing_columns = "、".join(sorted(required_columns - set(df.columns)))
            st.info(f"グラフ表示に必要な列がありません: {missing_columns}")
    except Exception as error:
        st.error(f"CSVの読み込みに失敗しました: {error}")