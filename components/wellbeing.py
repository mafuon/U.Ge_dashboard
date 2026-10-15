import re
from math import cos, pi, sin

import pandas as pd
import plotly.express as px
import streamlit as st

from components.chart_data import show_chart_data

try:
    import altair as alt
except Exception:
    alt = None


PENTAGON_ORDER = ["自己実現派", "自己成長派", "自然体派", "社会交流派", "生活充実派"]
PENTAGON_COLORS = {
    "自己実現派": "#F9D65D",
    "自己成長派": "#CBA6E8",
    "自然体派": "#A3D977",
    "社会交流派": "#E26A6A",
    "生活充実派": "#7DB1E8",
}
CHART_PADDING = {"left": 16, "right": 28, "top": 14, "bottom": 18}
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "pan2d",
        "select2d",
        "lasso2d",
        "autoscale2d",
        "resetScale2d",
        "zoomIn2d",
        "zoomOut2d",
        "toggleSpikelines",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
    ],
}


def _ideal_columns(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    columns = []
    for column in df.columns:
        column_name = str(column)
        category = next((name for name in PENTAGON_ORDER if column_name.endswith(name)), None)
        if category and "｜" in column_name:
            columns.append((column, column_name.rsplit("｜", 1)[0], "".join(category.split())))
    return columns


CURRENT_ITEMS = {
    "生活充実派": ["犯罪や災害の不安はない", "金銭的に充実、安定している", "身体は元気である", "デジタル化を取り入れ暮らしている"],
    "社会交流派": ["信頼する人、心を許せる人がいる", "人の役に立っている", "周囲や社会から自分が認められている", "多くの出会いがある"],
    "自然体派": ["ゆとりや自分の時間がある", "自由に意思決定ができる", "季節を感じて暮らしている", "素の自分で居られる"],
    "自己成長派": ["自分が成長出来ていると感じられる", "何かに夢中・没頭できている", "目標が達成されている", "勉強の機会や場がある"],
    "自己実現派": ["自分に自信がある", "生活によい変化や刺激がある", "悩みや不満がない", "好きなことができている"],
}
CURRENT_CATEGORY_MAP = {
    "生活充実": "生活充実派",
    "自己発信": "社会交流派",
    "自然体": "自然体派",
    "自己成長": "自己成長派",
    "自己実現": "自己実現派",
}


def current_pentagon_scores(df: pd.DataFrame) -> pd.DataFrame:
    axis_groups = {
        "Q1_自己実現派": ["自己実現"],
        "Q2_自己成長派": ["自己成長"],
        "Q3_社会交流派": ["自己発信", "社会交流"],
        "Q4_生活充実派": ["生活充実"],
        "Q5_自然体派": ["自然体"],
    }
    scores = pd.DataFrame(index=df.index)
    for target, tokens in axis_groups.items():
        columns = [
            column for column in df.columns
            if column.startswith("質問") and any(token in column for token in tokens)
        ]
        if columns:
            values = df[columns].apply(pd.to_numeric, errors="coerce")
            scale_max = 7 if values.max().max() > 5 else 5
            scores[target] = ((values.mean(axis=1) - 1) / (scale_max - 1) * 6).clip(0, 6)
    return scores


def current_pentagon_types(scores: pd.DataFrame) -> pd.Series:
    labels = {
        "Q1_自己実現派": "自己実現派",
        "Q2_自己成長派": "自己成長派",
        "Q3_社会交流派": "社会交流派",
        "Q4_生活充実派": "生活充実派",
        "Q5_自然体派": "自然体派",
    }
    if scores.empty:
        return pd.Series(pd.NA, index=scores.index, dtype="string")
    maximum = scores.max(axis=1)
    unique = scores.eq(maximum, axis=0).sum(axis=1).eq(1)
    types = scores.fillna(float("-inf")).idxmax(axis=1).map(labels)
    return types.where(unique).astype("string")


def _current_columns(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    counters = {category: 0 for category in PENTAGON_ORDER}
    columns = []
    for column in df.columns:
        match = re.match(r"^質問\d+｜(.+)$", str(column))
        if not match:
            continue
        category = CURRENT_CATEGORY_MAP.get(match.group(1).replace(" ", ""))
        if category is None:
            continue
        item = CURRENT_ITEMS[category][counters[category]]
        counters[category] += 1
        columns.append((column, item, category))
    return columns


def _wellbeing_data(df: pd.DataFrame, columns: list[tuple[str, str, str]]) -> pd.DataFrame:
    rows = []
    for column, item, category in columns:
        values = pd.to_numeric(df[column], errors="coerce").dropna()
        if values.empty:
            continue
        rows.append({
            "項目": item,
            "分類": category,
            "回答数": len(values),
            "合計値": values.sum(),
        })
    if not rows:
        return pd.DataFrame(columns=["項目", "分類", "回答数", "合計値"])

    data = pd.DataFrame(rows)
    data["分類"] = pd.Categorical(data["分類"], categories=PENTAGON_ORDER, ordered=True)
    return data.sort_values("分類").reset_index(drop=True)


def _category_averages(df: pd.DataFrame, columns: list[tuple[str, str, str]]) -> pd.Series:
    values = {}
    for category in PENTAGON_ORDER:
        category_columns = [column for column, _, column_category in columns if column_category == category]
        if category_columns:
            category_values = df[category_columns].apply(pd.to_numeric, errors="coerce")
            values[category] = category_values.stack().mean()
    averages = pd.Series(values, dtype="float64")
    averages.index = [category for category in PENTAGON_ORDER if category in values]
    return averages


def render_pentagon_structure_relation():
    with st.expander("幸福度スコアとペンタゴン別レーダーチャートの関係性"):
        st.markdown(
            """
            <div style="background-color:#f2f2f2; padding:15px; border-radius:8px; font-size:0.72rem;">
            このダッシュボードでは、幸福度を「カテゴリ別の構造」と「全体平均値」の2つの視点から表示しています。

            **レーダーチャート（ペンタゴン分析）**  
            各幸福カテゴリ（自己実現・自己成長・自然体・社会交流・生活充実）に含まれる質問群の平均値を算出し、5軸で表示しています。  
            これは「カテゴリ別の構造的バランス」を可視化するための指標です。

            **スコアカード（現在の幸福度スコア／理想の幸福度スコア（平均））**  
            全質問（例：20問）の回答を総合平均し、単一の数値として算出しています。  
            これは「全体幸福度の総合指標」を示すものです。

            そのため、レーダーチャートの数値とスコアカードの値には差が生じますが、両者は異なる分析目的に基づいて算出されています。
            </div>
            """,
            unsafe_allow_html=True,
        )

def render_happiness_category_comparison(df: pd.DataFrame):
    current_averages = _category_averages(df, _current_columns(df))
    ideal_averages = _category_averages(df, _ideal_columns(df))
    categories = [category.removesuffix("派") for category in PENTAGON_ORDER]
    comparison = pd.DataFrame({
        "カテゴリ": categories,
        "現在の幸福状態": [current_averages.get(category, float("nan")) for category in PENTAGON_ORDER],
        "理想の幸福状態": [ideal_averages.get(category, float("nan")) for category in PENTAGON_ORDER],
    })
    comparison = comparison.dropna(subset=["現在の幸福状態", "理想の幸福状態"], how="all")
    if comparison.empty:
        return

    st.markdown('<div id="pentagon" class="section-anchor"></div><div class="section-number">02</div><div class="pentagon-chart-divider"></div>', unsafe_allow_html=True)
    st.markdown("### ペンタゴン別")
    st.caption("現在の状況と幸せに必要だと思うことのアンケート結果から導き出された、現在と理想の状態をあらわす比較図です")
    chart_data = comparison.melt("カテゴリ", var_name="状態", value_name="平均値").dropna(subset=["平均値"])
    figure = px.line_polar(
        chart_data,
        r="平均値",
        theta="カテゴリ",
        color="状態",
        line_close=True,
        markers=True,
        color_discrete_map={"現在の幸福状態": "#2f80ed", "理想の幸福状態": "#e74c3c"},
    )
    figure.update_traces(fill="toself", opacity=0.55)
    figure.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, max(6, chart_data["平均値"].max())])),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=60, b=20),
        height=430,
    )
    st.plotly_chart(figure, use_container_width=True, config=PLOTLY_CONFIG)
    show_chart_data(chart_data, "pentagon-comparison")


