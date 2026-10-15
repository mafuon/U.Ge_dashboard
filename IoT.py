from io import BytesIO
from html import escape
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.sensory import COLOR_SWATCHES, DEFAULTS
from components.wellbeing import PENTAGON_ORDER, current_pentagon_scores, current_pentagon_types
from modules.data_loader import (
    AGE_COL,
    COLOR_COL,
    COURSE_COL,
    GENDER_COL,
    count_colors,
    filter_iot,
    load_data,
)

plt.rcParams["font.family"] = "Meiryo"


def render_theme_separator() -> None:
    st.html(
        '<div class="theme-separator" style="padding:100pt 0;">'
        '<hr style="margin:0; border:0; border-top:1px solid #A6B3C2;">'
        '</div>'
    )


def render_choice_list(column_label: str, choices: list[str]) -> None:
    items = "".join(
        f'<li style="margin:6px 0;">選択肢{number}：{escape(content)}</li>'
        for number, content in enumerate(choices, start=1)
    )
    st.markdown(
        f'<div style="font-size:14px; line-height:1.7; margin:12px 0 28px;">'
        f'<strong>選択肢内容一覧（{escape(column_label)}）</strong>'
        f'<ul style="padding-left:22px; margin-top:8px;">{items}</ul></div>',
        unsafe_allow_html=True,
    )


def render_high_resolution_chart(figure: go.Figure, filename: str) -> None:
    margin = figure.layout.margin.to_plotly_json() if figure.layout.margin else {}
    padded_margin = {
        "l": max(int(margin.get("l", 0)), 70) + 30,
        "r": max(int(margin.get("r", 0)), 30) + 30,
        "t": max(int(margin.get("t", 0)), 50) + 30,
        "b": max(int(margin.get("b", 0)), 50) + 30,
        "pad": 20,
    }
    figure.update_layout(margin=padded_margin, autosize=True)
    figure.update_traces(cliponaxis=False)
    export_width = int(figure.layout.width or 1600)
    export_height = int(figure.layout.height or 600)
    png_bytes = figure.to_image(
        format="png",
        width=max(export_width, 1600),
        height=max(export_height, 600),
        scale=3,
    )
    st.session_state.setdefault("chart_exports", {})[f"{filename}.png"] = png_bytes
    st.plotly_chart(
        figure,
        width="stretch",
        config={
            "displayModeBar": True,
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": filename,
                "scale": 3,
            },
        },
    )
    st.download_button(
        label="⬇️ このグラフを高解像度PNGでダウンロード",
        data=png_bytes,
        file_name=f"{filename}.png",
        mime="image/png",
        key=f"download_{filename}",
    )


st.set_page_config(
    page_title="スマートホーム志向",
    layout="wide",
)

st.title("スマートホーム（IoT）志向の実データ分析")
st.caption("各グラフのカメラアイコン、または下のボタンからPowerPoint向けの高解像度PNG（scale=3）を一括ダウンロードできます。")

try:
    df = load_data()
