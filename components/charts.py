import html
import re

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None

CHART_PADDING = {"left": 16, "right": 28, "top": 14, "bottom": 18}
AGE_ORDER = ["20代", "30代", "40代", "50代", "60代", "70代", "80代～"]
PINK_CHOICE_COLORS = {
    1: "#FFD5CE", 2: "#FFD6E5", 3: "#FFD5D9", 4: "#FFC2B9", 5: "#FF95C3",
    6: "#FF869A", 7: "#F4A7A0", 8: "#DE6F9D", 9: "#E66C83", 10: "#F8DDD4",
    11: "#F2DEE3", 12: "#BFA8AA", 13: "#FF7B5D", 14: "#FF6BF3", 15: "#FF5891",
    16: "#D7DCE2",
}
PINK_CHOICE_NAMES = {
    1: "明るい黄みのピンク", 2: "明るい紫みのピンク", 3: "明るいピンク",
    4: "強い黄みのピンク", 5: "強い紫みのピンク", 6: "強いピンク",
    7: "やわらかいピンク", 8: "濃い紫みのピンク", 9: "濃いピンク",
    10: "うすい黄みのピンク", 11: "うすい紫みのピンク", 12: "くすんだピンク",
    13: "鮮やかな黄みのピンク", 14: "鮮やかな紫みのピンク", 15: "鮮やかなピンク",
    16: "この中にはない",
}


def render_filtered_details(df):
    st.markdown('<div class="content-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-header section-orange">フィルタ結果の詳細</div>', unsafe_allow_html=True)

    detail_columns = [
        "年度", "年齢", "性別", "居住地", "現在の幸福度タイプ", "理想の幸福度タイプ",
        "現在の幸福状態", "理想的な幸福状態", "好きな色", "好きなインテリアスタイル", "世帯年収",
    ]
    visible_columns = [column for column in detail_columns if column in df.columns]
    if not visible_columns:
        st.info("詳細として表示できる項目がありません。")
        return

    st.caption(f"抽出対象：{len(df):,}人")
    st.dataframe(df[visible_columns], hide_index=True, width="stretch", height=420)


def _happiness_section_title():
    st.markdown('<div class="sensory-kicker">12</div><h3 class="sensory-title">しあわせ指数</h3>', unsafe_allow_html=True)


def _pink_choice_data(df: pd.DataFrame) -> pd.DataFrame:
    if "幸せを感じるピンク" not in df.columns:
        return pd.DataFrame(columns=["年度", "性別", "年齢", "色票", "回答数", "回答率", "構成比"])

    values = df[[column for column in ("年度", "性別", "年齢", "幸せを感じるピンク") if column in df.columns]].dropna(subset=["幸せを感じるピンク"]).copy()
    if values.empty:
        return pd.DataFrame(columns=["年度", "性別", "年齢", "色票", "回答数", "回答率", "構成比"])
    if "年度" not in values.columns:
        values["年度"] = "全体"
    values["色票番号"] = values["幸せを感じるピンク"].astype(str).str.extract(r"(\d+)", expand=False)
    values = values.dropna(subset=["色票番号"])
    values["色票番号"] = values["色票番号"].astype(int)
    values["色票"] = values["色票番号"].map(lambda number: f"{number} {PINK_CHOICE_NAMES.get(number, 'その他')}")
    data = values.groupby(["年度", "色票"], as_index=False).size().rename(columns={"size": "回答数"})
    respondent_counts = values.groupby("年度").size()
    data["回答率"] = data["回答数"].div(data["年度"].map(respondent_counts)).mul(100)
    data["構成比"] = data.groupby("年度")["回答数"].transform(lambda counts: counts.div(counts.sum()).mul(100))
    return data


def _pink_choice_color_map(data: pd.DataFrame) -> dict[str, str]:
    choices = data["色票"].drop_duplicates().tolist()
    return {
        choice: PINK_CHOICE_COLORS.get(int(choice.split(" ", 1)[0]), "#D7DCE2")
        for choice in choices
    }


def _pink_demographic_data(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"年度", "性別", "年齢", "幸せを感じるピンク"}
    if not required_columns.issubset(df.columns):
        return pd.DataFrame(columns=["年度", "年齢", "性別", "色票", "回答数"])

    values = df[list(required_columns)].dropna().copy()
    values = values[values["年齢"].isin(AGE_ORDER)]
    if values.empty:
        return pd.DataFrame(columns=["年度", "年齢", "性別", "色票", "回答数"])

    values["色票番号"] = values["幸せを感じるピンク"].astype(str).str.extract(r"(\d+)", expand=False)
    values = values.dropna(subset=["色票番号"])
    values["色票番号"] = values["色票番号"].astype(int)
    values["色票"] = values["色票番号"].map(lambda number: f"{number} {PINK_CHOICE_NAMES.get(number, 'その他')}")
    return values.groupby(["年度", "年齢", "性別", "色票番号", "色票"], as_index=False).size().rename(
        columns={"size": "回答数"}
    )