def _bar_chart(data: pd.DataFrame, axis_title: str):
    if alt is None:
        st.bar_chart(data.set_index("項目")["合計値"])
        return
    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X("合計値:Q", title=axis_title),
        y=alt.Y(
            "項目:N",
            sort=alt.EncodingSortField("分類", order="ascending"),
            title=None,
            axis=alt.Axis(labelLimit=0, labelFontSize=13, labelColor="#808495", minExtent=285),
        ),
        color=alt.Color(
            "分類:N",
            scale=alt.Scale(domain=PENTAGON_ORDER, range=[PENTAGON_COLORS[name] for name in PENTAGON_ORDER]),
            legend=alt.Legend(title="ペンタゴン構成", orient="right", direction="vertical", offset=0),
        ),
        tooltip=["分類:N", "項目:N", alt.Tooltip("合計値:Q", title="回答値の合計"), "回答数:Q"],
    ).properties(height=max(480, len(data) * 34), padding=CHART_PADDING).configure_legend(
        labelFontSize=13,
        titleFontSize=13,
        labelColor="#808495",
        titleColor="#808495",
    )
    st.altair_chart(chart, use_container_width=True)


def _yearly_type_composition(df: pd.DataFrame, type_column: str) -> pd.DataFrame:
    if "年度" not in df.columns or type_column not in df.columns:
        return pd.DataFrame(columns=["年度", "分類", "人数", "構成比"])
    composition = (
        df.dropna(subset=[type_column])
        .groupby(["年度", type_column], as_index=False)
        .size()
        .rename(columns={type_column: "分類", "size": "人数"})
    )
    if composition.empty:
        return composition
    composition["構成比"] = composition.groupby("年度")["人数"].transform(lambda values: values.div(values.sum()).mul(100))
    composition["分類"] = pd.Categorical(composition["分類"], categories=PENTAGON_ORDER, ordered=True)
    return composition.sort_values(["年度", "分類"]).reset_index(drop=True)