except (OSError, UnicodeError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
    st.error(f"CSVを読み込めませんでした：{exc}")
    st.stop()

data_path = Path(__file__).resolve().parent / "data" / "U.Ge「幸せ」アンケート集計データ_version27_.csv"
source_column_count = len(df.columns)
details_placeholder = st.empty()

if df.empty:
    st.warning("CSVにデータ行がありません。")
    st.stop()

lifestyle_columns = [
    column for column in df.columns
    if "理想の暮らし" in column or column.startswith("1つ以上、5つまで選んでください。")
]
required_columns = ["タイムスタンプ", "◆性別", "◆年齢"]
missing_columns = [column for column in required_columns if column not in df.columns]
if missing_columns or not lifestyle_columns:
    st.error(
        "集計に必要な列がありません："
        + "、".join(missing_columns + ([] if lifestyle_columns else ["理想の暮らしの回答列"]))
    )
    st.stop()

df = df.copy()
df["年度"] = pd.to_datetime(df["タイムスタンプ"], errors="coerce").dt.year.astype("Int64")
df["年代"] = df[AGE_COL].astype("string").str.strip()
df["性別"] = df[GENDER_COL].astype("string").str.strip()
valid_rows = (
    df["年度"].notna()
    & df["年代"].str.fullmatch(r"\d+代(?:～|〜)?", na=False)
    & df["性別"].notna()
    & df["性別"].ne("")
)
invalid_count = int((~valid_rows).sum())

iot_mask = pd.Series(False, index=df.index)
for column in lifestyle_columns:
    answers = df[column].astype("string")
    iot_mask |= (
        answers.str.contains("スマートホーム", regex=False, na=False)
        | answers.str.contains(r"(?:^|[,|\n])\s*18\s*(?:$|[,|\n])", regex=True, na=False)
    )

df_iot = df.loc[valid_rows & iot_mask].copy()
iot_df = filter_iot(df)
iot_colors = count_colors(iot_df)

target = "スマートホーム（IoT）で効率的な暮らし"
choices = DEFAULTS["理想の暮らし方"]
choice_map = {str(number): choice for number, choice in enumerate(choices, start=1)}
ranking_source = df.loc[df["年度"].notna(), ["年度", *lifestyle_columns]].copy()
ranking_source["回答者"] = ranking_source.index
answers = ranking_source.melt(
    id_vars=["年度", "回答者"],
    value_vars=lifestyle_columns,
    value_name="回答",
)
answers["回答"] = answers["回答"].astype("string").str.split(r"[,|\n]", regex=True)
answers = answers.explode("回答")
answers["回答"] = answers["回答"].str.strip()
answers = answers.loc[answers["回答"].notna() & answers["回答"].ne("")].copy()
answers["暮らし"] = answers["回答"].map(choice_map)
named_answers = answers["回答"].isin(choices)
answers.loc[named_answers, "暮らし"] = answers.loc[named_answers, "回答"]
unknown_count = int(answers["暮らし"].isna().sum())
with details_placeholder.container():
    with st.expander("データ件数・集計条件", expanded=False) as details:
        st.caption(f"読み込み元：{data_path.name}")
        st.write(f"データ件数：{len(df):,}件")
        st.write(f"列数：{source_column_count:,}列")
        st.write(f"IoT志向者数（集計対象）：{len(df_iot):,}件")
        st.caption(
            "理想の暮らしの回答に「スマートホーム」または選択肢18が含まれる回答者を抽出。"
            "年度は回答日時の暦年、年代はCSVの年代カテゴリを使用しています。"
        )
        st.caption(
            "暮らしランキングは各年の全回答者を集計しています（IoT志向者だけに限定しません）。"
            "複数回答は1人・1選択肢につき1件、同数は同順位（1位・1位・3位）です。"
            "未選択の年は順位なしとします。"
        )
        if invalid_count:
            st.warning(f"年度・性別・年代を確認できない{invalid_count}件を性年代構成比の集計から除外します。")
        if unknown_count:
            st.warning(f"選択肢の対応表で確認できない回答{unknown_count}件を暮らしランキングから除外します。")
answers = answers.dropna(subset=["暮らし"]).drop_duplicates(["年度", "回答者", "暮らし"])
ranking = answers.groupby(["年度", "暮らし"]).size().reset_index(name="件数")
ranking["順位"] = ranking.groupby("年度")["件数"].rank(method="min", ascending=False).astype("Int64")
ranking_years = [2023, 2024, 2025, 2026]
rank_per_year = (
    ranking.loc[ranking["暮らし"].eq(target), ["年度", "順位", "件数"]]
    .set_index("年度")
    .reindex(ranking_years)
    .reset_index()
)
headline_start_year, headline_end_year = 2023, 2025
headline_ranks = rank_per_year.set_index("年度")["順位"]
rank_start = headline_ranks.loc[headline_start_year]
rank_end = headline_ranks.loc[headline_end_year]
start_label = f"{int(rank_start)}位" if pd.notna(rank_start) else "順位なし"
end_label = f"{int(rank_end)}位" if pd.notna(rank_end) else "順位なし"
if pd.notna(rank_start) and pd.notna(rank_end):
    rank_diff = int(rank_start - rank_end)
    trend_text = (
        f"{rank_diff}位上昇" if rank_diff > 0
        else f"{abs(rank_diff)}位下降" if rank_diff < 0
        else "順位は変わりません。"
    )
else:
    trend_text = "順位データが不足しています。"
st.markdown(
    f"""
<div style="background-color:#f0f8ff; color:#17202a; padding:28px 16px; border-radius:8px; text-align:center;">
    <h3 style="color:#007ACC;">理想の暮らしランキング推移</h3>
    <p style="font-size:20px; font-weight:bold;">{target}</p>
    <p style="font-size:clamp(24px, 4vw, 40px); font-weight:bold; line-height:1.5; margin:20px 0 8px;">{headline_start_year}年　{start_label} → {headline_end_year}年　{end_label}</p>
    <p style="font-size:clamp(36px, 6vw, 56px); font-weight:bold; color:#007ACC; line-height:1.3; margin:8px 0;">{trend_text}</p>
</div>
""",
    unsafe_allow_html=True,
)
if pd.isna(rank_start) or pd.isna(rank_end):
    st.info("順位の増減を比較するには、2023年と2025年の両方の順位が必要です。")
if rank_per_year["順位"].notna().any():
    ranks = [
        int(rank) if pd.notna(rank) else None
        for rank in rank_per_year["順位"]
    ]
    fig_rank = go.Figure(go.Scatter(
        x=ranking_years,
        y=ranks,
        mode="lines+markers+text",
        line=dict(color="#007ACC", width=3),
        marker=dict(size=10),
        text=[f"{rank}位" if rank is not None else "" for rank in ranks],
        textposition="top center",
        connectgaps=False,
        hovertemplate="年度：%{x}<br>順位：%{y}位<extra></extra>",
    ))
    fig_rank.update_layout(
        title=f"{target}｜順位推移（2023〜2026）",
        xaxis=dict(title="年度", tickmode="array", tickvals=ranking_years, tickformat="d"),
        yaxis=dict(title="順位（数字が小さいほど上位）", autorange="reversed", dtick=1),
        height=400,
    )
    render_high_resolution_chart(fig_rank, "smart_home_trend_highres")
else:
    st.info("2023〜2026年のIoTの順位がないため、順位推移グラフを表示できません。")
st.caption(
    "※ 2026年は『理想の暮らし』の選択肢が3件追加されています。"
    "選択肢数が異なるため、年ごとの順位比較には注意が必要です。"
)
with st.expander("理想の暮らしの年度別ランキングを表示"):
    st.dataframe(rank_per_year, width="stretch", hide_index=True)
    st.dataframe(
        ranking.loc[ranking["年度"].isin(ranking_years)].sort_values(["年度", "順位", "暮らし"]),
        width="stretch",
        hide_index=True,
    )

render_theme_separator()
st.subheader("年度別・年代別／性別のIoT志向率（2024〜2026）")
details.markdown("**年代別・性別のIoT志向率（2024〜2026）**")
details.caption(
    "IoT志向率＝各年・各層のIoT志向者数 ÷ 同じ年・同じ層の回答者数 × 100。"
    "年代別は男女合計、性別は全年代合計です。積み上げや合計100％への正規化は行いません。"
)
comparison_years = [2024, 2025, 2026]
comparison_df = df.loc[valid_rows & df["年度"].isin(comparison_years), ["年度", "年代", "性別"]].copy()
comparison_df["IoT志向"] = iot_mask.loc[comparison_df.index]
if comparison_df.empty:
    st.warning("2024〜2026年に集計可能な回答がありません。")
    st.stop()

missing_years = sorted(set(comparison_years) - set(comparison_df["年度"].unique()))
if missing_years:
    st.warning("回答がないため表示できない年：" + "、".join(str(year) for year in missing_years))

age_order = sorted(comparison_df["年代"].unique(), key=lambda value: int(value.split("代")[0]))
for category, label, order in [
    ("年代", "年代別", age_order),
    ("性別", "性別", sorted(comparison_df["性別"].unique())),
]:
    rate_data = (
        comparison_df.groupby(["年度", category])["IoT志向"]
        .agg(回答者数="size", IoT志向者数="sum")
        .reset_index()
    )
    rate_data["IoT志向率"] = rate_data["IoT志向者数"].div(rate_data["回答者数"]).mul(100)
    rate_data["年度"] = rate_data["年度"].astype(str)
    fig_rate = px.bar(
        rate_data,
        x=category,
        y="IoT志向率",
        color="年度",
        barmode="group",
        category_orders={category: order, "年度": [str(year) for year in comparison_years]},
        color_discrete_map={"2024": "#007ACC", "2025": "#28A98B", "2026": "#E69F00"},
        custom_data=["IoT志向者数", "回答者数"],
        title=f"{label}のIoT志向率（2024〜2026）",
        labels={"IoT志向率": "IoT志向率（%）"},
    )
    fig_rate.update_layout(
        xaxis=dict(type="category"),
        yaxis=dict(ticksuffix="%", rangemode="tozero"),
        legend_title_text="年度",
        height=450,
    )
    fig_rate.update_traces(
        hovertemplate=(
            f"{category}：%{{x}}<br>"
            "IoT志向率：%{y:.1f}%<br>"
            "IoT志向者：%{customdata[0]}人／回答者：%{customdata[1]}人"
            "<extra>%{fullData.name}年</extra>"
        ),
    )
    rate_filename = (
        "iot_propensity_by_age_highres"
        if category == "年代"
        else "iot_propensity_by_gender_highres"
    )
    render_high_resolution_chart(fig_rate, rate_filename)
    st.markdown("**グラフから見える傾向（2024〜2026年）**")
    if category == "年代":
        st.markdown(
            "**30代では、IoT志向が年々高まっています。** "
            "2026年には、年代別で最も高い志向率となっています。"
        )
        st.markdown(
            "**40代は、比較的高い水準を維持しています。** "
            "2026年にやや下がるものの、3年間を通して大きな変動はありません。"
        )
        st.markdown(
            "**40・50代は、3年間とも20代より志向率が高くなっています。** "
            "一方、60代は2025年に高まり、2026年には低下しており、年代によって動きは異なります。"
        )
    else:
        st.markdown(
            "**男性のほうが、3年間ともIoTへの志向が強く表れています。** "
            "2025年に高まり、2026年には下がっていますが、女性を上回っています。"
        )
        st.markdown(
            "**女性の志向率は、3年間でほぼ横ばいです。** "
            "男女の差が最も大きいのは2025年で、2026年にはその差が縮まっています。"
        )

df_2026 = df.loc[df["年度"].eq(2026)].copy()
iot_mask_2026 = iot_mask.loc[df_2026.index]
df_iot_2026 = df_2026.loc[iot_mask_2026].copy()
details.markdown("**2026年のIoT支持者抽出結果**")
details.caption(
    "2026年に回答した全回答者が対象です。理想の暮らしに「スマートホーム」"
    "または選択肢18を含む回答者をIoT支持者として抽出しています。"
    "この抽出では性別・年代の欠損による除外は行いません。"
)
if df_2026.empty:
    st.warning("2026年の回答がないため、IoT支持者の抽出結果を表示できません。")
else:
    respondent_col, supporter_col, rate_col = details.columns(3)
    respondent_col.metric("2026年の回答者数", f"{len(df_2026):,}人")
    supporter_col.metric("2026年のIoT支持者数", f"{len(df_iot_2026):,}人")
    rate_col.metric("2026年のIoT支持率", f"{len(df_iot_2026) / len(df_2026) * 100:.1f}%")

render_theme_separator()
st.subheader("高級感の定義（DF列）｜IoT支持者 vs 全体")
luxury_column = (
    "2026年追加｜あなたにとって、日々のくらしの中で最も「高級（贅沢）」だと感じるのは、"
    "どのような状態・体験ですか？次の中からあなたに最も近いものを1つだけ選んでください。"
)
if luxury_column not in df.columns:
    st.error("高級感の定義（DF列）の設問が見つかりません。")
elif not df_2026.empty:
    luxury_results = []
    details.markdown("**高級感の定義（DF列）**")
    for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
        values = pd.to_numeric(respondents[luxury_column], errors="coerce")
        valid_choices = values.isin(range(1, 7))
        invalid_choices = respondents[luxury_column].notna() & ~valid_choices
        if invalid_choices.any():
            st.warning(f"{group}のDF列に選択肢1〜6以外の回答が{int(invalid_choices.sum())}件あり、比較から除外します。")
        response_count = int(valid_choices.sum())
        details.caption(
            f"{group}：有効回答{response_count:,}人／対象{len(respondents):,}人"
            f"（未回答{int(respondents[luxury_column].isna().sum()):,}人）"
        )
        if response_count == 0:
            st.warning(f"{group}にDF列の有効回答がないため、この群の割合は表示できません。")
            continue
        counts = values.loc[valid_choices].value_counts().reindex(range(1, 7), fill_value=0)
        luxury_results.append(pd.DataFrame({
            "選択肢": [f"選択肢{number}" for number in counts.index],
            "比較群": group,
            "回答数": counts.to_numpy(),
            "有効回答数": response_count,
            "回答割合": counts.to_numpy() / response_count * 100,
        }))
    details.caption(
        "割合は各群のDF列の有効回答数を100％として計算しています。全体にはIoT支持者も含まれます。"
        "選択肢の内容はグラフ下の一覧に表示しています。選択肢6の内容は未確認です。"
    )
    if luxury_results:
        luxury_data = pd.concat(luxury_results, ignore_index=True)
        fig_luxury = px.bar(
            luxury_data,
            x="選択肢",
            y="回答割合",
            color="比較群",
            barmode="group",
            title="高級感の定義｜IoT支持者と全体の回答割合（2026年）",
            color_discrete_map={"全体": "#A6B3C2", "IoT支持者": "#007ACC"},
            custom_data=["回答数", "有効回答数"],
            labels={"回答割合": "回答割合（%）"},
        )
        fig_luxury.update_layout(
            yaxis=dict(ticksuffix="%", rangemode="tozero"),
            height=450,
        )
        fig_luxury.update_traces(
            hovertemplate=(
                "%{x}<br>回答割合：%{y:.1f}%<br>"
                "回答数：%{customdata[0]}人／有効回答：%{customdata[1]}人"
                "<extra>%{fullData.name}</extra>"
            ),
        )
        render_high_resolution_chart(fig_luxury, "luxury_definition_iot_highres")
        render_choice_list("DF列", [
            "誰もが知る一流ブランドや、職人のこだわりが詰まった「本物」を身につけているとき",
            "自分のスキルアップや、他では得られない刺激的な最新の「体験」にお金を使っているとき",
            "人混みを離れ、自然に囲まれた場所でスマホをオフにして「何もしない時間」を過ごしているとき",
            "信頼できる仲間や家族と、少し贅沢な空間でおいしい食事を囲み「特別な時間」を共有しているとき",
            "一生モノの家具、オーガニックな食材、万全の防災設備など、日々の「安心・安全・快適な空間」が整っているとき",
            "内容未確認（CSVには回答がありますが、ご提供の原文に記載がありません）",
        ])
        st.markdown("**グラフから見える傾向（高級感の定義）**")
        st.markdown(
            "**大切な人と過ごす「特別な時間」は、全体でもIoT支持者でも多く選ばれています。** "
            "IoT支持者では、全体よりもその割合が高くなっています。"
        )
        st.markdown(
            "**日々の「安心・安全・快適な空間」も、IoT支持者では全体より多く選ばれています。** "
            "一生モノの家具や食材、防災設備など、暮らしの環境が整っている状態を高級とする回答です。"
        )
        st.markdown(
            "**自然の中で過ごす「何もしない時間」は、IoT支持者では全体より少なくなっています。** "
            "スキルアップや最新の体験を選ぶ割合も、全体を下回っています。"
        )
        st.caption(
            "選択肢6もIoT支持者では最多の回答と並んでいますが、内容が未確認のため、"
            "上のコメントは内容を確認できる選択肢に限っています。"
        )

render_theme_separator()
st.subheader("プレミアム消費の目的（DG列）｜IoT支持者の特徴")
premium_column = (
    "2026年追加｜あなたが通常より「少し高価なもの（プレミアムな商品・サービス）」を購入・利用するとき、"
    "その主な目的や動機は何ですか？あてはまるものを最大3つまで選んでください。"
)
if premium_column not in df.columns:
    st.error("プレミアム消費の目的（DG列）の設問が見つかりません。")
elif not df_2026.empty:
    premium_results = []
    details.markdown("**プレミアム消費の目的（DG列）**")
    for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
        selections = respondents[premium_column].astype("string").str.split(r"[,|\n]", regex=True).explode().str.strip()
        selections = selections.loc[selections.notna() & selections.ne("")]
        valid_choices = selections.isin([str(number) for number in range(1, 10)])
        invalid_count = int((~valid_choices).sum())
        if invalid_count:
            st.warning(f"{group}のDG列に選択肢1〜9以外の回答が{invalid_count}件あり、比較から除外します。")
        valid_selections = selections.loc[valid_choices].reset_index()
        valid_selections.columns = ["回答者", "選択肢番号"]
        valid_selections = valid_selections.drop_duplicates(["回答者", "選択肢番号"])
        response_count = valid_selections["回答者"].nunique()
        details.caption(f"{group}：有効回答{response_count:,}人／対象{len(respondents):,}人")
        if response_count == 0:
            st.warning(f"{group}にDG列の有効回答がないため、この群の選択率は表示できません。")
            continue
        counts = valid_selections["選択肢番号"].value_counts().reindex(
            [str(number) for number in range(1, 10)], fill_value=0,
        )
        premium_results.append(pd.DataFrame({
            "目的": [f"選択肢{number}" for number in counts.index],
            "比較群": group,
            "選択者数": counts.to_numpy(),
            "有効回答者数": response_count,
            "選択率": counts.to_numpy() / response_count * 100,
        }))
    details.caption(
        "選択率＝その目的を選んだ人数 ÷ 各群のDG列の有効回答者数 × 100。"
        "複数回答のため合計は100％を超える場合があり、同じ人の同じ選択肢は1件として数えます。"
        "全体にはIoT支持者も含まれます。選択肢の内容はグラフ下の一覧に表示しています。"
        "選択肢8・9の内容は未確認です。"
    )
    if premium_results:
        premium_data = pd.concat(premium_results, ignore_index=True)
        fig_premium = px.bar(
            premium_data,
            x="目的",
            y="選択率",
            color="比較群",
            barmode="group",
            title="プレミアム消費の目的｜IoT支持者と全体の選択率（2026年）",
            color_discrete_map={"全体": "#A6B3C2", "IoT支持者": "#007ACC"},
            custom_data=["選択者数", "有効回答者数"],
            labels={"選択率": "選択率（%）"},
        )
        fig_premium.update_layout(
            yaxis=dict(ticksuffix="%", rangemode="tozero"),
            height=450,
        )
        fig_premium.update_traces(
            hovertemplate=(
                "%{x}<br>選択率：%{y:.1f}%<br>"
                "選択者：%{customdata[0]}人／有効回答者：%{customdata[1]}人"
                "<extra>%{fullData.name}</extra>"
            ),
        )
        render_high_resolution_chart(fig_premium, "premium_consumption_iot_highres")
        render_choice_list("DG列", [
            *DEFAULTS["プレミアム購入目的"],
            "内容未確認（ご提供の原文に記載がありません）",
            "内容未確認（ご提供の原文に記載がありません）",
        ])
        st.markdown("**グラフから見える傾向（プレミアム消費の目的）**")
        st.markdown(
            "**「心身をリフレッシュしたい」「気持ちを高め、自信を持ちたい」が、両群で多く選ばれています。** "
            "IoT支持者では、どちらも全体より高い割合となっています。"
        )
        st.markdown(
            "**「自分らしさやこだわりの表現」「ステータスや周囲からの評価」も、IoT支持者では全体より多く選ばれています。** "
            "ただし、IoT支持者の中で最多の目的ではありません。"
        )
        st.markdown(
            "**「長く使えること・環境への配慮・暮らしの無駄を省くこと」は、IoT支持者では全体より少なくなっています。** "
            "この設問では、プレミアム消費の目的によって全体との違いが見られます。"
        )
        st.caption(
            "選択肢8・9は内容未確認のため、意味の読み取りには含めていません。"
            "上のコメントは内容を確認できる選択肢に限っています。"
        )

render_theme_separator()
st.subheader("Up-Grade（奮発したジャンル）｜IoT支持者の傾向")
upgrade_columns = [
    column for column in df.columns
    if column.startswith("奮発して良かったジャンル｜")
]
if not upgrade_columns:
    st.error("Up-Grade（奮発したジャンル）の設問が見つかりません。")
elif not df_2026.empty:
    upgrade_results = []
    details.markdown("**Up-Grade（DH〜DQ列）**")
    for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
        for column in upgrade_columns:
            values = pd.to_numeric(respondents[column], errors="coerce")
            valid_choices = values.isin([0, 1])
            invalid_count = int((respondents[column].notna() & ~valid_choices).sum())
            genre = column.split("｜", 1)[1].split("（", 1)[0].strip()
            if invalid_count:
                st.warning(f"{group}の「{genre}」に0・1以外の回答が{invalid_count}件あり、比較から除外します。")
            response_count = int(valid_choices.sum())
            if response_count == 0:
                st.warning(f"{group}の「{genre}」に有効回答がないため、この選択率は表示できません。")
                continue
            selected_count = int(values.loc[valid_choices].eq(1).sum())
            upgrade_results.append({
                "ジャンル": genre,
                "比較群": group,
                "選択者数": selected_count,
                "有効回答者数": response_count,
                "選択率": selected_count / response_count * 100,
            })
    details.caption(
        "各ジャンルの1を選択、0を未選択として集計。選択率は各群・各ジャンルの有効回答者数を分母にしています。"
        "複数回答のため合計は100％になりません。全体にはIoT支持者も含まれます。"
    )
    if upgrade_results:
        upgrade_data = pd.DataFrame(upgrade_results)
        fig_upgrade = px.bar(
            upgrade_data,
            x="ジャンル",
            y="選択率",
            color="比較群",
            barmode="group",
            title="Up-Grade（奮発したジャンル）｜IoT支持者と全体の選択率（2026年）",
            color_discrete_map={"全体": "#A6B3C2", "IoT支持者": "#007ACC"},
            custom_data=["選択者数", "有効回答者数"],
            labels={"選択率": "選択率（%）"},
        )
        fig_upgrade.update_layout(
            xaxis=dict(tickangle=-30),
            yaxis=dict(ticksuffix="%", rangemode="tozero"),
            height=550,
        )
        fig_upgrade.update_traces(
            hovertemplate=(
                "%{x}<br>選択率：%{y:.1f}%<br>"
                "選択者：%{customdata[0]}人／有効回答者：%{customdata[1]}人"
                "<extra>%{fullData.name}</extra>"
            ),
        )
        render_high_resolution_chart(fig_upgrade, "upgrade_iot_highres")
        render_choice_list("DH〜DQ列", [
            column.split("｜", 1)[1] for column in upgrade_columns
        ])
        st.caption(
            "DH〜DQはCSVの列順で番号を付けています。"
            "ご提供の原文と番号が異なり、CSVでは選択肢9が「その他」、選択肢10が「特にない」です。"
        )
        st.markdown("**グラフから見える傾向（奮発したジャンル）**")
        st.markdown(
            "**具体的なジャンルでは、「旅・宿泊」が両群で最も多く選ばれています。** "
            "IoT支持者では「自宅のインテリア・家電」が続き、全体との差も最も大きくなっています。"
        )
        st.markdown(
            "**IoT支持者の奮発した買い物は、住まいの機器だけに限りません。** "
            "ファッションや学び・エンタメ、ガジェット・デジタルも、全体より多く選ばれています。"
        )
        st.markdown(
            "**一方、「奮発した買い物はしていない」も、両群で多く選ばれています。** "
            "その割合はほぼ同じで、IoT支持者全体が奮発した買い物をしているわけではありません。"
        )

render_theme_separator()
st.subheader("高級感のあるインテリア（DR列）｜IoT支持者の志向")
interior_column = (
    "あなたがイメージする「高級感のあるインテリア」は次のうちどれですか。"
    "最もあてはまるものをお答えください。"
)
if interior_column not in df.columns:
    st.error("高級感のあるインテリア（DR列）の設問が見つかりません。")
elif not df_2026.empty:
    interior_results = []
    details.markdown("**高級感のあるインテリア（DR列）**")
    interior_labels = ["先進的な", "上品な", "風格のある", "豪華な", "シンプルな", "温もりのある"]
    for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
        values = pd.to_numeric(respondents[interior_column], errors="coerce")
        valid_choices = values.isin(range(1, 9))
        invalid_count = int((respondents[interior_column].notna() & ~valid_choices).sum())
        if invalid_count:
            st.warning(f"{group}のDR列に選択肢1〜8以外の回答が{invalid_count}件あり、比較から除外します。")
        response_count = int(valid_choices.sum())
        details.caption(
            f"{group}：有効回答{response_count:,}人／対象{len(respondents):,}人"
            f"（未回答{int(respondents[interior_column].isna().sum()):,}人）"
        )
        if response_count == 0:
            st.warning(f"{group}にDR列の有効回答がないため、この群の割合は表示できません。")
            continue
        counts = values.loc[valid_choices].value_counts().reindex(range(1, 7), fill_value=0)
        interior_results.append(pd.DataFrame({
            "インテリア": interior_labels,
            "比較群": group,
            "回答数": counts.to_numpy(),
            "有効回答数": response_count,
            "回答割合": counts.to_numpy() / response_count * 100,
        }))
    details.caption(
        "割合は各群のDR列の有効回答数を100％として計算しています。全体にはIoT支持者も含まれます。"
        "選択肢7・8はグラフに表示しませんが、割合の分母には含めています。"
        "選択肢の内容はグラフ下の一覧に表示しています。"
    )
    if interior_results:
        interior_data = pd.concat(interior_results, ignore_index=True)
        fig_interior = px.bar(
            interior_data,
            x="インテリア",
            y="回答割合",
            color="比較群",
            barmode="group",
            category_orders={"インテリア": interior_labels},
            title="高級感のあるインテリア｜IoT支持者と全体の回答割合（2026年）",
            color_discrete_map={"全体": "#A6B3C2", "IoT支持者": "#007ACC"},
            custom_data=["回答数", "有効回答数"],
            labels={"回答割合": "回答割合（%）"},
        )
        fig_interior.update_layout(
            yaxis=dict(ticksuffix="%", rangemode="tozero"),
            height=450,
        )
        fig_interior.update_traces(
            hovertemplate=(
                "%{x}<br>回答割合：%{y:.1f}%<br>"
                "回答数：%{customdata[0]}人／有効回答：%{customdata[1]}人"
                "<extra>%{fullData.name}</extra>"
            ),
        )
        render_high_resolution_chart(fig_interior, "interior_iot_highres")
        render_choice_list("DR列", [
            "先進的な高級感（インテリジェンス、都会的、クール、現代的、理知的）",
            "上品な高級感（気品がある、洗練された、エレガント、優美）",
            "風格のある高級感（伝統的、格調がある、渋みがある、円熟）",
            "豪華な高級感（ゴージャス、装飾的、華麗、凝った、華やか）",
            "シンプルな高級感（無駄がない、ミニマル、端正、静謐、機能的）",
            "温もりのある高級感（自然な、心地よい、調和的、素材感のある、オーガニック）",
        ])
        st.markdown("**グラフから見える傾向（高級感のあるインテリア）**")
        st.markdown(
            "**IoT支持者では、「シンプルな高級感」が最も多く選ばれています。** "
            "無駄のない、端正で機能的なイメージが上位にあり、「先進的」「上品」が同じ割合で続きます。"
        )
        st.markdown(
            "**全体との違いが最も大きいのは、「先進的な高級感」です。** "
            "都会的・クール・現代的なイメージを選ぶ割合は、IoT支持者では全体のおよそ2倍となっています。"
        )
        st.markdown(
            "**「風格のある」「温もりのある」高級感は、IoT支持者では全体より少なくなっています。** "
            "一方、「豪華な」は全体を上回っており、好みがシンプルな方向だけに揃っているわけではありません。"
        )

render_theme_separator()
st.subheader("年収（DS列）｜IoT支持者の所得分布")
income_column = "あなたの年収を教えてください"
if income_column not in df.columns:
    st.error("年収（DS列）の設問が見つかりません。")
elif not df_2026.empty:
    details.markdown("**年収（DS列）**")
    income_categories = (
        df_2026[income_column].dropna().astype("string").str.strip()
    )
    income_categories = income_categories.loc[income_categories.ne("")].unique().tolist()
    income_categories = sorted(
        income_categories,
        key=lambda value: (
            int(value.split("-", 1)[0]) if value.split("-", 1)[0].isdigit() else float("inf"),
            value,
        ),
    )
    income_results = []
    for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
        values = respondents[income_column].dropna().astype("string").str.strip()
        values = values.loc[values.ne("")]
        response_count = len(values)
        details.caption(
            f"{group}：回答{response_count:,}人／対象{len(respondents):,}人"
            f"（未回答{len(respondents) - response_count:,}人）"
        )
        if response_count == 0:
            st.warning(f"{group}にDS列の回答がないため、この群の割合は表示できません。")
            continue
        counts = values.value_counts().reindex(income_categories, fill_value=0)
        income_results.append(pd.DataFrame({
            "年収": counts.index,
            "比較群": group,
            "回答数": counts.to_numpy(),
            "回答者数": response_count,
            "回答割合": counts.to_numpy() / response_count * 100,
        }))
    details.caption(
        "設問は「あなたの年収を教えてください」です。世帯年収とは明記されていません。"
        "割合は各群のDS列の回答者数を分母とし、「答えたくない／わからない」も回答区分として含めています。"
        "全体にはIoT支持者も含まれます。"
    )
    if income_results:
        income_data = pd.concat(income_results, ignore_index=True)
        fig_income = px.bar(
            income_data,
            x="年収",
            y="回答割合",
            color="比較群",
            barmode="group",
            category_orders={"年収": income_categories},
            title="年収｜IoT支持者と全体の所得分布（2026年）",
            color_discrete_map={"全体": "#A6B3C2", "IoT支持者": "#007ACC"},
            custom_data=["回答数", "回答者数"],
            labels={"回答割合": "回答割合（%）"},
        )
        fig_income.update_layout(
            xaxis=dict(type="category", tickangle=-30),
            yaxis=dict(ticksuffix="%", rangemode="tozero"),
            height=550,
        )
        fig_income.update_traces(
            hovertemplate=(
                "%{x}<br>回答割合：%{y:.1f}%<br>"
                "回答数：%{customdata[0]}人／回答者：%{customdata[1]}人"
                "<extra>%{fullData.name}</extra>"
            ),
        )
        render_high_resolution_chart(fig_income, "income_iot_highres")
        render_choice_list("DS列", [
            "～300万円未満",
            "300万円～600万円未満",
            "600万円～800万円未満",
            "800万円～1000万円未満",
            "1000万円～1500万円未満",
            "1500万円～3000万円未満",
            "3000万円以上",
            "「答えたくない」または「わからない」",
        ])
        st.markdown("**グラフから見える傾向（年収）**")
        st.markdown(
            "**IoT支持者の中心は、年収600万円未満の層です。** "
            "1000万円〜1500万円未満の層も全体よりやや多いものの、高年収層に集中しているわけではありません。"
        )
        st.markdown(
            "**「答えたくない／わからない」も、両群に一定数あります。** "
            "この設問は世帯年収とは明記されていないため、家計全体の余裕や購買力まで読み取ることはできません。"
        )

render_theme_separator()
st.subheader("IoT支持者 × 現在のペンタゴンタイプ（2024〜2026年）")
pentagon_scores = current_pentagon_scores(df)
if len(pentagon_scores.columns) != len(PENTAGON_ORDER):
    st.error("現在のペンタゴンタイプを分類するための5分野の設問が揃っていません。")
else:
    pentagon_years = list(range(2022, 2027))
    pentagon_source = df.loc[df["年度"].isin(pentagon_years), ["年度"]].copy()
    pentagon_source["タイプ"] = current_pentagon_types(pentagon_scores).loc[pentagon_source.index]
    pentagon_source["比較群"] = iot_mask.loc[pentagon_source.index].map(
        {True: "IoT支持者", False: "IoT非支持者"},
    )
    details.markdown("**現在のペンタゴンタイプ（2022〜2026年）**")
    details.caption(
        "各分野の回答平均を既存ダッシュボードと同じ0〜6点に換算し、"
        "最高得点が1分野だけの回答者を分類します。同点・全分野未回答は分類できないため除外します。"
        "構成比は各年・各群の分類できた回答者数を分母とします。"
        "非支持者は理想の暮らしの回答にIoTの選択が確認できない回答者で、未回答者も含みます。"
        "他の比較グラフの「全体」と異なり、この2群は重複しません。"
        "2022・2023年のIoT支持者は分類可能な回答が少なく、少数の回答で構成比が大きく変わる点に注意が必要です。"
    )
    pentagon_results = []
    for year in pentagon_years:
        for group in ["IoT非支持者", "IoT支持者"]:
            respondents = pentagon_source.loc[
                pentagon_source["年度"].eq(year) & pentagon_source["比較群"].eq(group)
            ]
            types = respondents["タイプ"].dropna()
            details.caption(
                f"{year}年・{group}：分類可能{len(types):,}人／対象{len(respondents):,}人"
                f"（分類不能{len(respondents) - len(types):,}人）"
            )
            if types.empty:
                st.warning(f"{year}年の{group}に分類可能な回答がないため、この群の構成比は表示できません。")
                continue
            counts = types.value_counts().reindex(PENTAGON_ORDER, fill_value=0)
            pentagon_results.append(pd.DataFrame({
                "年度": str(year),
                "タイプ": counts.index,
                "比較群": group,
                "回答数": counts.to_numpy(),
                "分類可能数": len(types),
                "構成比": counts.to_numpy() / len(types) * 100,
            }))
    if pentagon_results:
        pentagon_data = pd.concat(pentagon_results, ignore_index=True)
        for display_years in [[2024, 2025, 2026], [2022, 2023]]:
            chart_data = pentagon_data.loc[pentagon_data["年度"].isin([str(year) for year in display_years])]
            if chart_data.empty:
                continue
            chart_container = (
                st.container() if display_years[0] == 2024
                else st.expander("参考：2022・2023年のペンタゴンタイプ", expanded=False)
            )
            with chart_container:
                fig_pentagon = px.bar(
                    chart_data,
                    x="タイプ",
                    y="構成比",
                    color="比較群",
                    facet_col="年度",
                    facet_col_wrap=2,
                    barmode="group",
                    category_orders={
                        "年度": [str(year) for year in display_years],
                        "タイプ": PENTAGON_ORDER,
                        "比較群": ["IoT非支持者", "IoT支持者"],
                    },
                    color_discrete_map={"IoT非支持者": "#A6B3C2", "IoT支持者": "#007ACC"},
                    custom_data=["回答数", "分類可能数"],
                    labels={"構成比": "構成比（%）", "タイプ": "現在のペンタゴンタイプ"},
                    title=(
                        "IoT支持者・非支持者の現在のペンタゴンタイプ構成比"
                        f"（{display_years[0]}〜{display_years[-1]}年）"
                    ),
                )
                fig_pentagon.update_layout(
                    height=800 if display_years[0] == 2024 else 450, legend_title_text="比較群",
                )
                fig_pentagon.update_xaxes(tickangle=-25, showticklabels=True)
                fig_pentagon.update_yaxes(ticksuffix="%", rangemode="tozero")
                fig_pentagon.update_traces(
                    hovertemplate=(
                        "%{x}<br>構成比：%{y:.1f}%<br>"
                        "回答数：%{customdata[0]}人／分類可能：%{customdata[1]}人"
                        "<extra>%{fullData.name}</extra>"
                    ),
                )
                render_high_resolution_chart(
                    fig_pentagon,
                    f"iot_pentagon_{display_years[0]}_{display_years[-1]}_highres",
                )
                if display_years[0] == 2022:
                    st.caption("この2年間はIoT支持者の分類可能な回答が少ないため、参考として掲載しています。")
        st.markdown("**2024〜2026年を中心にした読み取りと動機の仮説**")
        st.markdown(
            "**直近3年間では、IoT支持者の「生活充実派」が非支持者を上回っています。** "
            "ここから、「日々の安心と快適さを整えたい」という動機が考えられます。"
            "見守りや防災、室内環境の調整など、暮らしを支える機能が響く可能性があります。"
        )
        st.markdown(
            "**「自然体派」もIoT支持者に多く見られますが、この3年間は非支持者のほうが高い割合です。** "
            "IoT支持者特有の特徴とは言えませんが、「自分の時間を邪魔せず、手間を減らしたい」"
            "という動機は検討できそうです。"
        )
        st.markdown(
            "**デザインの仮説は、「自分の時間を邪魔しないこと」と「安心・快適さを支えること」の両立です。** "
            "未来感を見せるだけでなく、暮らしに自然になじみ、必要なときには迷わず使える設計が考えられます。"
        )
        st.caption(
            "これらは現在の幸福状態のタイプ構成から考えた仮説であり、IoTの購入・支持理由を直接確認した結果ではありません。"
            "自然体派は非支持者でも多く、IoT支持者だけの特徴とは限りません。"
            "また、生活充実派の分類には「デジタル化を取り入れ暮らしている」という設問が含まれるため、"
            "IoTとの関連には分類項目自体の影響も考えられます。"
        )

details.markdown("**30代の子どもの有無とIoT志向率（G列）**")
family_column = "◆同居家族"
if family_column not in df.columns:
    st.error("子どもの有無を確認するための同居家族（G列）の設問が見つかりません。")
else:
    family_answers = df[family_column].astype("string")
    child_status = pd.Series(pd.NA, index=df.index, dtype="string")
    child_status.loc[family_answers.str.contains("子供有り", regex=False, na=False)] = "子供有り"
    child_status.loc[family_answers.str.contains("子供無し", regex=False, na=False)] = "子供無し"
    family_data = df.loc[df["年度"].isin([2024, 2025, 2026]) & df["年代"].eq("30代"), ["年度"]].copy()
    family_data["子どもの有無"] = child_status.loc[family_data.index]
    family_data["IoT志向"] = iot_mask.loc[family_data.index]
    family_rates = (
        family_data.dropna(subset=["子どもの有無"])
        .groupby(["年度", "子どもの有無"])["IoT志向"]
        .agg(回答者数="size", IoT志向者数="sum")
        .reset_index()
    )
    family_rates["IoT志向率（%）"] = (
        family_rates["IoT志向者数"].div(family_rates["回答者数"]).mul(100).round(1)
    )
    details.caption(
        "G列の「子供有り」「子供無し」と明記された回答だけを分類し、婚姻状況は合算しています。"
        "「家族」「夫婦のみ」「単身」や未回答から子どもの有無は推定しません。"
        "割合は各年・30代・各区分の回答者数を分母とします。"
        "子どもの年齢や子育ての状況、生活の忙しさは、この列だけでは確認できません。"
    )
    details.dataframe(family_rates, width="stretch", hide_index=True)
    for year in [2024, 2025, 2026]:
        rows = family_data.loc[family_data["年度"].eq(year)]
        details.caption(
            f"{year}年・30代：子どもの有無を確認できない回答"
            f"{int(rows['子どもの有無'].isna().sum()):,}人／対象{len(rows):,}人"
        )

details.markdown("**女性の職業とIoT志向率（H列）**")
occupation_column = "◆職業"
if occupation_column not in df.columns:
    st.error("女性の就業状況を確認するための職業（H列）の設問が見つかりません。")
else:
    occupation_answers = df[occupation_column].astype("string").str.strip()
    employed_choices = [
        "会社員・公務員", "会社員(事務系)", "会社員(技術系)", "会社員(その他)",
        "公務員", "経営者・役員", "自営業・フリーランス", "自営業", "自由業",
        "パート・アルバイト", "派遣・契約社員",
    ]
    employment_status = pd.Series("学生・その他・未回答", index=df.index, dtype="string")
    employment_status.loc[occupation_answers.isin(employed_choices)] = "有職者"
    employment_status.loc[
        occupation_answers.isin(["専業主婦/専業主夫", "専業主婦(主夫)"])
    ] = "専業主婦"
    employment_data = df.loc[
        df["年度"].isin([2024, 2025, 2026]) & df["性別"].eq("女性"), ["年度"],
    ].copy()
    employment_data["職業区分"] = employment_status.loc[employment_data.index]
    employment_data["IoT志向"] = iot_mask.loc[employment_data.index]
    employment_rates = (
        employment_data.groupby(["年度", "職業区分"])["IoT志向"]
        .agg(回答者数="size", IoT志向者数="sum")
        .reset_index()
    )
    employment_rates["IoT志向率（%）"] = (
        employment_rates["IoT志向者数"].div(employment_rates["回答者数"]).mul(100).round(1)
    )
    employment_rates["女性回答者内の構成比（%）"] = (
        employment_rates["回答者数"]
        .div(employment_rates.groupby("年度")["回答者数"].transform("sum")).mul(100).round(1)
    )
    employment_rates["女性IoT支持者内の構成比（%）"] = (
        employment_rates["IoT志向者数"]
        .div(employment_rates.groupby("年度")["IoT志向者数"].transform("sum")).mul(100).round(1)
    )
    details.caption(
        "会社員・公務員・経営者・自営業・自由業・パート等を有職者として合算し、専業主婦と比較しています。"
        "学生・その他・未回答は就業状況を決められないため別区分で表示します。"
        "IoT志向率の分母は各年・女性・各職業区分の回答者数です。"
        "構成比は女性回答者全体、または女性IoT支持者全体に占める各区分の割合で、IoT志向率とは異なります。"
        "職業だけでは家事の負担、勤務時間、時短の希望、購入理由は確認できません。"
    )
    details.dataframe(employment_rates, width="stretch", hide_index=True)

render_theme_separator()
st.subheader("IoT選択者の好きな色")
st.markdown("### IoT選択者の好きな色 上位5色")

if iot_colors.empty:
    st.info("IoT選択者の好きな色に有効回答がないため、グラフを表示できません。")
else:
    color_hex_map = {color["name"]: color["hex"] for color in COLOR_SWATCHES}
    top_colors = (
        iot_colors.sort_values(ascending=False, kind="stable")
        .head(5)
        .rename_axis("色")
        .reset_index(name="人数")
    )
    total_color_selections = int(iot_colors.sum())
    top_colors["構成比"] = top_colors["人数"].div(total_color_selections).mul(100)
    top_colors["順位"] = range(1, len(top_colors) + 1)
    top_colors["表示"] = top_colors["人数"].map(lambda value: f"{value:,}人")
    chart_order = top_colors["色"].tolist()[::-1]
    chart_colors = {
        color: color_hex_map.get(color, "#4B9CD3")
        for color in top_colors["色"]
    }
    figure = px.bar(
        top_colors,
        x="人数",
        y="色",
        color="色",
        text="表示",
        orientation="h",
        category_orders={"色": chart_order},
        color_discrete_map=chart_colors,
        custom_data=["順位", "構成比"],
        labels={"人数": "選択数", "色": ""},
    )
    figure.update_layout(
        showlegend=False,
        height=390,
        margin=dict(l=20, r=30, t=25, b=40),
        xaxis=dict(rangemode="tozero", title="選択数"),
        yaxis=dict(title="", categoryorder="array", categoryarray=chart_order),
    )
    figure.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate=(
            "順位：%{customdata[0]}位<br>"
            "色：%{y}<br>"
            "選択数：%{x}人<br>"
            "IoT選択者内の構成比：%{customdata[1]:.1f}%"
            "<extra></extra>"
        ),
    )
    render_high_resolution_chart(figure, "iot_top5_favorite_colors_highres")
    st.caption(
        "IoT選択者が選んだ好きな色を選択数の多い順に表示しています。"
        "複数回答のため、人数ではなく色の選択数を集計しています。"
    )
    st.dataframe(
        top_colors[["順位", "色", "人数", "構成比"]].rename(
            columns={"人数": "選択数", "構成比": "IoT選択者内の構成比（%）"}
        ).assign(**{"IoT選択者内の構成比（%）": lambda data: data["IoT選択者内の構成比（%）"].round(1)}),
        width="stretch",
        hide_index=True,
    )
    overall_colors = count_colors(df)
    overall_color_total = int(overall_colors.sum())
    top_color_name = str(top_colors.iloc[0]["色"])
    top_color_share = float(top_colors.iloc[0]["構成比"])
    overall_color_share = (
        float(overall_colors.get(top_color_name, 0)) / overall_color_total * 100
        if overall_color_total
        else 0
    )
    color_order = top_colors["色"].tolist()
    survey_color_map = {color["name"]: color["hex"] for color in COLOR_SWATCHES}
    comparison_figure = go.Figure()
    comparison_figure.add_trace(
        go.Bar(
            name="全体",
            x=color_order,
            y=[
                float(overall_colors.get(color, 0)) / overall_color_total * 100
                for color in color_order
            ],
            marker_color="#A6B3C2",
            offsetgroup="overall",
            hovertemplate="色：%{x}<br>構成比：%{y:.1f}%<extra>全体</extra>",
        )
    )
    comparison_figure.add_trace(
        go.Bar(
            name="IoT支持者",
            x=color_order,
            y=top_colors["構成比"],
            marker_color=[
                survey_color_map.get(color, "#4B9CD3")
                for color in color_order
            ],
            offsetgroup="iot",
            hovertemplate="色：%{x}<br>構成比：%{y:.1f}%<extra>IoT支持者</extra>",
        )
    )
    comparison_figure.update_layout(
        title="好きな色 上位5色｜IoT支持者と全体の構成比比較",
        height=390,
        margin=dict(l=70, r=30, t=55, b=75),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(color="#5B6B84", size=12),
        xaxis=dict(
            type="category",
            showline=False,
            zeroline=False,
            gridcolor="#DDE6EF",
            title="好きな色",
            tickangle=-25,
        ),
        yaxis=dict(
            title="構成比（%）",
            ticksuffix="%",
            rangemode="tozero",
            gridcolor="#DDE6EF",
        ),
        barmode="group",
        bargap=0.25,
        bargroupgap=0.08,
        legend=dict(title="比較群", orientation="v", y=1.12, x=1.02),
    )
    render_high_resolution_chart(comparison_figure, "iot_top5_colors_comparison_highres")
    st.markdown("**グラフから見える傾向（好きな色）**")
    st.markdown(
        f"**{top_color_name}**を中心に、IoT支持者の色の好みが見えてきます。"
    )
    st.markdown(
        f"{top_color_name}は全体にも見られる色ですが、IoT支持者では"
        f"{'より強く' if top_color_share >= overall_color_share else 'やや控えめに'}"
        "選ばれています。"
    )
    st.markdown(
        "青は全体にも見られるベーシックな色ですが、IoT支持者では全体の約1.4倍の強さで選ばれています。"
        "冷静さや信頼感に加え、先進性や知性を感じさせる青が、IoT支持者の価値観と強く結び付いているようです。"
    )