def render_pink_analysis(df: pd.DataFrame):
    data = _pink_choice_data(df)
    if data.empty:
        return

    st.markdown('<div id="pink" class="section-anchor"></div><div class="sensory-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="sensory-kicker">13</div><h3 class="sensory-title">「しあわせ」を感じるピンク</h3><div class="sensory-note">これらピンクの中に「しあわせ」を感じるとしたら、あなたの気持ちに近い色はどれですか？</div>', unsafe_allow_html=True)
    color_map = _pink_choice_color_map(data)
    overall = data.groupby("色票", as_index=False)["回答数"].sum()
    overall["回答率"] = overall["回答数"].div(overall["回答数"].sum()).mul(100)

    if alt is not None:
        bar_chart = alt.Chart(overall).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
            x=alt.X("回答率:Q", title="回答者比率（%）", axis=alt.Axis(format=".0f")),
            y=alt.Y(
                "色票:N",
                sort="-x",
                title=None,
                axis=alt.Axis(labelLimit=420, labelFontSize=13),
            ),
            color=alt.Color("色票:N", scale=alt.Scale(domain=list(color_map), range=list(color_map.values())), legend=None),
            tooltip=["色票:N", "回答数:Q", alt.Tooltip("回答率:Q", format=".1f")],
        ).properties(
            height=max(220, len(overall) * 34),
            padding={"left": 50, "right": 28, "top": 14, "bottom": 18},
        )
        st.altair_chart(bar_chart, width="stretch")

        years = sorted(data["年度"].unique())
        demographic = _pink_demographic_data(df)
        if not demographic.empty:
            demographic["年度"] = demographic["年度"].astype(str).str.extract(r"(202[45])", expand=False)
            demographic = demographic.dropna(subset=["年度"])
            demographic["年度"] = demographic["年度"] + "年度"
        if not demographic.empty:
            target_years = ["2024年度", "2025年度"]
            demographic["属性"] = demographic["性別"].astype(str) + " " + demographic["年齢"].astype(str)
            demographic_order = [
                f"{gender} {age}"
                for age in AGE_ORDER
                for gender in ("女性", "男性")
                if f"{gender} {age}" in set(demographic["属性"])
            ]
            demographic["構成比"] = demographic.groupby(["年度", "属性"])["回答数"].transform(
                lambda counts: counts.div(counts.sum())
            )
            demographic["色票番号"] = demographic["色票"].str.extract(r"(\d+)", expand=False).astype(int)
            pink_choice_order = [
                f"{number} {PINK_CHOICE_NAMES[number]}"
                for number in sorted(demographic["色票番号"].unique())
            ]
            bars = alt.Chart(demographic).mark_bar().encode(
                x=alt.X(
                    "構成比:Q",
                    stack="zero",
                    title="構成比（%）",
                    axis=alt.Axis(format=".0%", grid=False),
                    scale=alt.Scale(domain=[0, 1]),
                ),
                y=alt.Y("属性:N", sort=demographic_order, title="性別 × 年代", axis=alt.Axis(labelLimit=120)),
                color=alt.Color(
                    "色票:N",
                    scale=alt.Scale(domain=pink_choice_order, range=[color_map[choice] for choice in pink_choice_order]),
                    legend=None,
                ),
                tooltip=["年度:N", "性別:N", "年齢:N", "色票:N", "回答数:Q", alt.Tooltip("構成比:Q", format=".1f")],
            )
            demographic_chart = bars.properties(height=max(340, len(demographic_order) * 28)).facet(
                column=alt.Column("年度:N", sort=target_years, title="年度"),
            ).properties(
                padding={"left": 100, "right": 28, "top": 14, "bottom": 18},
                spacing=48,
            ).resolve_scale(y="shared").configure_view(stroke=None)
            st.markdown("#### 性別 × 年代別の構成比")
            st.caption("年度によりピンクの色票数が異なります。  \n25年度はその色を選んだ理由を自由記述のコーナーで確認することができます。")
            st.altair_chart(demographic_chart, width="stretch")
        else:
            st.info("性別・年代の列がないため、性別 × 年代別のグラフを表示できません。")
    else:
        st.bar_chart(overall.set_index("色票")["回答率"], height=max(220, len(overall) * 34))