PENTAGON_PIE_COLORS = {
    "自己実現派": "#F9D65D",
    "自己成長派": "#CBA6E8",
    "自然体派": "#A3D977",
    "社会交流派": "#E26A6A",
    "生活充実派": "#7DB1E8",
}


def _darken_hex_color(color: str, factor: float = 0.8) -> str:
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return f"#{int(red * factor):02X}{int(green * factor):02X}{int(blue * factor):02X}"


def _pie_chart(composition: pd.DataFrame, year):
    selected = composition[composition["年度"].eq(year)].set_index("分類").reindex(PENTAGON_ORDER, fill_value=0).reset_index()
    if selected.empty:
        return
    selected = selected[["分類", "構成比"]].copy()
    selected["構成比"] = pd.to_numeric(selected["構成比"], errors="coerce").fillna(0)
    figure = px.pie(
        selected,
        names="分類",
        values="構成比",
        color="分類",
        category_orders={"分類": PENTAGON_ORDER},
        color_discrete_map=PENTAGON_PIE_COLORS,
        hole=0.5,
    )
    figure.update_traces(texttemplate="%{label}<br>%{percent}", textposition="inside", hovertemplate="%{label}<br>構成比: %{value:.1f}%<extra></extra>")
    figure.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(size=14),
        showlegend=True,
        legend=dict(
            orientation="v",
            x=0.735,
            xref="container",
            y=0.5,
            xanchor="left",
            yanchor="middle",
            font=dict(size=13, color="#808495"),
        ),
        margin=dict(l=40, r=40, t=60, b=40),
        height=430,
    )
    st.plotly_chart(figure, width="stretch", config=PLOTLY_CONFIG)
    show_chart_data(selected, f"pentagon-donut-{year}")