render_theme_separator()
st.subheader("IoT選択者の「しあわせ」を感じるピンク")
st.markdown("### 「しあわせ」を感じるピンク")
st.caption("これらのピンクの中に「しあわせ」を感じるとしたら、あなたの気持ちに近い色はどれですか？")

pink_column = df.columns[107] if len(df.columns) > 107 else None
pink_choices = [
    "明るい黄みのピンク", "明るい紫みのピンク", "明るいピンク",
    "強い黄みのピンク", "強い紫みのピンク", "強いピンク",
    "やわらかいピンク", "濃い紫みのピンク", "濃いピンク",
    "うすい黄みのピンク", "うすい紫みのピンク", "くすんだピンク",
    "鮮やかな黄みのピンク", "鮮やかな紫みのピンク", "鮮やかなピンク",
    "この中にはない",
]
if pink_column is None or pink_column not in df_iot.columns:
    st.warning("「しあわせ」を感じるピンクの回答列が見つからないため、グラフを表示できません。")
else:
    pink_values = df_iot[pink_column].dropna().astype("string").str.strip()

    def normalize_pink(value: object) -> str | None:
        text = str(value).strip()
        match = re.match(r"^(\d+)[.．]?\s*", text)
        if match:
            choice_number = int(match.group(1))
            if 1 <= choice_number <= len(pink_choices):
                return pink_choices[choice_number - 1]
        return text if text in pink_choices else None

    pink_counts = (
        pink_values.map(normalize_pink)
        .dropna()
        .value_counts()
        .reindex(pink_choices, fill_value=0)
        .rename_axis("色")
        .reset_index(name="選択数")
    )
    pink_counts = pink_counts.loc[pink_counts["選択数"].gt(0)].sort_values(
        "選択数", ascending=False, kind="stable"
    )

    if pink_counts.empty:
        st.info("IoT支持者のピンク回答に有効回答がないため、グラフを表示できません。")
    else:
        total_pink_answers = int(pink_counts["選択数"].sum())
        pink_counts["構成比"] = pink_counts["選択数"].div(total_pink_answers).mul(100)
        pink_counts["順位"] = range(1, len(pink_counts) + 1)
        pink_bar_colors = [
            "#F7D2E1", "#F8D1D7", "#F18BB0", "#F5B4A9",
            "#F4BBAA", "#F17D93", "#F3A29A", "#D86A9A",
            "#E767E7", "#F18177", "#EFA8C4", "#BBA3A4",
            "#FF7358", "#F061E5", "#EF5086", "#BFC5CA",
        ]
        pink_counts["棒色"] = [
            pink_bar_colors[min(rank - 1, len(pink_bar_colors) - 1)]
            for rank in pink_counts["順位"]
        ]
        overall_pink_counts = (
            df[pink_column]
            .dropna()
            .astype("string")
            .str.strip()
            .map(normalize_pink)
            .dropna()
            .value_counts()
            .reindex(pink_choices, fill_value=0)
        )
        overall_pink_total = int(overall_pink_counts.sum())
        pink_top5 = pink_counts.head(5).copy()
        pink_order = pink_top5["色"].tolist()
        pink_survey_colors = dict(zip(pink_top5["色"], pink_top5["棒色"]))
        comparison_figure = go.Figure()
        comparison_figure.add_trace(
            go.Bar(
                name="全体",
                x=pink_order,
                y=[
                    float(overall_pink_counts.get(color, 0))
                    / overall_pink_total
                    * 100
                    for color in pink_order
                ],
                marker_color="#A6B3C2",
                offsetgroup="overall",
                hovertemplate="色：%{x}<br>回答者比率：%{y:.1f}%<extra>全体</extra>",
            )
        )
        comparison_figure.add_trace(
            go.Bar(
                name="IoT支持者",
                x=pink_order,
                y=pink_top5["構成比"],
                marker_color=[pink_survey_colors[color] for color in pink_order],
                offsetgroup="iot",
                hovertemplate="色：%{x}<br>回答者比率：%{y:.1f}%<extra>IoT支持者</extra>",
            ),
        )
        comparison_figure.update_layout(
            title="「しあわせ」を感じるピンク 上位5色｜IoT支持者と全体の構成比比較",
            height=390,
            margin=dict(l=70, r=30, t=55, b=75),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(color="#5B6B84", size=12),
            xaxis=dict(
                type="category",
                showline=False,
                zeroline=False,
                gridcolor="#DDE6EF",
                title="色",
                tickangle=-25,
            ),
            yaxis=dict(
                title="回答者比率（%）",
                ticksuffix="%",
                rangemode="tozero",
                gridcolor="#DDE6EF",
            ),
            barmode="group",
            bargap=0.25,
            bargroupgap=0.08,
            legend=dict(title="比較群", orientation="v", y=1.12, x=1.02),
        )
        render_high_resolution_chart(comparison_figure, "iot_happy_pink_highres")
        st.caption("IoT支持者が「しあわせ」を感じるピンクの上位5色を、全体と構成比で比較しています。")
        st.dataframe(
            pink_top5[["順位", "色", "選択数", "構成比"]].rename(
                columns={"構成比": "IoT支持者内の回答者比率（%）"}
            ).assign(
                **{
                    "IoT支持者内の回答者比率（%）": lambda data: data[
                        "IoT支持者内の回答者比率（%）"
                    ].round(1)
                }
            ),
            width="stretch",
            hide_index=True,
        )
        pink_top = str(pink_top5.iloc[0]["色"])
        pink_top_share = float(pink_top5.iloc[0]["構成比"])
        overall_pink_share = (
            float(overall_pink_counts.get(pink_top, 0)) / overall_pink_total * 100
            if overall_pink_total
            else 0
        )
        st.markdown("**グラフから見える傾向（しあわせを感じるピンク）**")
        st.markdown(
            f"IoT支持者が「しあわせ」を感じる色として、**{pink_top}**が印象的に表れています。"
        )
        st.markdown(
            f"{pink_top}は全体にも共通する感覚ですが、IoT支持者では"
            f"{'より強く' if pink_top_share >= overall_pink_share else 'やや控えめに'}"
            "選ばれています。"
        )
        bright_purple_pink = "明るい紫みのピンク"
        bright_purple_iot_share = (
            float(pink_counts.loc[pink_counts["色"].eq(bright_purple_pink), "構成比"].iloc[0])
            if pink_counts["色"].eq(bright_purple_pink).any()
            else 0
        )
        bright_purple_overall_share = (
            float(overall_pink_counts.get(bright_purple_pink, 0))
            / overall_pink_total
            * 100
            if overall_pink_total
            else 0
        )
        if bright_purple_iot_share and bright_purple_overall_share:
            st.markdown(
                "**明るい紫みのピンク**は全体にも共通する感覚ですが、"
                "IoT支持者では全体の約1.1倍の強さで選ばれています。"
                "明るく華やかな印象の中に、知性や先進性を感じさせる色として"
                "受け止められているようです。"
            )
        st.markdown(
            "明るさや鮮やかさを持つピンクが中心にあり、"
            "「しあわせ」を前向きなエネルギーや、気持ちを軽やかにする彩りとして"
            "捉えていることがうかがえます。"
        )

