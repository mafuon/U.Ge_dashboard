import os
import zipfile
from pathlib import Path
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image

from components.sensory import DEFAULTS
from components.wellbeing import PENTAGON_ORDER, current_pentagon_scores, current_pentagon_types


def generate_and_export_charts(output_dirs: list[Path], scale: int = 3):
    base_dir = Path(__file__).resolve().parent
    data_path = base_dir / "data" / "U.Ge「幸せ」アンケート集計データ_version27_.csv"

    if not data_path.exists():
        raise FileNotFoundError(f"データファイルが存在しません: {data_path}")

    df = pd.read_csv(data_path, encoding="utf-8")
    if df.empty:
        raise ValueError("CSVにデータ行がありません。")

    lifestyle_columns = [
        column for column in df.columns
        if "理想の暮らし" in column or column.startswith("1つ以上、5つまで選んでください。")
    ]
    df = df.copy()
    df["年度"] = pd.to_datetime(df["タイムスタンプ"], errors="coerce").dt.year.astype("Int64")
    df["年代"] = df["◆年齢"].astype("string").str.strip()
    df["性別"] = df["◆性別"].astype("string").str.strip()
    valid_rows = (
        df["年度"].notna()
        & df["年代"].str.fullmatch(r"\d+代(?:～|〜)?", na=False)
        & df["性別"].notna()
        & df["性別"].ne("")
    )

    iot_mask = pd.Series(False, index=df.index)
    for column in lifestyle_columns:
        answers = df[column].astype("string")
        iot_mask |= (
            answers.str.contains("スマートホーム", regex=False, na=False)
            | answers.str.contains(r"(?:^|[,|\n])\s*18\s*(?:$|[,|\n])", regex=True, na=False)
        )

    figures: dict[str, go.Figure] = {}

    # 1. 理想の暮らしランキング推移
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
    ))
    fig_rank.update_layout(
        title=f"{target}｜順位推移（2023〜2026）",
        xaxis=dict(title="年度", tickmode="array", tickvals=ranking_years, tickformat="d"),
        yaxis=dict(title="順位（数字が小さいほど上位）", autorange="reversed", dtick=1),
        height=450,
        width=850,
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
    )
    figures["smart_home_trend_highres.png"] = fig_rank

    # 2 & 3. 年代別・性別のIoT志向率
    comparison_years = [2024, 2025, 2026]
    comparison_df = df.loc[valid_rows & df["年度"].isin(comparison_years), ["年度", "年代", "性別"]].copy()
    comparison_df["IoT志向"] = iot_mask.loc[comparison_df.index]
    age_order = sorted(comparison_df["年代"].unique(), key=lambda value: int(value.split("代")[0]))

    for category, label, order, fname in [
        ("年代", "年代別", age_order, "iot_propensity_by_age_highres.png"),
        ("性別", "性別", sorted(comparison_df["性別"].unique()), "iot_propensity_by_gender_highres.png"),
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
            title=f"{label}のIoT志向率（2024〜2026）",
            labels={"IoT志向率": "IoT志向率（%）"},
        )
        fig_rate.update_layout(
            xaxis=dict(type="category"),
            yaxis=dict(ticksuffix="%", rangemode="tozero"),
            legend_title_text="年度",
            height=450,
            width=850,
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
        )
        figures[fname] = fig_rate

    df_2026 = df.loc[df["年度"].eq(2026)].copy()
    iot_mask_2026 = iot_mask.loc[df_2026.index]
    df_iot_2026 = df_2026.loc[iot_mask_2026].copy()

    # 4. 高級感の定義（DF列）
    luxury_column = (
        "2026年追加｜あなたにとって、日々のくらしの中で最も「高級（贅沢）」だと感じるのは、"
        "どのような状態・体験ですか？次の中からあなたに最も近いものを1つだけ選んでください。"
    )
    if luxury_column in df.columns and not df_2026.empty:
        luxury_results = []
        for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
            values = pd.to_numeric(respondents[luxury_column], errors="coerce")
            valid_choices = values.isin(range(1, 7))
            response_count = int(valid_choices.sum())
            if response_count > 0:
                counts = values.loc[valid_choices].value_counts().reindex(range(1, 7), fill_value=0)
                luxury_results.append(pd.DataFrame({
                    "選択肢": [f"選択肢{number}" for number in counts.index],
                    "比較群": group,
                    "回答数": counts.to_numpy(),
                    "回答割合": counts.to_numpy() / response_count * 100,
                }))
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
                labels={"回答割合": "回答割合（%）"},
            )
            fig_luxury.update_layout(
                yaxis=dict(ticksuffix="%", rangemode="tozero"),
                height=450,
                width=850,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
            )
            figures["luxury_definition_iot_highres.png"] = fig_luxury

    # 5. プレミアム消費の目的（DG列）
    premium_column = (
        "2026年追加｜あなたが通常より「少し高価なもの（プレミアムな商品・サービス）」を購入・利用するとき、"
        "その主な目的や動機は何ですか？あてはまるものを最大3つまで選んでください。"
    )
    if premium_column in df.columns and not df_2026.empty:
        premium_results = []
        for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
            selections = respondents[premium_column].astype("string").str.split(r"[,|\n]", regex=True).explode().str.strip()
            selections = selections.loc[selections.notna() & selections.ne("")]
            valid_choices = selections.isin([str(number) for number in range(1, 10)])
            valid_selections = selections.loc[valid_choices].reset_index()
            valid_selections.columns = ["回答者", "選択肢番号"]
            valid_selections = valid_selections.drop_duplicates(["回答者", "選択肢番号"])
            response_count = int(valid_selections["回答者"].nunique())
            if response_count > 0:
                counts = valid_selections["選択肢番号"].value_counts().reindex(
                    [str(number) for number in range(1, 10)], fill_value=0,
                )
                premium_results.append(pd.DataFrame({
                    "目的": [f"選択肢{number}" for number in counts.index],
                    "比較群": group,
                    "選択率": counts.to_numpy() / response_count * 100,
                }))
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
                labels={"選択率": "選択率（%）"},
            )
            fig_premium.update_layout(
                yaxis=dict(ticksuffix="%", rangemode="tozero"),
                height=450,
                width=850,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
            )
            figures["premium_consumption_iot_highres.png"] = fig_premium

    # 6. Up-Grade（奮発したジャンル）
    upgrade_columns = [
        column for column in df.columns
        if column.startswith("奮発して良かったジャンル｜")
    ]
    if upgrade_columns and not df_2026.empty:
        upgrade_results = []
        for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
            for column in upgrade_columns:
                values = pd.to_numeric(respondents[column], errors="coerce")
                valid_choices = values.isin([0, 1])
                genre = column.split("｜", 1)[1].split("（", 1)[0].strip()
                response_count = int(valid_choices.sum())
                if response_count > 0:
                    selected_count = int(values.loc[valid_choices].eq(1).sum())
                    upgrade_results.append({
                        "ジャンル": genre,
                        "比較群": group,
                        "選択率": selected_count / response_count * 100,
                    })
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
                labels={"選択率": "選択率（%）"},
            )
            fig_upgrade.update_layout(
                xaxis=dict(tickangle=-30),
                yaxis=dict(ticksuffix="%", rangemode="tozero"),
                height=550,
                width=950,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
            )
            figures["upgrade_iot_highres.png"] = fig_upgrade

    # 7. 高級感のあるインテリア（DR列）
    interior_column = (
        "あなたがイメージする「高級感のあるインテリア」は次のうちどれですか。"
        "最もあてはまるものをお答えください。"
    )
    if interior_column in df.columns and not df_2026.empty:
        interior_results = []
        interior_labels = ["先進的な", "上品な", "風格のある", "豪華な", "シンプルな", "温もりのある"]
        for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
            values = pd.to_numeric(respondents[interior_column], errors="coerce")
            valid_choices = values.isin(range(1, 9))
            response_count = int(valid_choices.sum())
            if response_count > 0:
                counts = values.loc[valid_choices].value_counts().reindex(range(1, 7), fill_value=0)
                interior_results.append(pd.DataFrame({
                    "インテリア": interior_labels,
                    "比較群": group,
                    "回答割合": counts.to_numpy() / response_count * 100,
                }))
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
                labels={"回答割合": "回答割合（%）"},
            )
            fig_interior.update_layout(
                yaxis=dict(ticksuffix="%", rangemode="tozero"),
                height=450,
                width=850,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
            )
            figures["interior_iot_highres.png"] = fig_interior

    # 8. 年収（DS列）
    income_column = "あなたの年収を教えてください"
    if income_column in df.columns and not df_2026.empty:
        income_categories = (
            df_2026[income_column].dropna().astype("string").str.strip()
        )
        income_categories = income_categories.loc[income_categories.ne("")].unique().tolist()
        income_categories = sorted(
            income_categories,
            key=lambda value: (
                0 if "300万円未満" in value and "～" in value and "300万円～" not in value
                else 1 if "300万円～600万円" in value
                else 2 if "600万円～800万円" in value
                else 3 if "800万円～1000万円" in value
                else 4 if "1000万円～1500万円" in value
                else 5 if "1500万円～3000万円" in value
                else 6 if "3000万円以上" in value
                else 7
            ),
        )
        income_results = []
        for group, respondents in [("全体", df_2026), ("IoT支持者", df_iot_2026)]:
            values = respondents[income_column].dropna().astype("string").str.strip()
            response_count = int(values.ne("").sum())
            if response_count > 0:
                counts = values.value_counts().reindex(income_categories, fill_value=0)
                income_results.append(pd.DataFrame({
                    "年収": counts.index,
                    "比較群": group,
                    "回答割合": counts.to_numpy() / response_count * 100,
                }))
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
                labels={"回答割合": "回答割合（%）"},
            )
            fig_income.update_layout(
                xaxis=dict(type="category", tickangle=-30),
                yaxis=dict(ticksuffix="%", rangemode="tozero"),
                height=550,
                width=900,
                plot_bgcolor="#FFFFFF",
                paper_bgcolor="#FFFFFF",
            )
            figures["income_iot_highres.png"] = fig_income

    # 9 & 10. ペンタゴンタイプ構成比
    pentagon_scores = current_pentagon_scores(df)
    if len(pentagon_scores.columns) == len(PENTAGON_ORDER):
        pentagon_years = list(range(2022, 2027))
        pentagon_source = df.loc[df["年度"].isin(pentagon_years), ["年度"]].copy()
        pentagon_source["タイプ"] = current_pentagon_types(pentagon_scores).loc[pentagon_source.index]
        pentagon_source["比較群"] = iot_mask.loc[pentagon_source.index].map(
            {True: "IoT支持者", False: "IoT非支持者"},
        )
        pentagon_results = []
        for year in pentagon_years:
            for group in ["IoT非支持者", "IoT支持者"]:
                respondents = pentagon_source.loc[
                    pentagon_source["年度"].eq(year) & pentagon_source["比較群"].eq(group)
                ]
                types = respondents["タイプ"].dropna()
                if not types.empty:
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
                    labels={"構成比": "構成比（%）", "タイプ": "現在のペンタゴンタイプ"},
                    title=(
                        "IoT支持者・非支持者の現在のペンタゴンタイプ構成比"
                        f"（{display_years[0]}〜{display_years[-1]}年）"
                    ),
                )
                fig_pentagon.update_layout(
                    height=800 if display_years[0] == 2024 else 450,
                    width=1000,
                    legend_title_text="比較群",
                    plot_bgcolor="#FFFFFF",
                    paper_bgcolor="#FFFFFF",
                )
                fig_pentagon.update_xaxes(tickangle=-25, showticklabels=True)
                fig_pentagon.update_yaxes(ticksuffix="%", rangemode="tozero")
                figures[f"iot_pentagon_{display_years[0]}_{display_years[-1]}_highres.png"] = fig_pentagon

    # 保存処理
    exported_files = []
    for output_dir in output_dirs:
        output_dir.mkdir(parents=True, exist_ok=True)
        for filename, fig in figures.items():
            margin = fig.layout.margin.to_plotly_json() if fig.layout.margin else {}
            fig.update_layout(
                margin={
                    "l": max(int(margin.get("l", 0)), 70) + 30,
                    "r": max(int(margin.get("r", 0)), 30) + 30,
                    "t": max(int(margin.get("t", 0)), 50) + 30,
                    "b": max(int(margin.get("b", 0)), 50) + 30,
                    "pad": 20,
                },
                autosize=True,
            )
            fig.update_traces(cliponaxis=False)
            file_path = output_dir / filename
            fig.write_image(str(file_path), scale=scale)
            if output_dir == output_dirs[0]:
                with Image.open(file_path) as img:
                    w, h = img.size
                exported_files.append({
                    "filename": filename,
                    "resolution": f"{w}x{h}px",
                    "size_kb": f"{file_path.stat().st_size / 1024:.1f} KB",
                    "path": str(file_path),
                })
                print(f"Exported: {filename} ({w}x{h}px, {file_path.stat().st_size / 1024:.1f} KB)")

    return exported_files


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    workspace_output = base_dir / "highres_charts"
    user_downloads = Path.home() / "Downloads" / "highres_charts"

    print("高解像度グラフの出力中 (scale=3)...")
    results = generate_and_export_charts([workspace_output, user_downloads], scale=3)

    # ZIPファイルも作成
    zip_path = Path.home() / "Downloads" / "IoT_highres_charts.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            p = Path(r["path"])
            zf.write(p, arcname=p.name)
    print(f"\nZIPアーカイブを作成しました: {zip_path} ({zip_path.stat().st_size / 1024:.1f} KB)")
