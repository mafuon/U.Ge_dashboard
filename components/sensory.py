import html
import re
from collections.abc import Iterable

import pandas as pd
import streamlit as st

try:
    import altair as alt
except Exception:
    alt = None


COLORS = {
    "pink": "#f29aa0",
    "blue": "#86aeea",
    "orange": "#e9b46a",
    "green": "#77b99a",
    "ink": "#17202a",
}

CHART_PADDING = {"left": 16, "right": 28, "top": 14, "bottom": 18}

COLOR_PALETTE = {
    "赤": "#e76f51", "橙": "#f4a261", "黄": "#e9c46a", "緑": "#72b98b",
    "青": "#4f86c6", "紫": "#9b72cf", "ピンク": "#e9a0b5", "白": "#f8f8f5",
    "黒": "#252525", "グレー": "#9aa0a6", "ベージュ": "#d9c2a3", "ブラウン": "#8b6650",
    "ネイビー": "#203a5f", "水色": "#9bd7e5", "アイボリー": "#f4efdf", "ゴールド": "#cda85c",
}

COLOR_SWATCHES = [
    {"id": 1, "name": "ローズピンク", "english": "Rose Pink", "hex": "#E75480"},
    {"id": 2, "name": "ピンク", "english": "Pink", "hex": "#FADADD"},
    {"id": 3, "name": "赤", "english": "Red", "hex": "#FF0000"},
    {"id": 4, "name": "オールドローズ", "english": "Old Rose", "hex": "#C0504D"},
    {"id": 5, "name": "ワイン", "english": "Wine", "hex": "#800040"},
    {"id": 6, "name": "オレンジ", "english": "Orange", "hex": "#FF7F00"},
    {"id": 7, "name": "ライトオレンジ", "english": "Light Orange", "hex": "#FAD6A5"},
    {"id": 8, "name": "ベージュ", "english": "Beige", "hex": "#EED5B7"},
    {"id": 9, "name": "黄土色", "english": "Ochre", "hex": "#DDAA00"},
    {"id": 10, "name": "茶色", "english": "Brown", "hex": "#8B4513"},
    {"id": 11, "name": "黄色", "english": "Yellow", "hex": "#FFFF00"},
    {"id": 12, "name": "クリーム", "english": "Cream", "hex": "#FFFDD0"},
    {"id": 13, "name": "黄緑", "english": "Yellow-Green", "hex": "#9ACD32"},
    {"id": 14, "name": "カーキ", "english": "Khaki", "hex": "#BDB76B"},
    {"id": 15, "name": "緑", "english": "Green", "hex": "#008000"},
    {"id": 16, "name": "ライトグリーン", "english": "Light Green", "hex": "#90EE90"},
    {"id": 17, "name": "スモーキーグリーン", "english": "Smoky Green", "hex": "#A8C3A0"},
    {"id": 18, "name": "ダークグリーン", "english": "Dark Green", "hex": "#013220"},
    {"id": 19, "name": "青", "english": "Blue", "hex": "#0073CF"},
    {"id": 20, "name": "スカイブルー", "english": "Sky Blue", "hex": "#87CEEB"},
    {"id": 21, "name": "ネイビーブルー", "english": "Navy Blue", "hex": "#000080"},
    {"id": 22, "name": "パープル", "english": "Purple", "hex": "#800080"},
    {"id": 23, "name": "ライラック", "english": "Lilac", "hex": "#C8A2C8"},
    {"id": 24, "name": "ふじ色", "english": "Wisteria", "hex": "#BDB2FF"},
    {"id": 25, "name": "白", "english": "White", "hex": "#FFFFFF"},
    {"id": 26, "name": "グレー", "english": "Gray", "hex": "#BEBEBE"},
    {"id": 27, "name": "黒", "english": "Black", "hex": "#000000"},
    {"id": 28, "name": "ゴールド", "english": "Gold", "hex": "#FFD700"},
    {"id": 29, "name": "シルバー", "english": "Silver", "hex": "#C0C0C0"},
]