render_theme_separator()
st.subheader("IoT選択者の好きなインテリアスタイル")
st.markdown("### IoT選択者の好きなインテリアスタイル")

# CV列（0始まりでは99番目）を好きなインテリアスタイルの回答元として使う。
interior_column = df.columns[99] if len(df.columns) > 99 else None
interior_choices = DEFAULTS["好きなインテリアスタイル"]
if interior_column is None or interior_column not in df_iot.columns:
    st.warning("好きなインテリアスタイルの回答列が見つからないため、グラフを表示できません。")
else:
    interior_values = (
        df_iot[interior_column]
        .dropna()
        .astype("string")
        .str.split(r"[,|\n]", regex=True)
        .explode()
        .str.strip()
    )
    interior_values = interior_values[interior_values.ne("")]

    def normalize_interior(value: object) -> str | None:
        text = str(value).strip()
        match = re.match(r"^(\d+)[.．]?\s*", text)
        if match:
            choice_number = int(match.group(1))
            if 1 <= choice_number <= len(interior_choices):
                return interior_choices[choice_number - 1]
        return text if text in interior_choices else None

    interior_values = interior_values.map(normalize_interior).dropna()
    interior_counts = (
        interior_values.value_counts()
        .reindex(interior_choices, fill_value=0)
        .rename_axis("スタイル")
        .reset_index(name="選択数")
    )
    interior_counts = interior_counts.loc[interior_counts["選択数"].gt(0)].sort_values(
        "選択数", ascending=False, kind="stable"
    )

    if interior_counts.empty:
        st.info("IoT選択者のインテリアスタイルに有効回答がないため、グラフを表示できません。")
    else:
        asset_dir = Path(__file__).resolve().parent / "assets"
        gallery_columns = st.columns(3)
        for index, style in enumerate(interior_choices, start=1):
            if style not in set(interior_counts["スタイル"]):
                continue
            image_path = asset_dir / f"interior_{index}.png"
            with gallery_columns[(index - 1) % len(gallery_columns)]:
                if image_path.exists():
                    st.image(image_path, width="stretch")
                st.caption(f"{index}. {style}")

        total_interior_selections = int(interior_counts["選択数"].sum())
        interior_counts["構成比"] = (
            interior_counts["選択数"].div(total_interior_selections).mul(100)
        )
        interior_counts["順位"] = range(1, len(interior_counts) + 1)
        interior_bar_colors = ["#4FA64F", "#4F7FB3", "#F28C1B", "#E85B5B", "#6DB6B0"]
        interior_counts["棒色"] = [
            interior_bar_colors[min(rank - 1, len(interior_bar_colors) - 1)]
            for rank in interior_counts["順位"]
        ]
        overall_interior_counts = (
            df[interior_column]
            .dropna()
            .astype("string")
            .str.split(r"[,|\n]", regex=True)
            .explode()
            .str.strip()
            .map(normalize_interior)
            .dropna()
            .value_counts()
            .reindex(interior_choices, fill_value=0)
        )
        overall_interior_total = int(overall_interior_counts.sum())
        chart_order = interior_counts["スタイル"].tolist()
        comparison_figure = go.Figure()
        comparison_figure.add_trace(
            go.Bar(
                name="全体",
                x=chart_order,
                y=[
                    float(overall_interior_counts.get(style, 0))
                    / overall_interior_total
                    * 100
                    for style in chart_order
                ],
                marker_color="#A6B3C2",
                offsetgroup="overall",
                hovertemplate="スタイル：%{x}<br>構成比：%{y:.1f}%<extra>全体</extra>",
            )
        )
        comparison_figure.add_trace(
            go.Bar(
                name="IoT支持者",
                x=chart_order,
                y=interior_counts["構成比"],
                marker_color="#007ACC",
                offsetgroup="iot",
                hovertemplate="スタイル：%{x}<br>構成比：%{y:.1f}%<extra>IoT支持者</extra>",
            ),
        )
        comparison_figure.update_layout(
            title="好きなインテリアスタイル｜IoT支持者と全体の構成比比較",
            height=430,
            margin=dict(l=35, r=30, t=55, b=110),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(color="#5B6B84", size=12),
            xaxis=dict(
                type="category",
                showline=False,
                zeroline=False,
                gridcolor="#DDE6EF",
                title="インテリア",
                tickangle=-25,
            ),
            yaxis=dict(
                title="構成比（%）",
                ticksuffix="%",
                rangemode="tozero",
                gridcolor="#DDE6EF",
            ),
            barmode="group",
            bargap=0.25,
            bargroupgap=0.08,
            legend=dict(title="比較群", orientation="v", y=1.12, x=1.02),
        )
        render_high_resolution_chart(comparison_figure, "iot_favorite_interior_styles_highres")
        st.caption(
            "IoT支持者と全体の好きなインテリアスタイルを、構成比で比較しています。"
            "複数回答のため、各グループ内の選択構成比を表示しています。"
        )
        st.dataframe(
            interior_counts[["順位", "スタイル", "選択数", "構成比"]].rename(
                columns={"構成比": "IoT選択者内の構成比（%）"}
            ).assign(
                **{
                    "IoT選択者内の構成比（%）": lambda data: data[
                        "IoT選択者内の構成比（%）"
                    ].round(1)
                }
            ),
            width="stretch",
            hide_index=True,
        )
        interior_top = str(interior_counts.iloc[0]["スタイル"])
        interior_top_share = float(interior_counts.iloc[0]["構成比"])
        overall_interior_share = (
            float(overall_interior_counts.get(interior_top, 0))
            / overall_interior_total
            * 100
            if overall_interior_total
            else 0
        )
        interior_difference = (
            interior_counts.set_index("スタイル")["構成比"]
            - overall_interior_counts.div(overall_interior_total).mul(100)
        )
        strongest_interior_style = str(interior_difference.idxmax())
        st.markdown("**グラフから見える傾向（好きなインテリアスタイル）**")
        st.markdown(
            f"IoT支持者の空間の好みでは、**{interior_top}**が中心にあります。"
        )
        st.markdown(
            f"{interior_top}は全体にも通じる好みですが、IoT支持者では"
            f"{'より強く' if interior_top_share >= overall_interior_share else 'やや控えめに'}"
            "表れています。"
        )
        st.markdown(
            f"全体との差が特に表れているのは**{strongest_interior_style}**です。"
            "IoT支持者は、便利さだけでなく、心地よく自分らしい空間として"
            "テクノロジーを取り入れたいと考えているようです。"
        )
        st.markdown(
            "先進的な機器を取り入れながらも、空間そのものは穏やかで心地よく、"
            "暮らしの中に自然になじむことを求めているようです。"
        )

