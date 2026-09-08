from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from components.sidebar import render_sidebar
from components.cards import render_metric_cards
from components.charts import render_charts, render_comment_section, render_filtered_details, render_pink_analysis, render_trend
from components.sensory import DEFAULTS, render_sensory_analysis
from components.wellbeing import render_wellbeing_analysis


st.set_page_config(page_title="U.Ge アンケート分析ダッシュボード", page_icon="📊", layout="wide")

base_dir = Path(__file__).resolve().parent
css_path = base_dir / "assets" / "style.css"
with open(css_path, encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def sample_data():
    choices = DEFAULTS
    return pd.DataFrame(
        {
            "年度": [2023, 2023, 2024, 2024, 2025, 2025],
            "年齢": ["20代", "30代", "40代", "20代", "30代", "40代"],
            "性別": ["男性", "女性", "男性", "女性", "男性", "女性"],
            "居住地": ["東京", "大阪", "福岡", "東京", "大阪", "福岡"],
            "同居家族": ["単身", "夫婦のみ", "家族（2人以上、親・子供・孫など）", "単身", "家族（2人以上、親・子供・孫など）", "その他"],
            "職業": ["会社員・公務員", "経営者・役員", "自営業・フリーランス", "派遣・契約社員", "パート・アルバイト", "専業主婦/専業主夫"],
            "世帯年収": ["①～300万円未満", "②300万円～600万円未満", "③600万円～800万円未満", "④800万円～1000万円未満", "⑤1000万円～1500万円未満", "⑥1500万円～3000万円未満"],
            "幸福度平均": [72.5, 81.2, 76.4, 74.8, 85.1, 79.6],
            "幸福度スコア": [72.5, 81.2, 76.4, 74.8, 85.1, 79.6],
            "現在の幸福状態": [4, 5, 4, 4, 5, 5],
            "幸せに必要なこと": [6, 6, 5, 5, 6, 5],
            "コメント": [
                "住みやすく、家族と過ごす時間が増えた。",
                "支援体制が整い、安心して暮らせている。",
                "地域のイベントが増えて、交流の機会が増えた。",
                "ライフスタイルの変化に適応できている。",
                "暮らしの質が上がり、満足度が高い。",
                "都心へのアクセスが良く、利便性が高い。",
            ],
            "好きな色": ["1, 15, 19", "2, 8, 20", "3, 10, 27", "4, 11, 25", "5, 16, 28", "6, 18, 29"],
            "好きなインテリアスタイル": [choices["好きなインテリアスタイル"][0], choices["好きなインテリアスタイル"][1], choices["好きなインテリアスタイル"][2], choices["好きなインテリアスタイル"][3], choices["好きなインテリアスタイル"][4], choices["好きなインテリアスタイル"][0]],
            "理想の暮らし方": ["1, 5, 9", "2, 7, 10", "3, 11, 19", "4, 12, 18", "6, 15, 24", "8, 16, 27"],
            "好きなファッションスタイル": [choices["好きなファッションスタイル"][0], choices["好きなファッションスタイル"][1], choices["好きなファッションスタイル"][2], choices["好きなファッションスタイル"][3], choices["好きなファッションスタイル"][4], choices["好きなファッションスタイル"][5]],
            "最も高級だと感じる体験": [choices["最も高級だと感じる体験"][0], choices["最も高級だと感じる体験"][1], choices["最も高級だと感じる体験"][2], choices["最も高級だと感じる体験"][3], choices["最も高級だと感じる体験"][4], choices["最も高級だと感じる体験"][0]],
            "プレミアム購入目的": ["1, 2", "3, 4", "2, 5", "1, 6", "3, 7", "4, 5"],
            "Up-Gradeジャンル": ["1, 4", "2, 6", "3, 8", "4, 5", "6, 7", "1, 9"],
            "高級感のあるインテリアイメージ": [choices["高級感のあるインテリアイメージ"][0], choices["高級感のあるインテリアイメージ"][1], choices["高級感のあるインテリアイメージ"][2], choices["高級感のあるインテリアイメージ"][3], choices["高級感のあるインテリアイメージ"][4], choices["高級感のあるインテリアイメージ"][5]],
            "今後やりたいこと": ["1, 10, 16", "2, 6, 18", "3, 8, 14", "4, 12, 21", "5, 20, 27", "9, 15, 23"],
            "comment_tag": ["地域", "住まい", "安心", "住まい", "地域", "利便性"],
        }
    )


def normalize_to_6(raw, min_val=1, max_val=5):
    if pd.isna(raw) or max_val <= min_val:
        return pd.NA
    return (raw - min_val) / (max_val - min_val) * 6


def normalize_columns(df):
    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    aliases = {
        "年代": "年齢",
        "年齢層": "年齢",
        "都道府県": "居住地",
        "地域": "居住地",
        "世帯構成": "同居家族",
        "家族構成": "同居家族",
        "年収": "世帯年収",
        "幸福度": "幸福度スコア",
        "幸福度平均値": "幸福度平均",
        "現在の幸福度": "現在の幸福状態",
        "自由記述": "コメント",
        "好きな色（3つ）": "好きな色",
        "幸福度項目（5軸）": "幸福度項目",
    }
    rename_map = {source: target for source, target in aliases.items() if source in df.columns and target not in df.columns}
    df = df.rename(columns=rename_map).copy()
    prefix_aliases = {
        "◆性別": "性別",
        "◆年齢": "年齢",
        "◆居住地": "居住地",
        "◆同居家族": "同居家族",
        "◆職業": "職業",
        "◆あなたの世帯年収": "世帯年収",
        "◆あなたにとって「幸せ」に必要": "幸せに必要なこと",
        "◆好きな色を3つ選んでください": "好きな色",
        "インテリアスタイル｜選択肢5つ": "好きなインテリアスタイル",
        "好きなインテリアスタイル｜選択肢5つ": "好きなインテリアスタイル",
        "◆あなたが好きなインテリアスタイル": "好きなインテリアスタイル",
        "◆あなたにとって理想の暮らし方": "理想の暮らし方",
        "1つ以上、5つまで選んでください。": "理想の暮らし方",
        "あなたが好きなファッションスタイルを選んでください。（1つだけ選択）": "好きなファッションスタイル",
        "◆あなたが好きなファッションスタイル": "好きなファッションスタイル",
        "2024年特別設問｜これらピンクの中に「しあわせ」を感じる": "幸せを感じるピンク",
        "2026年追加｜あなたにとって、日々のくらしの中で最も「高級（贅沢）」": "最も高級だと感じる体験",
        "◆あなたにとって、日々のくらしの中で最も「高級（贅沢）」": "最も高級だと感じる体験",
        "2026年追加｜あなたが通常より「少し高価なもの": "プレミアム購入目的",
        "◆あなたが通常より「少し高価なもの": "プレミアム購入目的",
        "◆あなたがここ1年間のなかで、自分やくらしを「Up-Grade": "Up-Gradeジャンル",
        "あなたがイメージする「高級感のあるインテリア」": "高級感のあるインテリアイメージ",
        "◆あなたがイメージする「高級感のあるインテリア」": "高級感のあるインテリアイメージ",
        "◆あなたが今後やりたいこと": "今後やりたいこと",
        "◆あなたの現在の状況": "現在の幸福状態",
    }
    for prefix, target in prefix_aliases.items():
        source = next((column for column in df.columns if column.startswith(prefix)), None)
        if source and target not in df.columns:
            df[target] = df[source]

    if "幸せを感じるピンク" not in df.columns:
        pink_column = next(
            (
                column
                for column in df.columns
                if "ピンク" in column
                and any(word in column for word in ("幸せ", "しあわせ"))
                and "理由" not in column
            ),
            None,
        )
        if pink_column:
            df["幸せを感じるピンク"] = df[pink_column]

    def copy_best_happiness_column(target, matches):
        candidates = [column for column in df.columns if column != target and matches(column)]
        if not candidates:
            return
        best_column = max(candidates, key=lambda column: df[column].notna().sum())
        if target not in df.columns or not df[target].notna().any():
            df[target] = df[best_column]

    copy_best_happiness_column(
        "現在の幸福状態",
        lambda column: "現在" in column and any(word in column for word in ("幸福", "幸せ", "状況")),
    )
    copy_best_happiness_column(
        "理想的な幸福状態",
        lambda column: "理想" in column and any(word in column for word in ("幸福", "幸せ")),
    )

    if "世帯年収" not in df.columns:
        income_column = next((column for column in df.columns if "年収" in column), None)
        if income_column:
            df["世帯年収"] = df[income_column]

    for prefix, target in (("奮発して良かったジャンル｜", "Up-Gradeジャンル"), ("将来｜", "今後やりたいこと")):
        source_columns = [column for column in df.columns if column.startswith(prefix)]
        choices = DEFAULTS.get(target, [])
        if source_columns and target not in df.columns:
            selected = pd.DataFrame(index=df.index)
            for choice in choices:
                source = next((column for column in source_columns if column.removeprefix(prefix).replace(" ", "").startswith(choice.replace(" ", ""))), None)
                if source:
                    selected[choice] = pd.to_numeric(df[source], errors="coerce").fillna(0).gt(0)
            if not selected.empty:
                df[target] = selected.apply(lambda row: ", ".join(row.index[row]), axis=1).replace("", pd.NA)

    if "年度" not in df.columns and "タイムスタンプ" in df.columns:
        timestamps = pd.to_datetime(df["タイムスタンプ"], errors="coerce")
        df["年度"] = timestamps.dt.year

    axis_groups = {
        "Q1_自己実現派": ["自己実現"],
        "Q2_自己成長派": ["自己成長"],
        "Q3_社会交流派": ["自己発信", "社会交流"],
        "Q4_生活充実派": ["生活充実"],
        "Q5_自然体派": ["自然体"],
    }
    for target, tokens in axis_groups.items():
        axis_columns = [column for column in df.columns if column.startswith("質問") and any(token in column for token in tokens)]
        if axis_columns:
            numeric_axes = df[axis_columns].apply(pd.to_numeric, errors="coerce")
            raw_score = numeric_axes.mean(axis=1)
            scale_max = 7 if numeric_axes.max().max() > 5 else 5
            df[target] = raw_score.apply(normalize_to_6, max_val=scale_max).clip(lower=0, upper=6)
    axis_columns = [column for column in axis_groups if column in df.columns]

    if axis_columns and ("現在の幸福状態" not in df.columns or not df["現在の幸福状態"].notna().any()):
        df["現在の幸福状態"] = df[axis_columns].mean(axis=1).round().astype("Int64")
    if axis_columns:
        current_scores = df[axis_columns].apply(pd.to_numeric, errors="coerce")
        current_maximum = current_scores.max(axis=1)
        current_unique = current_scores.eq(current_maximum, axis=0).sum(axis=1).eq(1)
        current_types = current_scores.idxmax(axis=1).map(
            dict(zip(axis_groups, ("自己実現派", "自己成長派", "社会交流派", "生活充実派", "自然体派")))
        )
        df["現在の幸福度タイプ"] = current_types.where(current_unique)

    ideal_source_columns = [
        column
        for column in df.columns
        if any(column.endswith(f"｜{label}") for label in ("自己実現派", "自己成長派", "社会交流派", "生活充実派", "自然体派"))
    ]
    if ideal_source_columns and ("理想的な幸福状態" not in df.columns or not df["理想的な幸福状態"].notna().any()):
        ideal_scores = df[ideal_source_columns].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        df["理想的な幸福状態"] = ideal_scores.apply(normalize_to_6, max_val=7).round().astype("Int64")
    if ideal_source_columns:
        ideal_groups = {
            "自己実現派": [column for column in ideal_source_columns if column.endswith("｜自己実現派")],
            "自己成長派": [column for column in ideal_source_columns if column.endswith("｜自己成長派")],
            "社会交流派": [column for column in ideal_source_columns if column.endswith("｜社会交流派")],
            "生活充実派": [column for column in ideal_source_columns if column.endswith("｜生活充実派")],
            "自然体派": [column for column in ideal_source_columns if column.endswith("｜自然体派")],
        }
        ideal_type_scores = pd.DataFrame({
            label: df[columns].apply(pd.to_numeric, errors="coerce").mean(axis=1)
            for label, columns in ideal_groups.items() if columns
        })
        ideal_maximum = ideal_type_scores.max(axis=1)
        ideal_unique = ideal_type_scores.eq(ideal_maximum, axis=0).sum(axis=1).eq(1)
        ideal_types = ideal_type_scores.idxmax(axis=1)
        df["理想の幸福度タイプ"] = ideal_types.where(ideal_unique & df["現在の幸福度タイプ"].notna())

    if "幸福度平均" not in df.columns and axis_columns:
        df["幸福度平均"] = df[axis_columns].mean(axis=1).div(6).mul(100)
        df["幸福度スコア"] = df["幸福度平均"]

    if "年度" in df.columns:
        numeric_year = pd.to_numeric(df["年度"], errors="coerce")
        df["年度"] = numeric_year.where(numeric_year.notna(), df["年度"])
    return df


def read_uploaded_csv(uploaded_file):
    raw = uploaded_file.getvalue()
    last_error = None
    for encoding in ("utf-8-sig", "cp932", "shift_jis", "utf-16"):
        try:
            return normalize_columns(pd.read_csv(BytesIO(raw), encoding=encoding))
        except (UnicodeDecodeError, pd.errors.ParserError) as error:
            last_error = error
    raise ValueError(f"CSVを読み込めませんでした: {last_error}")


def load_data(uploaded_file=None):
    if uploaded_file is not None:
        return read_uploaded_csv(uploaded_file)

    excel_path = base_dir / "data" / "uge_survey.xlsx"
    if excel_path.exists():
        df = pd.read_excel(excel_path)
    else:
        df = sample_data()
    df = normalize_columns(df)
    if "幸福度平均" not in df.columns:
        score_cols = [c for c in df.columns if "スコア" in c or "満足度" in c or "幸福" in c]
        if score_cols:
            numeric_scores = df[score_cols].apply(pd.to_numeric, errors="coerce")
            if numeric_scores.notna().any().any():
                df["幸福度平均"] = numeric_scores.mean(axis=1)
    return df


def render_section_navigation():
    st.markdown(
        '''<nav class="section-navigation" aria-label="セクション移動">
            <a class="section-navigation__item section-navigation__item--wellbeing" href="#wellbeing">ウェルビーイング分析<span>01-02</span></a>
            <a class="section-navigation__item section-navigation__item--sensory" href="#sensory">感性分析 | すきな色・暮らし・行動<span>03-11</span></a>
            <a class="section-navigation__item section-navigation__item--happiness" href="#happiness">しあわせ指数<span>12</span></a>
            <a class="section-navigation__item section-navigation__item--pink" href="#pink">しあわせピンク<span>13</span></a>
            <a class="section-navigation__item section-navigation__item--comments" href="#comments">自由記述<span>回答を見る</span></a>
        </nav>''',
        unsafe_allow_html=True,
    )


def main():
    uploaded_file = st.sidebar.file_uploader("CSVファイルをアップロード", type=["csv"], help="UTF-8、UTF-8 BOM、Shift-JIS、CP932に対応", key="csv_uploader")
    st.markdown('<div class="dashboard-title">アンケート分析ダッシュボード</div>', unsafe_allow_html=True)
    if uploaded_file is None:
        st.info("サイドバーからCSVファイルをアップロードすると、分析結果を表示します。")
        return

    try:
        df = load_data(uploaded_file)
    except ValueError as error:
        st.error(str(error))
        st.info("別のCSVファイルをアップロードしてください。")
        return

    source_label = f"CSV: {uploaded_file.name}"
    st.markdown(f'<div class="dashboard-sub">{source_label}を読み込み、直感的に比較・分析できます。</div>', unsafe_allow_html=True)
    render_section_navigation()

    filtered_df, _ = render_sidebar(df)
    render_metric_cards(filtered_df)
    render_wellbeing_analysis(filtered_df)
    render_sensory_analysis(filtered_df)
    render_charts(filtered_df)
    render_trend(filtered_df)
    render_pink_analysis(filtered_df)
    render_comment_section(filtered_df)
    render_filtered_details(filtered_df)


if __name__ == "__main__":
    main()