CHOICE_PALETTE = [
    "#4c78a8", "#f58518", "#e45756", "#72b7b2", "#54a24b", "#eeca3b",
    "#b279a2", "#ff9da6", "#9d755d", "#bab0ac", "#5f9ed1", "#edc948",
    "#8cd17d", "#b6992d", "#499894", "#d37295", "#79706e", "#86bcb6",
    "#fabfd2", "#d4a6c8", "#7f8c8d", "#a0cbe8", "#ffbe7d", "#ff9d9a",
    "#b5bd61", "#59a14f", "#af7aa1", "#76b7b2", "#e15759",
]

DEFAULTS = {
    "幸せに必要なこと": ["悩みや不満がないこと", "目標が達成されること", "季節の変化を感じられること", "周囲や社会から自分が認められること", "身体が元気であること", "生活によい変化や刺激があること", "何かに夢中・没頭できること", "自由に意思決定ができること", "人の役に立つこと", "金銭的に充実、安定していること", "自分らしく、自信を持った行動ができること", "自分が成長出来ていると感じられること", "ゆとりや自分の時間があること", "信頼する人、心を許せる人がいること", "犯罪や災害の不安がないこと", "好きなことができること", "勉強の機会や場があること", "素の自分で居られること", "多くの出会いがあること", "デジタル化が進み便利になること"],
    "好きな色": [color["name"] for color in COLOR_SWATCHES],
    "好きなインテリアスタイル": ["自然体で暮らす", "自分らしさを大切にし、趣味を楽しむ", "エレガントなスタイル", "味わいのある空間をアレンジして暮らす", "心地良さを追求しシンプルに暮らす"],
    "理想の暮らし方": ["四季を楽しむ暮らし", "お風呂を楽しむ暮らし", "テラスバルコニーのある暮らし", "ワークスペースのある暮らし", "料理を楽しむ暮らし", "家飲みを楽しむ暮らし", "カフェにいるような暮らし", "ペットと楽しむ暮らし", "グリーンを楽しむ暮らし", "本に囲まれた暮らし", "ホームシアターのある暮らし", "ヨガや運動を楽しむ暮らし", "季節の行事を楽しむ暮らし", "バーベキューを楽しむ暮らし", "子供、孫と楽しむ暮らし", "音楽を楽しむ暮らし", "暖炉を楽しむ暮らし", "スマートホーム（IoT）で効率的な暮らし", "アートを楽しむ暮らし", "ガレージハウスのある暮らし", "ホームパーティーを楽しむ暮らし", "DIYを楽しむ暮らし", "ホビールームのある暮らし", "香りを楽しむ暮らし", "VR・ゲームを楽しむ暮らし", "場所にとらわれない暮らし（多拠点生活など）", "睡眠を大切にする暮らし", "その他", "この中にはない"],
    "好きなファッションスタイル": ["コンテンポラリー / ベーシック", "コズミック / モダン", "ダンディ / トラディショナル", "ファンクショナル / シビライズド", "ロマンティック / ゴージャス", "メカニック / シンプル", "ナチュラル / エスニック", "フェミニン / エレガント", "スポーティ / セクシー"],
    "最も高級だと感じる体験": ["一流ブランドや職人のこだわりが詰まった「本物」を身につけているとき", "自分のスキルアップや最新の「体験」にお金を使っているとき", "自然に囲まれた場所でスマホをオフにして「何もしない時間」を過ごしているとき", "信頼できる仲間や家族と、少し贅沢な空間でおいしい食事を囲むとき", "日々の「安心・安全・快適な空間」が整っているとき"],
    "プレミアム購入目的": ["自分のモチベーションを高め、自信を持ちたいから", "自分の知識や経験、可能性を広げたいから", "心身をリフレッシュし、ストレスのない健やかな状態を保ちたいから", "周囲の人や大切なパートナーに、感謝や敬意を伝えるため", "長く使えて地球環境にも優しく、結果的に生活の無駄を省けるから", "他の人とは違う、自分だけの個性やこだわりを表現したいから", "ステータス（社会的地位）の証明や、周囲からの評価のため"],
    "Up-Gradeジャンル": ["ファッション・身の回りの小物", "美容・スキンケア・セルフケア", "健康維持・ウェルネス", "自宅のインテリア・家電", "食", "旅・宿泊", "学び・エンタメ", "ガジェット・デジタル", "特にない / 奮発した買い物はしていない"],
    "高級感のあるインテリアイメージ": ["先進的な高級感", "上品な高級感", "風格のある高級感", "豪華な高級感", "シンプルな高級感", "温もりのある高級感"],
    "今後やりたいこと": ["読書", "芸術鑑賞（音楽・アートなど）", "ゲーム", "映像鑑賞（映画・ネットフリックスなど）", "スポーツ・トレーニング", "美容・セルフケア・ウェルネス", "車・バイク", "アウトドア", "社会活動", "旅行", "散歩", "筋トレ", "釣り", "写真", "音楽演奏", "料理", "創作（文筆・絵画などアナログな創作活動）", "勉強", "仕事", "投資・資産形成（NISA等）", "グルメ・お酒", "ショッピング（オンラインも含む）", "ペット", "パソコン・インターネット閲覧", "デジタルによる発信・創作", "推し活・ファン活動", "今後やりたいことはない", "その他"],
}