render_theme_separator()
st.subheader("IoT選択者の好きなファッションスタイル")
st.markdown("### IoT選択者の好きなファッションスタイル")

# DB列（0始まりでは105番目）を好きなファッションスタイルの回答元として使う。
fashion_column = df.columns[105] if len(df.columns) > 105 else None
fashion_choices = DEFAULTS["好きなファッションスタイル"]
if fashion_column not in df_iot.columns:
    st.warning("好きなファッションスタイルの回答列が見つからないため、グラフを表示できません。")
else:
    fashion_values = df_iot[fashion_column].dropna().astype("string").str.strip()

    def normalize_fashion(value: object) -> str | None:
        text = str(value).strip()
        match = re.match(r"^(\d+)[.．]?\s*", text)
        if match:
            choice_number = int(match.group(1))
            if 1 <= choice_number <= len(fashion_choices):
                return fashion_choices[choice_number - 1]
        return text if text in fashion_choices else None

    fashion_counts = (
        fashion_values.map(normalize_fashion)
        .dropna()
        .value_counts()
        .reindex(fashion_choices, fill_value=0)
        .rename_axis("スタイル")
        .reset_index(name="選択数")
    )
    fashion_counts = fashion_counts.loc[fashion_counts["選択数"].gt(0)].sort_values(
        "選択数", ascending=False, kind="stable"
    )

    if fashion_counts.empty:
        st.info("IoT選択者のファッションスタイルに有効回答がないため、グラフを表示できません。")
    else:
        total_fashion_selections = int(fashion_counts["選択数"].sum())
        fashion_counts["構成比"] = (
            fashion_counts["選択数"].div(total_fashion_selections).mul(100)
        )
        fashion_counts["順位"] = range(1, len(fashion_counts) + 1)
        overall_fashion_counts = (
            df[fashion_column]
            .dropna()
            .astype("string")
            .str.strip()
            .map(normalize_fashion)
            .dropna()
            .value_counts()
            .reindex(fashion_choices, fill_value=0)
        )
        overall_fashion_total = int(overall_fashion_counts.sum())
        fashion_order = fashion_counts["スタイル"].tolist()
        comparison_figure = go.Figure()
        comparison_figure.add_trace(
            go.Bar(
                name="全体",
                x=fashion_order,
                y=[
                    float(overall_fashion_counts.get(style, 0))
                    / overall_fashion_total
                    * 100
                    for style in fashion_order
                ],
                marker_color="#A6B3C2",
                offsetgroup="overall",
                hovertemplate="スタイル：%{x}<br>回答者比率：%{y:.1f}%<extra>全体</extra>",
            )
        )
        comparison_figure.add_trace(
            go.Bar(
                name="IoT支持者",
                x=fashion_order,
                y=fashion_counts["構成比"],
                marker_color="#007ACC",
                offsetgroup="iot",
                hovertemplate="スタイル：%{x}<br>回答者比率：%{y:.1f}%<extra>IoT支持者</extra>",
            ),
        )
        comparison_figure.update_layout(
            title="好きなファッションスタイル｜IoT支持者と全体の構成比比較",
            height=500,
            margin=dict(l=35, r=30, t=55, b=135),
            paper_bgcolor="#FFFFFF",
            plot_bgcolor="#FFFFFF",
            font=dict(color="#5B6B84", size=12),
            xaxis=dict(
                type="category",
                showline=False,
                zeroline=False,
                gridcolor="#DDE6EF",
                title="ファッション",
                tickangle=-35,
            ),
            yaxis=dict(
                title="回答者比率（%）",
                ticksuffix="%",
                rangemode="tozero",
                gridcolor="#DDE6EF",
            ),
            barmode="group",
            bargap=0.25,
            bargroupgap=0.08,
            legend=dict(title="比較群", orientation="v", y=1.12, x=1.02),
        )
        render_high_resolution_chart(comparison_figure, "iot_favorite_fashion_styles_highres")
        st.caption(
            "IoT支持者と全体の好きなファッションスタイルを、回答者比率で比較しています。"
        )
        st.dataframe(
            fashion_counts[["順位", "スタイル", "選択数", "構成比"]].rename(
                columns={"構成比": "IoT支持者内の構成比（%）"}
            ).assign(
                **{
                    "IoT支持者内の構成比（%）": lambda data: data[
                        "IoT支持者内の構成比（%）"
                    ].round(1)
                }
            ),
            width="stretch",
            hide_index=True,
        )
        fashion_top = str(fashion_counts.iloc[0]["スタイル"])
        fashion_top_share = float(fashion_counts.iloc[0]["構成比"])
        overall_fashion_share = (
            float(overall_fashion_counts.get(fashion_top, 0))
            / overall_fashion_total
            * 100
            if overall_fashion_total
            else 0
        )
        fashion_difference = (
            fashion_counts.set_index("スタイル")["構成比"]
            - overall_fashion_counts.div(overall_fashion_total).mul(100)
        )
        strongest_fashion_style = str(fashion_difference.idxmax())
        st.markdown("**グラフから見える傾向（好きなファッションスタイル）**")
        st.markdown(
            f"IoT支持者の装いでは、**{fashion_top}**のようなスタイルが中心にあります。"
        )
        st.markdown(
            f"{fashion_top}は全体にも共通するスタイルですが、IoT支持者では"
            f"{'より強く' if fashion_top_share >= overall_fashion_share else 'やや控えめに'}"
            "表れています。"
        )
        st.markdown(
            f"全体との差が特に表れているのは**{strongest_fashion_style}**です。"
            "新しさを取り入れながらも、日常の動きやすさと自分らしさを両立する装いが"
            "好まれているようです。"
        )
        st.markdown(
            "主張しすぎないベーシックさや、軽やかな機能美が感じられます。"
            "新しいものを取り入れながらも、自分の生活に無理なくなじむことを大切にしているようです。"
        )