def render_charts(df):
    if df.empty:
        return

    st.markdown('<div id="happiness" class="section-anchor"></div><div class="content-divider"></div>', unsafe_allow_html=True)
    _happiness_section_title()
    score_col = "幸福度平均" if "幸福度平均" in df.columns else "幸福度スコア" if "幸福度スコア" in df.columns else None

    def grouped_mean(value_column, group_column, output_column):
        value_series = df[value_column]
        group_series = df[group_column]
        if isinstance(value_series, pd.DataFrame):
            value_series = value_series.iloc[:, 0]
        if isinstance(group_series, pd.DataFrame):
            group_series = group_series.iloc[:, 0]
        values = pd.DataFrame({"属性": group_series, output_column: pd.to_numeric(value_series, errors="coerce")})
        return values.groupby("属性", dropna=False)[output_column].mean().reset_index()

    st.markdown('<div class="sensory-note">幸福度比較</div>', unsafe_allow_html=True)
    if score_col is None or "年齢" not in df.columns:
        st.info("幸福度または年代の列がないため、比較を表示できません。")
        return

    compare_df = grouped_mean(score_col, "年齢", "幸福度平均")
    compare_df["年齢"] = compare_df["属性"].astype(str)
    compare_df = compare_df[compare_df["年齢"].isin(AGE_ORDER)]

    if alt is not None:
        bars = alt.Chart(compare_df).mark_bar(color="#A0C4FF").encode(
            x=alt.X("年齢:N", title="年代", sort=AGE_ORDER),
            y=alt.Y("幸福度平均:Q", title="幸福度平均", scale=alt.Scale(domain=[0, 100])),
            tooltip=[alt.Tooltip("年齢:N", title="年代"), alt.Tooltip("幸福度平均:Q", title="幸福度平均", format=".1f")],
        )
        trend = alt.Chart(compare_df).mark_line(
            color="#1E3A8A",
            strokeWidth=4,
            point=alt.OverlayMarkDef(filled=True, fill="#FFFFFF", stroke="#1E3A8A", strokeWidth=3, size=130),
        ).encode(
            x=alt.X("年齢:N", sort=AGE_ORDER),
            y=alt.Y("幸福度平均:Q", scale=alt.Scale(domain=[0, 100])),
        )
        chart = (bars + trend).properties(height=420, padding=CHART_PADDING)
        st.altair_chart(chart, use_container_width=True)
    else:
        st.bar_chart(compare_df.set_index("年齢")[["幸福度平均"]], use_container_width=True)

FREE_TEXT_QUESTIONS = {
    "好きな色を選んだ理由": ("色を選んだ", "理由"),
    "マイモットー": ("マイモットー",),
    "好きな言葉": ("好きな言葉",),
    "幸せとは": ("幸せとは",),
    "ピンクを選んだ理由": ("ピンクを選んだ理由",),
}


def _free_text_columns(df):
    columns = {}
    for label, keywords in FREE_TEXT_QUESTIONS.items():
        column = next(
            (
                candidate
                for candidate in df.columns
                if all(keyword in str(candidate).replace(" ", "").replace("\n", "") for keyword in keywords)
            ),
            None,
        )
        if column:
            columns[label] = column
    return columns


def _has_free_text(series):
    text = series.fillna("").astype(str).str.strip()
    return text.ne("") & text.str.lower().ne("nan")


def _display_free_text(value):
    text = html.unescape(str(value)).strip()
    return re.sub(r"</?div\b[^>]*>", "", text, flags=re.IGNORECASE).strip()