def _values(df: pd.DataFrame, column: str, limit: int | None = None) -> pd.DataFrame:
    if column in df.columns:
        respondent_count = df[column].notna().sum()
        series = df[column].dropna().astype(str).str.split(r"[,|\n]", regex=True).explode().str.strip()
        series = series[series != ""]
        choices = DEFAULTS.get(column)
        if choices:
            def canonicalize(value: str) -> str:
                number = re.match(r"^(\d+)[.．]?\s*", value)
                if number and 1 <= int(number.group(1)) <= len(choices):
                    return choices[int(number.group(1)) - 1]
                return value

            series = series.map(canonicalize)
            counts = series.value_counts().reindex(choices, fill_value=0).rename_axis("項目").reset_index(name="回答数")
        else:
            counts = series.value_counts().rename_axis("項目").reset_index(name="回答数")
    else:
        fallback = DEFAULTS.get(column, ["回答なし"])
        counts = pd.DataFrame({"項目": fallback, "回答数": [max(1, len(fallback) - i) for i in range(len(fallback))]})
        respondent_count = counts["回答数"].sum()
    counts["回答率"] = counts["回答数"].div(respondent_count).mul(100) if respondent_count else 0
    if limit:
        counts = counts.head(limit)
    return counts


def _bar_chart(
    data: pd.DataFrame,
    color: str = COLORS["pink"],
    height: int = 220,
    color_map: dict[str, str] | None = None,
    max_percent: int = 100,
):
    if alt is None:
        st.bar_chart(data.set_index("項目")["回答率"], height=height)
        return
    chart = alt.Chart(data).mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5).encode(
        x=alt.X("回答率:Q", title="回答者比率（%）", scale=alt.Scale(domain=[0, max_percent]), axis=alt.Axis(format=".0f")),
        y=alt.Y("項目:N", sort="-x", title=None, axis=alt.Axis(labelLimit=0, minExtent=260)),
        color=alt.Color(
            "項目:N",
            scale=alt.Scale(domain=list(color_map), range=list(color_map.values())),
            legend=None,
        ) if color_map else alt.value(color),
        tooltip=["項目:N", "回答率:Q", "回答数:Q"],
    ).properties(height=height, padding=CHART_PADDING)
    st.altair_chart(chart, use_container_width=True)


def _choice_color_map(column: str, items: Iterable[str]) -> dict[str, str]:
    choices = DEFAULTS.get(column, [])
    ordered_items = list(dict.fromkeys([*choices, *items]))
    return {
        item: CHOICE_PALETTE[index % len(CHOICE_PALETTE)]
        for index, item in enumerate(ordered_items)
    }