render_theme_separator()
st.subheader("今後やりたいこと｜IoT支持者と全体")
st.markdown("### IoT支持者の「今後やりたいこと」")
st.caption(
    "「将来｜」で始まる複数選択列を使い、各群の有効回答者に占める選択者の割合を比較しています。"
    "全体にはIoT支持者も含まれます。"
)
future_columns = [
    column for column in df.columns if str(column).startswith("将来｜")
]
future_choices = DEFAULTS["今後やりたいこと"]
future_aliases = {
    "投資・資産形成（NISA等）": "投資",
    "パソコン・インターネット閲覧": "パソコン・インターネット・SNS",
    "創作（文筆・絵画などアナログな創作活動）": "創作",
    "その他": "その他（自由記述）",
}

if not future_columns:
    st.error("「今後やりたいこと」の回答列（将来｜）が見つかりません。")
else:
    future_column_by_choice = {}
    for column in future_columns:
        item = str(column).split("｜", 1)[1].strip()
        matched_choice = next(
            (
                choice for choice in future_choices
                if item.replace(" ", "").startswith(choice.replace(" ", ""))
            ),
            None,
        )
        if matched_choice is None:
            matched_choice = next(
                (
                    choice for choice, alias in future_aliases.items()
                    if item.replace(" ", "").startswith(alias.replace(" ", ""))
                ),
                None,
            )
        if matched_choice is not None:
            future_column_by_choice[matched_choice] = column

    future_valid_rows = df[future_columns].notna().any(axis=1)
    future_iot_rows = future_valid_rows & iot_mask
    future_groups = {
        "全体": df.loc[future_valid_rows],
        "IoT支持者": df.loc[future_iot_rows],
    }
    future_results = []
    for group, respondents in future_groups.items():
        for choice in future_choices:
            column = future_column_by_choice.get(choice)
            selected_count = (
                int(pd.to_numeric(respondents[column], errors="coerce").fillna(0).gt(0).sum())
                if column is not None
                else 0
            )
            respondent_count = len(respondents)
            future_results.append({
                "やりたいこと": choice,
                "比較群": group,
                "選択者数": selected_count,
                "有効回答者数": respondent_count,
                "回答者比率": (
                    selected_count / respondent_count * 100
                    if respondent_count else 0
                ),
            })

    future_data = pd.DataFrame(future_results)
    future_order = (
        future_data.loc[future_data["比較群"].eq("IoT支持者")]
        .sort_values(["回答者比率", "やりたいこと"], ascending=[False, True], kind="stable")
        .head(10)["やりたいこと"]
        .tolist()
    )
    future_top10_data = future_data.loc[
        future_data["やりたいこと"].isin(future_order)
    ].copy()
    future_top10_data["やりたいこと"] = pd.Categorical(
        future_top10_data["やりたいこと"],
        categories=future_order,
        ordered=True,
    )
    future_figure = px.bar(
        future_top10_data,
        x="やりたいこと",
        y="回答者比率",
        color="比較群",
        barmode="group",
        category_orders={
            "やりたいこと": future_order,
            "比較群": ["全体", "IoT支持者"],
        },
        color_discrete_map={"全体": "#A6B3C2", "IoT支持者": "#007ACC"},
        custom_data=["選択者数", "有効回答者数"],
        title="今後やりたいこと｜IoT支持者TOP10と全体の回答者比率比較",
        labels={"回答者比率": "回答者比率（%）", "やりたいこと": "やりたいこと"},
    )
    future_figure.update_layout(
        xaxis=dict(type="category", tickangle=-35),
        yaxis=dict(ticksuffix="%", rangemode="tozero"),
        height=600,
        margin=dict(l=35, r=30, t=60, b=155),
        legend_title_text="比較群",
    )
    future_figure.update_traces(
        hovertemplate=(
            "%{x}<br>回答者比率：%{y:.1f}%<br>"
            "選択者：%{customdata[0]}人／有効回答者：%{customdata[1]}人"
            "<extra>%{fullData.name}</extra>"
        ),
    )
    render_high_resolution_chart(future_figure, "future_activities_iot_highres")

    future_comparison = future_data.pivot(
        index="やりたいこと", columns="比較群", values="回答者比率"
    ).fillna(0)
    future_comparison["IoT支持者との差"] = (
        future_comparison.get("IoT支持者", 0) - future_comparison.get("全体", 0)
    )
    future_comparison = future_comparison.sort_values(
        "IoT支持者との差", ascending=False, kind="stable"
    ).reset_index()
    future_top10_comparison = future_comparison.loc[
        future_comparison["やりたいこと"].isin(future_order)
    ].copy()
    st.dataframe(
        future_top10_comparison.round(1),
        width="stretch",
        hide_index=True,
    )
    strongest_future_choice = str(future_comparison.iloc[0]["やりたいこと"])
    strongest_future_difference = float(future_comparison.iloc[0]["IoT支持者との差"])
    st.markdown("**グラフから見える傾向（今後やりたいこと）**")
    st.markdown(
        f"IoT支持者で全体との差が最も大きいのは**{strongest_future_choice}**で、"
        f"差は{strongest_future_difference:+.1f}ポイントです。"
    )
    st.caption(
        "回答者比率＝各項目の選択者数 ÷ 各群の「将来｜」列に有効回答がある人数 × 100。"
        "複数回答のため、合計は100％になりません。"
    )

