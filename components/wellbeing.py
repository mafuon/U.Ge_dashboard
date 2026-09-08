import re
from math import cos, pi, sin

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None


PENTAGON_ORDER = ["自己実現派", "自己成長派", "自然体派", "社会交流派", "生活充実派"]
PENTAGON_COLORS = {
    "生活充実派": "#73b9c4",
    "社会交流派": "#e89d73",
    "自然体派": "#90b77d",
    "自己成長派": "#b58cc7",
    "自己実現派": "#e4b867",
}
CHART_PADDING = {"left": 16, "right": 28, "top": 14, "bottom": 18}


def _ideal_columns(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    pattern = re.compile(r"^(.*)｜(自己実現派|自己成長派|社会交流派|生活充実派|自然体派)$")
    columns = []
    for column in df.columns:
        match = pattern.match(str(column))
        if match:
            columns.append((column, match.group(1), match.group(2)))
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


def _bar_chart(data: pd.DataFrame, axis_title: str):
    if alt is None:
        st.bar_chart(data.set_index("項目")["合計値"])
        return
    chart = alt.Chart(data).mark_bar().encode(
        x=alt.X("合計値:Q", title=axis_title),
        y=alt.Y("項目:N", sort=alt.EncodingSortField("分類", order="ascending"), title=None, axis=alt.Axis(labelLimit=0, minExtent=285)),
        color=alt.Color("分類:N", scale=alt.Scale(domain=PENTAGON_ORDER, range=[PENTAGON_COLORS[name] for name in PENTAGON_ORDER]), legend=alt.Legend(title="ペンタゴン構成")),
        tooltip=["分類:N", "項目:N", alt.Tooltip("合計値:Q", title="回答値の合計"), "回答数:Q"],
    ).properties(height=max(480, len(data) * 34), padding=CHART_PADDING)
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


def _radar_chart(composition: pd.DataFrame, year):
    if alt is None:
        return
    selected = composition[composition["年度"].eq(year)].set_index("分類").reindex(PENTAGON_ORDER, fill_value=0).reset_index()
    if selected.empty:
        return
    maximum = 50
    angles = [pi / 2 - index * 2 * pi / len(PENTAGON_ORDER) for index in range(len(PENTAGON_ORDER))]
    selected["角度"] = angles
    selected["x"] = selected.apply(lambda row: row["構成比"] / maximum * cos(row["角度"]), axis=1)
    selected["y"] = selected.apply(lambda row: row["構成比"] / maximum * sin(row["角度"]), axis=1)
    selected["表示"] = selected["構成比"].map(lambda value: f"{value:.0f}%")
    selected["描画順"] = range(len(selected))
    polygon = pd.concat([selected, selected.iloc[[0]]], ignore_index=True)
    polygon.loc[polygon.index[-1], "描画順"] = len(selected)

    grid_rows = []
    for level in (10, 20, 30, 40, 50):
        for index, angle in enumerate(angles):
            grid_rows.append({"level": level, "order": index, "x": level / maximum * cos(angle), "y": level / maximum * sin(angle)})
    grid = pd.DataFrame(grid_rows)
    grid = pd.concat(
        [grid, grid.groupby("level", observed=True).head(1).assign(order=len(PENTAGON_ORDER))],
        ignore_index=True,
    )
    axes = pd.DataFrame({"x": [0] * len(angles), "y": [0] * len(angles), "x2": [cos(angle) for angle in angles], "y2": [sin(angle) for angle in angles]})
    labels = pd.DataFrame({"分類": PENTAGON_ORDER, "x": [1.2 * cos(angle) for angle in angles], "y": [1.2 * sin(angle) for angle in angles]})
    scale = alt.Scale(domain=[-1.35, 1.35], nice=False)
    base = alt.Chart().encode(x=alt.X("x:Q", axis=None, scale=scale), y=alt.Y("y:Q", axis=None, scale=scale))
    chart = alt.layer(
        base.mark_line(color="#d8dde2", strokeWidth=1).encode(detail="level:N", order="order:Q").transform_filter(alt.datum.level > 0).properties(data=grid),
        base.mark_rule(color="#d8dde2", strokeWidth=1).encode(x2="x2:Q", y2="y2:Q").properties(data=axes),
        base.mark_line(color="#38b8c8", strokeWidth=2).encode(order="描画順:Q", tooltip=["分類:N", alt.Tooltip("人数:Q", title="人数"), alt.Tooltip("構成比:Q", title="構成比", format=".1f")]).properties(data=polygon),
        base.mark_point(color="#38b8c8", filled=True, size=55).properties(data=selected),
        base.mark_text(dy=-10, color="#5e6772", fontSize=12).encode(text="表示:N").properties(data=selected),
        base.mark_text(color="#5e6772", fontSize=12).encode(text="分類:N").properties(data=labels),
    ).properties(width=360, height=300, padding=CHART_PADDING).configure_view(stroke=None)
    st.altair_chart(chart, width=360, height=300)


def _yearly_radar(df: pd.DataFrame, type_column: str, key: str):
    composition = _yearly_type_composition(df, type_column)
    if composition.empty:
        return
    years = sorted(composition["年度"].unique(), reverse=True)
    selected_year = st.selectbox("年度", years, key=key, width=360)
    _radar_chart(composition, selected_year)


def render_wellbeing_analysis(df: pd.DataFrame):
    current_columns = _current_columns(df)
    ideal_columns = _ideal_columns(df)
    current_df = df[df["現在の幸福度タイプ"].notna()] if "現在の幸福度タイプ" in df.columns else df.iloc[0:0]
    ideal_df = df[df["理想の幸福度タイプ"].notna()] if "理想の幸福度タイプ" in df.columns else df.iloc[0:0]
    current_data = _wellbeing_data(current_df, current_columns)
    ideal_data = _wellbeing_data(ideal_df, ideal_columns)
    if current_data.empty and ideal_data.empty:
        return

    st.markdown('<div id="wellbeing" class="section-anchor"></div><div class="sensory-shell"><div class="section-header section-blue">ウェルビーイング分析</div><div class="sensory-intro">回答者の傾向から、幸福の構成要素を5つのペンタゴンに分類し、心の充足度を多面的に読み解きます。</div></div>', unsafe_allow_html=True)
    if not current_data.empty:
        st.markdown('<div class="sensory-kicker">01</div><h3 class="sensory-title">現在のしあわせ状況</h3><div class="sensory-note">一意に分類できる回答者の回答値を合計し、5つのペンタゴンごとに表示します。</div>', unsafe_allow_html=True)
        _bar_chart(current_data, "現在の幸福スコア（合計）")
        st.markdown("#### 年度別の構成比")
        st.caption("しあわせペンタゴン")
        _yearly_radar(current_df, "現在の幸福度タイプ", "current_happiness_type_year")

    if not ideal_data.empty:
        if not current_data.empty:
            st.markdown('<div class="sensory-divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="sensory-kicker">02</div><h3 class="sensory-title">理想のしあわせ状況</h3><div class="sensory-note">現在・理想ともに一意に分類できる回答者の回答値を合計し、5つのペンタゴンごとに表示します。</div>', unsafe_allow_html=True)
        _bar_chart(ideal_data, "理想の幸福スコア（合計）")
        st.markdown("#### 年度別の構成比")
        st.caption("しあわせペンタゴン")
        _yearly_radar(ideal_df, "理想の幸福度タイプ", "ideal_happiness_type_year")