def _yearly_color_composition(df: pd.DataFrame, color_map: dict[str, str]):
    if alt is None or "年度" not in df.columns or "好きな色" not in df.columns:
        return

    choices = DEFAULTS["好きな色"]
    color_values = df[["年度", "好きな色"]].dropna().copy()
    color_values["色"] = color_values["好きな色"].astype(str).str.split(r"[,|\n]", regex=True)
    color_values = color_values.explode("色")
    color_values["色"] = color_values["色"].str.strip()
    color_values = color_values[color_values["色"] != ""]

    def canonicalize(value: str) -> str:
        number = re.match(r"^(\d+)[.．]?\s*", value)
        if number and 1 <= int(number.group(1)) <= len(choices):
            return choices[int(number.group(1)) - 1]
        return value

    color_values["色"] = color_values["色"].map(canonicalize)
    color_values = color_values[color_values["色"].isin(choices)]
    composition = color_values.groupby(["年度", "色"], as_index=False).size().rename(columns={"size": "選択数"})
    composition["構成比"] = composition.groupby("年度")["選択数"].transform(lambda values: values.div(values.sum()).mul(100))
    years = sorted(composition["年度"].unique())

    chart = alt.Chart(composition).mark_bar(stroke=None).encode(
        x=alt.X("構成比:Q", stack="normalize", title="構成比（%）", axis=alt.Axis(format=".0%", grid=False)),
        y=alt.Y("年度:N", sort=years, scale=alt.Scale(reverse=True), title="年度", axis=alt.Axis(grid=False)),
        color=alt.Color("色:N", scale=alt.Scale(domain=list(color_map), range=list(color_map.values())), legend=None),
        tooltip=["年度:N", "色:N", "選択数:Q", alt.Tooltip("構成比:Q", format=".1f")],
    ).properties(height=max(180, len(years) * 62), padding=CHART_PADDING)
    st.altair_chart(chart, use_container_width=True)


def _yearly_choice_composition(df: pd.DataFrame, column: str, color_map: dict[str, str]):
    if alt is None or "年度" not in df.columns or column not in df.columns:
        return

    choices = DEFAULTS.get(column)
    values = df[["年度", column]].dropna().copy()
    values["項目"] = values[column].astype(str).str.split(r"[,|\n]", regex=True)
    values = values.explode("項目")
    values["項目"] = values["項目"].str.strip()
    values = values[values["項目"] != ""]

    if choices:
        def canonicalize(value: str) -> str:
            number = re.match(r"^(\d+)[.．]?\s*", value)
            if number and 1 <= int(number.group(1)) <= len(choices):
                return choices[int(number.group(1)) - 1]
            return value

        values["項目"] = values["項目"].map(canonicalize)
        values = values[values["項目"].isin(choices)]

    composition = values.groupby(["年度", "項目"], as_index=False).size().rename(columns={"size": "選択数"})
    if composition.empty:
        return
    composition["構成比"] = composition.groupby("年度")["選択数"].transform(lambda counts: counts.div(counts.sum()).mul(100))
    years = sorted(composition["年度"].unique())

    chart = alt.Chart(composition).mark_bar(stroke=None).encode(
        x=alt.X("構成比:Q", stack="normalize", title="構成比（%）", axis=alt.Axis(format=".0%", grid=False)),
        y=alt.Y("年度:N", sort=years, scale=alt.Scale(reverse=True), title="年度", axis=alt.Axis(grid=False)),
        color=alt.Color("項目:N", scale=alt.Scale(domain=list(color_map), range=list(color_map.values())), legend=None),
        tooltip=["年度:N", "項目:N", "選択数:Q", alt.Tooltip("構成比:Q", format=".1f")],
    ).properties(height=max(180, len(years) * 62), padding=CHART_PADDING)
    st.altair_chart(chart, use_container_width=True)


def _yearly_composition_heading():
    st.markdown("#### 年度別の選択構成比")
    st.caption("各年度における、選択された回答全体の構成比です。複数回答の設問では、年度ごとに合計100%になります。")


def _heatmap_chart(data: pd.DataFrame, color: str = COLORS["pink"]):
    if alt is None:
        st.dataframe(data, hide_index=True, use_container_width=True)
        return
    chart = alt.Chart(data.head(12)).mark_rect(cornerRadius=5).encode(
        x=alt.X("項目:N", sort="-y", axis=alt.Axis(labelAngle=-35, title=None)),
        y=alt.Y("回答数:Q", title="選択数"),
        color=alt.Color("回答数:Q", scale=alt.Scale(range=["#f8f8f5", color]), legend=None),
        tooltip=["項目:N", "回答数:Q"],
    ).properties(height=220, padding=CHART_PADDING)
    st.altair_chart(chart, use_container_width=True)


def _donut_chart(data: pd.DataFrame, color: str = COLORS["orange"]):
    if alt is None:
        st.dataframe(data, hide_index=True, use_container_width=True)
        return
    chart = alt.Chart(data.head(8)).mark_arc(innerRadius=42).encode(
        theta=alt.Theta("回答数:Q"),
        color=alt.Color("項目:N", scale=alt.Scale(scheme="pastel1"), legend=None),
        tooltip=["項目:N", "回答数:Q"],
    ).properties(height=220, padding=CHART_PADDING)
    st.altair_chart(chart, use_container_width=True)


