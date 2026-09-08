import pandas as pd
import streamlit as st
import hashlib

HAPPINESS_TYPE_ORDER = ["自己実現派", "自己成長派", "自然体派", "社会交流派", "生活充実派"]


def render_sidebar(df):
    st.sidebar.markdown('<div class="filter-panel"><div class="sidebar-title">U.Ge Dashboard</div>', unsafe_allow_html=True)

    current_happiness_column = next((column for column in ("現在の幸福状態", "現在の幸福状況（集約分）") if column in df.columns), None)
    ideal_happiness_column = next((column for column in ("理想的な幸福状態", "理想的な幸福の状態（集約分）", "幸せに必要なこと") if column in df.columns), None)
    year_options = ["すべて"] + sorted(df["年度"].dropna().unique().tolist()) if "年度" in df.columns else ["すべて"]
    age_options = sorted(df["年齢"].dropna().unique().tolist()) if "年齢" in df.columns else []
    gender_options = sorted(df["性別"].dropna().unique().tolist()) if "性別" in df.columns else []
    city_options = sorted(df["居住地"].dropna().unique().tolist()) if "居住地" in df.columns else []
    job_options = sorted(df["職業"].dropna().unique().tolist()) if "職業" in df.columns else []
    family_options = sorted(df["同居家族"].dropna().unique().tolist()) if "同居家族" in df.columns else []
    income_options = sorted(df["世帯年収"].dropna().unique().tolist()) if "世帯年収" in df.columns else []
    current_happiness_options = sorted(df[current_happiness_column].dropna().unique().tolist()) if current_happiness_column else []
    ideal_happiness_options = sorted(df[ideal_happiness_column].dropna().unique().tolist()) if ideal_happiness_column else []
    current_type_options = [
        option for option in HAPPINESS_TYPE_ORDER
        if "現在の幸福度タイプ" in df.columns and option in df["現在の幸福度タイプ"].dropna().unique()
    ]
    ideal_type_options = [
        option for option in HAPPINESS_TYPE_ORDER
        if "理想の幸福度タイプ" in df.columns and option in df["理想の幸福度タイプ"].dropna().unique()
    ]
    happiness_all_option = "すべて（絞り込まない）"
    dataset_signature = hashlib.md5("|".join(map(str, df.columns)).encode("utf-8")).hexdigest()[:8] + f"_{len(df)}"

    with st.sidebar:
        st.markdown('<div class="sidebar-section"><span class="sidebar-label">年度</span>', unsafe_allow_html=True)
        selected_year = st.pills(
            "年度フィルタ",
            year_options,
            default="すべて",
            label_visibility="collapsed",
            key=f"sidebar_year_{dataset_signature}",
            width="stretch",
        )

        st.markdown('<div class="sidebar-section"><span class="sidebar-label">年齢</span>', unsafe_allow_html=True)
        selected_age = st.pills(
            "年代フィルタ",
            age_options,
            selection_mode="multi",
            default=age_options,
            label_visibility="collapsed",
            key=f"sidebar_age_{dataset_signature}",
            width="stretch",
        )

        st.markdown('<div class="sidebar-section"><span class="sidebar-label">性別</span>', unsafe_allow_html=True)
        selected_gender = st.pills(
            "性別フィルタ",
            gender_options,
            selection_mode="multi",
            default=gender_options,
            label_visibility="collapsed",
            key=f"sidebar_gender_{dataset_signature}",
            width="stretch",
        )

        if current_type_options:
            st.markdown('<div class="sidebar-section"><span class="sidebar-label">現在のペンタゴンタイプ</span>', unsafe_allow_html=True)
            selected_current_type = st.pills(
                "現在のペンタゴンタイプフィルタ",
                [happiness_all_option, *current_type_options],
                default=happiness_all_option,
                label_visibility="collapsed",
                key=f"sidebar_current_type_{dataset_signature}",
                width="stretch",
            )
        else:
            selected_current_type = happiness_all_option

        if ideal_type_options:
            st.markdown('<div class="sidebar-section"><span class="sidebar-label">理想のペンタゴンタイプ</span>', unsafe_allow_html=True)
            selected_ideal_type = st.pills(
                "理想のペンタゴンタイプフィルタ",
                [happiness_all_option, *ideal_type_options],
                default=happiness_all_option,
                label_visibility="collapsed",
                key=f"sidebar_ideal_type_{dataset_signature}",
                width="stretch",
            )
        else:
            selected_ideal_type = happiness_all_option

        if current_happiness_column:
            st.markdown('<div class="sidebar-section"><span class="sidebar-label">現在の幸福状態</span>', unsafe_allow_html=True)
            selected_current_happiness = st.selectbox(
                "現在の幸福状態フィルタ",
                [happiness_all_option, *current_happiness_options],
                help="表示したい現在の幸福状態を1つ選びます。初期値の「すべて」は絞り込みを行いません。",
                key=f"sidebar_current_happiness_{dataset_signature}",
            )
        else:
            selected_current_happiness = happiness_all_option

        if ideal_happiness_column:
            st.markdown('<div class="sidebar-section"><span class="sidebar-label">理想的な幸福状態</span>', unsafe_allow_html=True)
            selected_ideal_happiness = st.selectbox(
                "理想的な幸福状態フィルタ",
                [happiness_all_option, *ideal_happiness_options],
                help="表示したい理想的な幸福状態を1つ選びます。初期値の「すべて」は絞り込みを行いません。",
                key=f"sidebar_ideal_happiness_{dataset_signature}",
            )
        else:
            selected_ideal_happiness = happiness_all_option

        st.markdown('<div class="sidebar-section"><span class="sidebar-label">居住地</span>', unsafe_allow_html=True)
        selected_city = st.selectbox(
            "居住地フィルタ",
            [happiness_all_option, *city_options],
            key=f"sidebar_city_{dataset_signature}",
        )

        st.markdown('<div class="sidebar-section"><span class="sidebar-label">職業</span>', unsafe_allow_html=True)
        selected_job = st.selectbox(
            "職業フィルタ",
            [happiness_all_option, *job_options],
            key=f"sidebar_job_{dataset_signature}",
        )

        st.markdown('<div class="sidebar-section"><span class="sidebar-label">同居家族</span>', unsafe_allow_html=True)
        selected_family = st.selectbox(
            "同居家族フィルタ",
            [happiness_all_option, *family_options],
            key=f"sidebar_family_{dataset_signature}",
        )

        st.markdown('<div class="sidebar-section"><span class="sidebar-label">世帯年収</span>', unsafe_allow_html=True)
        selected_income = st.selectbox(
            "世帯年収フィルタ",
            [happiness_all_option, *income_options],
            key=f"sidebar_income_{dataset_signature}",
        )

        st.markdown('</div>', unsafe_allow_html=True)

    mask = pd.Series(True, index=df.index)
    if "年度" in df.columns and selected_year != "すべて":
        mask &= df["年度"].eq(selected_year)
    if "年齢" in df.columns and age_options and selected_age != age_options:
        mask &= df["年齢"].isin(selected_age)
    if "性別" in df.columns and gender_options and selected_gender != gender_options:
        mask &= df["性別"].isin(selected_gender)
    if "居住地" in df.columns and selected_city != happiness_all_option:
        mask &= df["居住地"].eq(selected_city)
    if "職業" in df.columns and selected_job != happiness_all_option:
        mask &= df["職業"].eq(selected_job)
    if "同居家族" in df.columns and selected_family != happiness_all_option:
        mask &= df["同居家族"].eq(selected_family)
    if "世帯年収" in df.columns and selected_income != happiness_all_option:
        mask &= df["世帯年収"].eq(selected_income)
    if current_type_options and selected_current_type != happiness_all_option:
        mask &= df["現在の幸福度タイプ"].eq(selected_current_type)
    if ideal_type_options and selected_ideal_type != happiness_all_option:
        mask &= df["理想の幸福度タイプ"].eq(selected_ideal_type)
    if current_happiness_column and selected_current_happiness != happiness_all_option:
        mask &= df[current_happiness_column].eq(selected_current_happiness)
    if ideal_happiness_column and selected_ideal_happiness != happiness_all_option:
        mask &= df[ideal_happiness_column].eq(selected_ideal_happiness)

    filtered = df.loc[mask].copy()

    return filtered, {
        "year": selected_year,
        "age": selected_age,
        "gender": selected_gender,
        "city": selected_city,
        "job": selected_job,
        "family": selected_family,
        "income": selected_income,
        "current_type": selected_current_type,
        "ideal_type": selected_ideal_type,
        "current_happiness": selected_current_happiness,
        "ideal_happiness": selected_ideal_happiness,
    }