render_theme_separator()
st.subheader("自由記述｜IoT支持者の回答")
st.caption(
    "IoT支持者（理想の暮らしに「スマートホーム」または選択肢18を含む回答者）の"
    "自由記述を、回答内容のみ表示しています。氏名や回答者番号は表示しません。"
)
free_text_specs = [
    ("好きな色を選んだ理由", "上の色を選んだ理由"),
    ("マイモットー", "あなたのマイモットーは何ですか？"),
    ("好きなことば", "あなたの好きな言葉"),
    ("しあわせとは", "幸せとは何ですか？"),
]
free_text_iot = df.loc[iot_mask]
for title, column_fragment in free_text_specs:
    free_text_column = next(
        (column for column in df.columns if column_fragment in str(column)),
        None,
    )
    st.markdown(f"**{title}**")
    if free_text_column is None:
        st.warning(f"{title}の回答列が見つかりません。")
        continue
    raw_responses = free_text_iot[free_text_column].astype("string").str.strip()
    nonblank_responses = raw_responses.notna() & raw_responses.ne("")
    placeholder_responses = nonblank_responses & raw_responses.isin(["-", "ー", "―"])
    responses = raw_responses.loc[
        nonblank_responses & ~placeholder_responses
    ].rename("回答").reset_index(drop=True).to_frame()
    st.caption(
        f"IoT支持者{len(free_text_iot):,}人："
        f"空欄{int((~nonblank_responses).sum()):,}件／"
        f"無回答記号（-）{int(placeholder_responses.sum()):,}件／"
        f"有効回答{len(responses):,}件"
    )
    if responses.empty:
        st.info(f"IoT支持者の{title}に有効回答はありません。")
    else:
        st.dataframe(responses, width="stretch", hide_index=True)