def _cards(items: Iterable[str], selected: set[str], kind: str = "default", limit: int | None = None):
    items = list(items)[:limit] if limit else list(items)
    columns = st.columns(min(5, max(1, len(items))))
    for index, item in enumerate(items):
        active = item in selected
        accent = COLORS["pink"] if active else "#ffffff"
        with columns[index % len(columns)]:
            st.markdown(
                f'<div class="sensory-card {"is-active" if active else ""}" style="--accent:{accent}"><span>{html.escape(item)}</span></div>',
                unsafe_allow_html=True,
            )


def _selected_values(df: pd.DataFrame, column: str, data: pd.DataFrame) -> set[str]:
    if column not in df.columns or df.empty:
        return set(data.head(3)["項目"])
    values = df[column].dropna().astype(str).str.split(r"[,|\n]", regex=True).explode().str.strip()
    return set(values[values != ""].unique())


def _section_title(number: int, title: str, note: str = ""):
    if number > 1:
        st.markdown('<div class="sensory-divider"></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sensory-kicker">{number:02d}</div><h3 class="sensory-title">{html.escape(title)}</h3><div class="sensory-note">{html.escape(note)}</div>', unsafe_allow_html=True)


def render_sensory_analysis(df: pd.DataFrame):
    st.markdown('<div id="sensory" class="section-anchor"></div><div class="sensory-shell"><div class="section-header section-orange">感性分析</div><div class="sensory-intro">回答者の選択傾向から、暮らしとプレミアムの価値観を読み解きます。</div></div>', unsafe_allow_html=True)

    _section_title(3, "好きな色", "好きな色3つ")
    color_data = _values(df, "好きな色", 29)
    color_map = {color["name"]: color["hex"] for color in COLOR_SWATCHES}
    _bar_chart(color_data, COLORS["pink"], height=720, color_map=color_map, max_percent=50)
    st.markdown("#### 年度別の色選択構成比")
    st.caption("各年度における、選択された色全体の構成比です。複数回答のため、年度ごとに合計100%になります。")
    _yearly_color_composition(df, color_map)

    sections = [
        (4, "好きなインテリアスタイル", "好きなインテリアスタイル", "5つのスタイルから見える空間の好み", COLORS["blue"]),
        (5, "理想の暮らし方", "理想の暮らし方", "最大5つまで選ばれた、暮らしの理想像", COLORS["orange"]),
        (6, "好きなファッションスタイル", "好きなファッションスタイル", "装いに表れる個性とムード", COLORS["orange"]),
        (7, "最も高級だと感じる体験", "最も高級だと感じる体験", "時間・空間・体験への価値観", COLORS["green"]),
        (8, "プレミアム商品を買う目的", "プレミアム購入目的", "通常より少し高価な商品・サービスを購入・利用する主な目的", COLORS["pink"]),
        (9, "Up-Gradeのために奮発したジャンル", "Up-Gradeジャンル", "暮らしのどこをアップグレードしたいか", COLORS["pink"]),
        (10, "高級感のあるインテリアイメージ", "高級感のあるインテリアイメージ", "空間の上質さをつくる要素", COLORS["blue"]),
        (11, "今後やりたいこと", "今後やりたいこと", "これから取り組みたいこと・楽しみたいこと", COLORS["green"]),
    ]
    for number, title, column, note, color in sections:
        _section_title(number, title, note)
        data = _values(df, column)
        color_map = _choice_color_map(column, data["項目"])
        if number == 5:
            _bar_chart(data, color, height=max(420, len(data) * 28), color_map=color_map, max_percent=50)
            _yearly_composition_heading()
            _yearly_choice_composition(df, column, color_map)
            continue
        if number == 8:
            _bar_chart(data, color, height=max(260, len(data) * 42), color_map=color_map, max_percent=50)
            _yearly_composition_heading()
            _yearly_choice_composition(df, column, color_map)
            continue
        chart_height = max(400, len(data) * 28) if number == 11 else max(220, len(data) * 34)
        _bar_chart(data, color, height=chart_height, color_map=color_map, max_percent=50)
        _yearly_composition_heading()
        _yearly_choice_composition(df, column, color_map)