def _yearly_composition_bar(composition: pd.DataFrame):
    figure = px.bar(
        composition,
        x="構成比",
        y="年度",
        color="分類",
        orientation="h",
        category_orders={"分類": PENTAGON_ORDER},
        color_discrete_map=PENTAGON_PIE_COLORS,
    )
    figure.update_layout(
        barmode="stack",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(size=14),
        showlegend=False,
        margin=dict(l=60, r=60, t=30, b=60),
        xaxis=dict(range=[0, 100], title="構成比（%）"),
        yaxis=dict(title=None, categoryorder="array", categoryarray=sorted(composition["年度"].unique())),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            font=dict(size=13),
        ),
        height=max(180, len(composition["年度"].unique()) * 62),
    )
    figure.update_traces(hovertemplate="%{y}<br>%{fullData.name}: %{x:.1f}%<extra></extra>")
    st.markdown('<div class="yearly-composition-chart-anchor"></div>', unsafe_allow_html=True)
    st.plotly_chart(figure, width="stretch", config=PLOTLY_CONFIG)


def _yearly_radar(df: pd.DataFrame, type_column: str, key: str):
    composition = _yearly_type_composition(df, type_column)
    if composition.empty:
        return
    years = sorted(composition["年度"].unique(), reverse=True)
    _pie_chart(composition, years[0])
    _yearly_composition_bar(composition)


def render_wellbeing_intro():
    st.markdown('<div id="wellbeing" class="section-anchor"></div><div class="sensory-shell"><div class="section-header section-blue">ウェルビーイング分析</div><div class="sensory-intro">回答者の傾向から、幸福の構成要素を5つのペンタゴンに分類し、心の充足度を多面的に読み解きます。</div></div>', unsafe_allow_html=True)


def render_wellbeing_analysis(df: pd.DataFrame):
    current_columns = _current_columns(df)
    ideal_columns = _ideal_columns(df)
    current_df = df[df["現在の幸福度タイプ"].notna()] if "現在の幸福度タイプ" in df.columns else df.iloc[0:0]
    ideal_df = df[df["理想の幸福度タイプ"].notna()] if "理想の幸福度タイプ" in df.columns else df.iloc[0:0]
    current_data = _wellbeing_data(current_df, current_columns)
    ideal_data = _wellbeing_data(ideal_df, ideal_columns)
    if current_data.empty and ideal_data.empty:
        return

    if not current_data.empty:
        render_happiness_category_comparison(df)
        st.markdown('<div id="current-happiness" class="section-anchor"></div><div class="sensory-kicker">03</div><h3 class="sensory-title">現在のしあわせ状況</h3><div class="sensory-note">一意に分類できる回答者の回答合計値</div>', unsafe_allow_html=True)
        _bar_chart(current_data, "現在の幸福スコア（合計）")
        st.markdown('<div class="happiness-chart-title">年度別ペンタゴン構成比推移</div>', unsafe_allow_html=True)
        st.caption("しあわせペンタゴン")
        _yearly_radar(current_df, "現在の幸福度タイプ", "current_happiness_type_year")

    if not ideal_data.empty:
        if not current_data.empty:
            st.markdown('<div class="sensory-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div id="ideal-happiness" class="section-anchor"></div><div class="sensory-kicker">04</div><h3 class="sensory-title">理想のしあわせ状況</h3><div class="sensory-note">一意に分類できる回答者の回答合計値</div>', unsafe_allow_html=True)
        _bar_chart(ideal_data, "理想の幸福スコア（合計）")
        st.markdown('<div class="happiness-chart-title">年度別ペンタゴン構成比推移</div>', unsafe_allow_html=True)
        st.caption("しあわせペンタゴン")
        _yearly_radar(ideal_df, "理想の幸福度タイプ", "ideal_happiness_type_year")