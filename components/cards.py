import math

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None


RADAR_COLUMNS = [
    "Q1_自己実現派",
    "Q2_自己成長派",
    "Q3_社会交流派",
    "Q4_生活充実派",
    "Q5_自然体派",
]

RADAR_LABELS = ["自己実現派", "自己成長派", "社会交流派", "生活充実派", "自然体派"]
SHOW_CURRENT_HAPPINESS_COMPOSITION = False


def _happiness_type_radar(df):
    column = next((name for name in ("現在の幸福状態", "現在の幸福状況（集約分）") if name in df.columns), None)
    if column is None:
        return None

    responses = df[column].dropna().astype(str)
    counts = [responses.str.contains(label, regex=False).sum() for label in RADAR_LABELS]
    total = sum(counts)
    if total == 0:
        return None

    return pd.DataFrame({
        "項目": RADAR_LABELS,
        "スコア": [count / total * 100 for count in counts],
        "人数": counts,
    })


def _radar_chart(radar_df, max_score, color, score_suffix):
    points = []
    labels = []
    grid_points = []
    for index, row in radar_df.iterrows():
        angle = math.radians(90 - (index * 360 / len(RADAR_LABELS)))
        radius = row["スコア"] / max_score
        score_radius = min(radius + 0.12, 0.9)
        points.append({
            "項目": row["項目"],
            "スコア": row["スコア"],
            "人数": row.get("人数", pd.NA),
            "順序": index,
            "x": radius * math.cos(angle),
            "y": radius * math.sin(angle),
            "表示スコア": f"{row['スコア']:.0f}%" if max_score == 100 else f"{row['スコア']:.1f}",
            "スコアx": score_radius * math.cos(angle),
            "スコアy": score_radius * math.sin(angle),
        })
        score_text = f"{row['スコア']:.0f}%" if max_score == 100 else f"{row['スコア']:.1f} / 6"
        label_x = 1.18 * math.cos(angle)
        label_y = 1.18 * math.sin(angle)
        labels.extend([
            {"表示ラベル": row["項目"], "x": label_x, "y": label_y},
            {"表示ラベル": score_text, "x": label_x, "y": label_y - 0.13},
        ])
        for level in range(1, 6):
            grid_radius = level / 5
            grid_points.append({"水準": level, "順序": index, "x": grid_radius * math.cos(angle), "y": grid_radius * math.sin(angle)})

    points.append({**points[0], "順序": len(points)})
    for level in range(1, 6):
        level_points = [point for point in grid_points if point["水準"] == level]
        grid_points.append({**level_points[0], "順序": len(RADAR_LABELS)})

    polygon_df = pd.DataFrame(points)
    grid_df = pd.DataFrame(grid_points)
    label_df = pd.DataFrame(labels)
    chart = (
        alt.Chart(grid_df)
        .mark_line(color="#d7dce2", strokeWidth=1)
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[-1.35, 1.35]), axis=None),
            y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.35, 1.35]), axis=None),
            detail="水準:N",
            order="順序:Q",
        )
        + alt.Chart(polygon_df)
        .mark_line(point=alt.OverlayMarkDef(size=55, filled=True), strokeWidth=2.5, color=color)
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[-1.35, 1.35]), axis=None),
            y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.35, 1.35]), axis=None),
            order="順序:Q",
            tooltip=[alt.Tooltip("項目:N"), alt.Tooltip("スコア:Q", format=".1f", title=f"スコア（{score_suffix}）"), alt.Tooltip("人数:Q")],
        )
        + alt.Chart(label_df)
        .mark_text(fontSize=12, color="#58616b")
        .encode(
            x=alt.X("x:Q", scale=alt.Scale(domain=[-1.35, 1.35]), axis=None),
            y=alt.Y("y:Q", scale=alt.Scale(domain=[-1.35, 1.35]), axis=None),
            text="表示ラベル:N",
        )
    )
    return chart.properties(width=340, height=340)


def render_metric_cards(df):
    if df.empty:
        st.warning("条件に一致するデータがありません。")
        return

    n_records = len(df)
    score_series = df["幸福度平均"] if "幸福度平均" in df.columns else df["幸福度スコア"] if "幸福度スコア" in df.columns else pd.Series(dtype=float)
    avg_score = pd.to_numeric(score_series, errors="coerce").mean()
    avg_score = 0 if pd.isna(avg_score) else avg_score
    happiness_out_of_six = round((avg_score / 100) * 6, 1)

    columns = st.columns([1, 1, 2] if SHOW_CURRENT_HAPPINESS_COMPOSITION else [1, 1])
    col1, col2 = columns[:2]

    with col1:
        st.markdown(
            f"""
            <div class="metric-panel">
                <div class="metric-label">回答者数</div>
                <div class="metric-value">{n_records}</div>
                <div class="metric-unit">人</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-panel">
                <div class="metric-label">現在の幸福度スコア（平均）</div>
                <div class="metric-value">{happiness_out_of_six}</div>
                <div class="metric-unit">/ 6</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if SHOW_CURRENT_HAPPINESS_COMPOSITION:
        col3 = columns[2]
        with col3:
            type_radar = _happiness_type_radar(df)
            default_values = [4.2, 4.4, 4.0, 4.6, 4.8]
            if type_radar is not None:
                radar_df = type_radar
                max_score = 100
                color = "#35bcc8"
                score_suffix = "%"
                score_label = f"集計タイプ数：{int(radar_df['人数'].sum())}"
            elif all(column in df.columns for column in RADAR_COLUMNS):
                radar_data = df[RADAR_COLUMNS].apply(pd.to_numeric, errors="coerce").mean().reset_index()
                radar_data.columns = ["項目", "スコア"]
                radar_values = [
                    float(score) if pd.notna(score) else default_values[index]
                    for index, score in enumerate(radar_data["スコア"])
                ]
                radar_df = pd.DataFrame({"項目": RADAR_LABELS, "スコア": [min(max(value, 0), 6) for value in radar_values]})
                max_score = 6
                color = "#FFB6B9"
                score_suffix = "/ 6"
                score_label = f"平均スコア：{radar_df['スコア'].mean():.1f} / 6"
            else:
                radar_df = pd.DataFrame({"項目": RADAR_LABELS, "スコア": default_values})
                max_score = 6
                color = "#FFB6B9"
                score_suffix = "/ 6"
                score_label = f"平均スコア：{radar_df['スコア'].mean():.1f} / 6"

            with st.container(border=True):
                st.markdown('<div class="pentagon-title">現在の幸福状態の構成</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="score-badge">{score_label}</div>', unsafe_allow_html=True)

                if alt is not None:
                    st.altair_chart(_radar_chart(radar_df, max_score, color, score_suffix), width="content")
                else:
                    st.write(radar_df.set_index("項目"))