def render_comment_section(df):
    st.markdown('<div class="content-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div id="comments" class="section-anchor"></div><div class="section-number">14</div><div class="section-header section-orange">年度別の自由記述</div>', unsafe_allow_html=True)
    question_columns = _free_text_columns(df)
    if not question_columns or "年度" not in df.columns:
        st.info("年度別に表示できる自由記述の設問がありません。")
        return

    has_answer = pd.DataFrame({column: _has_free_text(df[column]) for column in question_columns.values()})
    years = sorted(df.loc[has_answer.any(axis=1), "年度"].dropna().astype(str).unique(), reverse=True)
    if not years:
        st.info("回答のある自由記述がありません。")
        return
    selected_year = st.selectbox("年度", years, key="free_text_year")
    year_df = df[df["年度"].astype(str).eq(selected_year)]
    available_questions = {
        label: column
        for label, column in question_columns.items()
        if _has_free_text(year_df[column]).any()
    }
    if not available_questions:
        st.info("選択した年度には表示できる自由記述がありません。")
        return

    selected_question = st.segmented_control(
        "設問",
        list(available_questions),
        default=next(iter(available_questions)),
        required=True,
        key="free_text_question",
        width="stretch",
    )
    answer_column = available_questions[selected_question]
    question_text = str(answer_column).replace("\\n", " ").replace("\n", " ").strip()
    st.caption(f"設問: {question_text}")
    query = st.text_input(
        "自由記述を検索",
        placeholder="キーワードを入力して押してください",
        key="free_text_query",
    )
    comment_df = year_df[_has_free_text(year_df[answer_column])].copy()
    comment_df[answer_column] = comment_df[answer_column].astype(str).str.strip()
    comment_df = comment_df[comment_df[answer_column].ne("")]
    if query:
        comment_df = comment_df[comment_df[answer_column].str.contains(query, case=False, na=False)]

    st.caption(f"{selected_year}年度 / {selected_question} / 回答 {len(comment_df):,}件")
    if comment_df.empty:
        st.info("該当する自由記述がありません。")
        return

    display_context = (selected_year, selected_question, query)
    if st.session_state.get("free_text_display_context") != display_context:
        st.session_state["free_text_display_context"] = display_context
        st.session_state["free_text_display_limit"] = 8
    display_limit = st.session_state.get("free_text_display_limit", 8)
    cols = st.columns(2)
    for index, (_, row) in enumerate(comment_df.head(display_limit).iterrows()):
        answer_text = _display_free_text(row[answer_column])
        metadata = " / ".join(
            str(row.get(column, ""))
            for column in ("年度", "年齢", "性別", "居住地")
            if pd.notna(row.get(column, "")) and str(row.get(column, "")).strip()
        )
        pink_choice = ""
        if selected_question == "ピンクを選んだ理由":
            value = str(row.get("幸せを感じるピンク", "")).strip()
            if value and value.lower() != "nan":
                if value.endswith(".0"):
                    value = value[:-2]
                pink_choice = f'<div class="comment-tag">選んだピンク: No.{html.escape(value)}</div>'
        with cols[index % 2]:
            card_html = (
                '<div class="comment-card">'
                f'<div class="comment-meta">{html.escape(metadata)}</div>'
                f'<div class="comment-tag">{html.escape(selected_question)}</div>'
                f'{pink_choice}'
                f'<div class="comment-text">{html.escape(answer_text)}</div>'
                '</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)

    if len(comment_df) > display_limit:
        if st.button(
            f"さらに表示（残り {len(comment_df) - display_limit:,}件）",
            key="free_text_show_more",
        ):
            st.session_state["free_text_display_limit"] = display_limit + 8
            st.rerun()

def render_trend(df):
    if df.empty or "年度" not in df.columns:
        return
    if "年齢" not in df.columns:
        return

    score_col = "幸福度平均" if "幸福度平均" in df.columns else "幸福度スコア" if "幸福度スコア" in df.columns else None
    if score_col is None:
        return

    trend_df = df.copy()
    trend_df[score_col] = pd.to_numeric(trend_df[score_col], errors="coerce")
    trend_df = trend_df.dropna(subset=[score_col])
    if trend_df.empty:
        return

    trend_df = trend_df.groupby(["年度", "年齢"], dropna=False)[score_col].mean().reset_index().rename(columns={score_col: "幸福度平均"})
    trend_df["年度"] = trend_df["年度"].astype(str)
    trend_df["年齢"] = trend_df["年齢"].astype(str)
    trend_df = trend_df[trend_df["年齢"].isin(AGE_ORDER)]
    st.markdown('<div class="sensory-note">年代別の幸福度推移</div>', unsafe_allow_html=True)
    if alt is not None:
        chart = alt.Chart(trend_df).mark_line(point=True).encode(
            x=alt.X("年度:N", title="年度", sort=None),
            y=alt.Y("幸福度平均:Q", title="幸福度平均", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("年齢:N", title="年代", sort=AGE_ORDER),
            detail="年齢:N",
            tooltip=[alt.Tooltip("年度:N", title="年度"), alt.Tooltip("年齢:N", title="年代"), alt.Tooltip("幸福度平均:Q", title="幸福度平均", format=".1f")],
        ).properties(height=340, padding=CHART_PADDING)
        st.altair_chart(chart, use_container_width=True)
    else:
        fallback_df = trend_df.pivot(index="年度", columns="年齢", values="幸福度平均").reindex(columns=AGE_ORDER)
        st.line_chart(fallback_df, use_container_width=True)