color_reason_column = next(
    (column for column in df.columns if "上の色を選んだ理由" in str(column)),
    None,
)
st.markdown("**好きな色を選んだ理由のニュアンス比較**")
if color_reason_column is None:
    st.warning("好きな色を選んだ理由の回答列が見つかりません。")
else:
    color_reason = df[color_reason_column].astype("string").str.strip()
    color_reason_valid = (
        color_reason.notna()
        & color_reason.ne("")
        & ~color_reason.isin(["-", "ー", "―"])
    )
    color_reason_iot_valid = color_reason_valid & iot_mask
    all_color_reason_count = int(color_reason_valid.sum())
    iot_color_reason_count = int(color_reason_iot_valid.sum())
    keyword_specs = [
        ("自然・空・海・水・風・山・緑", ["自然", "空", "海", "水", "風", "山", "緑"]),
        ("落ち着き・安心・癒やし", ["落ち着", "安心", "安ら", "癒", "リラックス", "穏やか"]),
        ("明るさ・元気・前向きさ", ["明る", "元気", "活気", "前向き", "ポジティブ"]),
        ("好み・好き", ["好き", "好み", "惹かれ", "気に入"]),
        ("美しさ・きれい", ["きれい", "綺麗", "美し", "おしゃれ", "上品", "鮮やか"]),
        ("自分らしさ・個性", ["自分らし", "個性", "自分に", "似合"]),
        ("季節・思い出・記憶", ["季節", "春", "夏", "秋", "冬", "思い出", "記憶", "子供", "幼少"]),
    ]
    keyword_results = []
    for label, keywords in keyword_specs:
        pattern = "|".join(re.escape(keyword) for keyword in keywords)
        all_count = int(
            (color_reason_valid & color_reason.str.contains(
                pattern, regex=True, na=False
            )).sum()
        )
        iot_count = int(
            (color_reason_iot_valid & color_reason.str.contains(
                pattern, regex=True, na=False
            )).sum()
        )
        all_rate = (
            all_count / all_color_reason_count * 100
            if all_color_reason_count else 0
        )
        iot_rate = (
            iot_count / iot_color_reason_count * 100
            if iot_color_reason_count else 0
        )
        keyword_results.append({
            "表現の傾向": label,
            "全体回答数": all_count,
            "全体比率（%）": all_rate,
            "IoT支持者回答数": iot_count,
            "IoT支持者比率（%）": iot_rate,
            "差（ポイント）": iot_rate - all_rate,
        })
    keyword_data = pd.DataFrame(keyword_results).sort_values(
        "差（ポイント）", ascending=False, kind="stable"
    )
    st.dataframe(
        keyword_data.round({
            "全体比率（%）": 1,
            "IoT支持者比率（%）": 1,
            "差（ポイント）": 1,
        }),
        width="stretch",
        hide_index=True,
    )
    keyword_order = keyword_data["表現の傾向"].tolist()
    keyword_chart_data = keyword_data.melt(
        id_vars=["表現の傾向"],
        value_vars=["全体比率（%）", "IoT支持者比率（%）"],
        var_name="比較群",
        value_name="回答者比率",
    )
    keyword_chart_data["比較群"] = keyword_chart_data["比較群"].map({
        "全体比率（%）": "全体",
        "IoT支持者比率（%）": "IoT支持者",
    })
    keyword_figure = px.bar(
        keyword_chart_data,
        x="表現の傾向",
        y="回答者比率",
        color="比較群",
        barmode="group",
        category_orders={
            "表現の傾向": keyword_order,
            "比較群": ["全体", "IoT支持者"],
        },
        color_discrete_map={"全体": "#A6B3C2", "IoT支持者": "#007ACC"},
        title="好きな色を選んだ理由｜表現傾向の比較",
        labels={"表現の傾向": "", "回答者比率": "回答者比率（%）"},
    )
    keyword_figure.update_layout(
        xaxis=dict(type="category", tickangle=-35),
        yaxis=dict(ticksuffix="%", rangemode="tozero"),
        height=560,
        margin=dict(l=35, r=30, t=60, b=155),
        legend_title_text="比較群",
    )
    keyword_figure.update_traces(
        hovertemplate="%{x}<br>回答者比率：%{y:.1f}%<extra>%{fullData.name}</extra>",
    )
    render_high_resolution_chart(
        keyword_figure,
        "color_reason_nuance_comparison_highres",
    )
    st.markdown(
        "**IoT支持者では、自然・空・海など環境を想起させる表現や、"
        "自分らしさ・個性に関する表現が、全体よりやや多く見られます。**"
    )
    st.markdown(
        "**一方、「落ち着き・安心・癒やし」は全体と大きな差がなく、"
        "IoT支持者だけに特徴的な表現とは言い切れません。**"
    )
    st.caption(
        f"有効回答：全体{all_color_reason_count:,}件／"
        f"IoT支持者{iot_color_reason_count:,}件。"
        "1つの自由記述は最大3色の選択全体への回答であり、特定の色だけの理由には直接結びつけられません。"
        "キーワードは表現の重なりを含む参考集計です。"
    )

render_theme_separator()
st.subheader("総合コメント｜IoTで暮らしをUp Gradeする")
st.markdown(
    "**スマートホーム（IoT）に着目したのは、理想の暮らしの中でその存在感が高まり、"
    "これからの「心地よい暮らし」を考える手がかりになると感じたからです。** "
    "IoT志向は一部の先進層だけのものではなく、年代や性別を越えて、"
    "安心・快適さや自分の時間を大切にしたい人の価値観として表れています。"
)
st.markdown(
    "**分析から見えてきたのは、IoTが「便利な機器」から「暮らしの質を高める環境」へ広がっていることです。** "
    "高級感の定義では、安心・安全・快適な空間や、大切な人と過ごす特別な時間が重視され、"
    "プレミアム消費でも、心身のリフレッシュや気持ちを高めることが目的として表れています。"
    "住まいや体験を整えることが、毎日を前向きにするUp Gradeにつながっています。"
)
st.markdown(
    "**今後やりたいことからは、IoT支持者の関心が住まいの効率化だけでなく、"
    "デジタルを使った情報収集や映像・ゲーム、旅行などの体験にも広がっていることが見えてきます。** "
    "特に「パソコン・インターネット閲覧」「映像鑑賞」「ゲーム」は全体より高く、"
    "IoTは機器単体ではなく、日常の楽しみ方や時間の使い方を支える基盤として捉えられている可能性があります。"
)
st.markdown(
    "**IoT支持者の感性には、先進性と人らしい心地よさが共存しています。** "
    "青やスカイブルーに表れる知性と信頼感、ライトグリーンの自然な心地よさ、"
    "黒の洗練された機能美、赤やピンクの前向きなエネルギー。"
    "テクノロジーには、冷たさではなく、気持ちを軽やかにする彩りが求められています。"
)
st.markdown(
    "**好きな色を選んだ理由にも、IoT支持者らしいニュアンスが表れています。** "
    "全体と比べて、自然・空・海・水など環境を想起させる表現や、"
    "自分らしさ・個性に関する表現がやや多く、色を単なる好みだけでなく、"
    "心地よい環境や自分のスタイルを表すものとして捉えている可能性があります。"
    "ただし、これは最大3色の選択全体に対する自由記述の比較であり、色ごとの理由を直接示すものではありません。"
)
st.markdown(
    "**空間と装いの好みからも、IoT支持者のスタイルが見えてきます。** "
    "インテリアでは先進的な機器を取り入れながら、空間は穏やかで自然になじむことを重視し、"
    "ファッションではベーシックさや機能美を土台に、自分らしさを楽しんでいます。"
    "新しさを取り入れながら、日常から浮かないことが価値になっています。"
)
st.markdown(
    "**年齢・性別・家族構成や仕事の状況を越えて、IoTはそれぞれの暮らしに合わせて価値を持つ可能性があります。** "
    "30代の志向の高まりや、40・50代の安定した関心、女性の働き方による違いなど、"
    "支持の背景は一つではありません。だからこそ、使う人の生活に寄り添い、"
    "必要なときに助け、普段は意識させない設計が大切になります。"
)
st.markdown(
    "**自由記述からは、IoT支持者の価値観を補足する言葉も確認できます。** "
    "ただし、マイモットー・好きなことば・しあわせとはの有効回答は各3件にとどまるため、"
    "これらはIoT支持者全体の傾向ではなく、個別の参考例として扱います。"
)
st.markdown(
    "**目指したいのは、「暮らしを静かに支えるスマートさ」です。** "
    "安心・快適さ、自分の時間、自然体でいられる空間、そして自分らしい彩り。"
    "これらを一つにつなぐことで、IoTは日々の負担を軽くするだけでなく、"
    "暮らしを前向きにUp Gradeし、気持ちまで整えるデザインへと広がっていきます。"
)
st.caption(
    "総合コメントには、確認できた傾向と、そこから考えた仮説・提案を含みます。"
    "時代背景や購入動機との因果関係は検証していません。2026年には理想の暮らしの選択肢追加があり、"
    "順位上昇を継続的な需要拡大とは断定できません。"
    "年収は世帯年収とは明記されておらず、家計の余裕を直接示すものではありません。"
    "自然体派は非支持者にも多く、生活充実派の分類にはデジタル化の設問が含まれます。"
)

chart_exports = st.session_state.get("chart_exports", {})
if chart_exports:
    zip_buffer = BytesIO()
    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as archive:
        for filename, png_bytes in sorted(chart_exports.items()):
            archive.writestr(filename, png_bytes)
    st.download_button(
        label=f"📦 すべてのグラフ（{len(chart_exports)}点）を高解像度PNGで一括ダウンロード",
        data=zip_buffer.getvalue(),
        file_name="IoT_all_highres_charts.zip",
        mime="application/zip",
        key="download_all_highres_charts",
    )
