from pathlib import Path
import re
from io import BytesIO

import pandas as pd
from components.sensory import DEFAULTS
from components.wellbeing import current_pentagon_scores, current_pentagon_types


COURSE_COL = "選択コース"
COLOR_COL = "好きな色"
GENDER_COL = "性別"
AGE_COL = "年齢"

_COLOR_NAMES = [
    "ローズピンク", "ピンク", "赤", "オールドローズ", "ワイン", "オレンジ",
    "ライトオレンジ", "ベージュ", "黄土色", "茶色", "黄色", "クリーム",
    "黄緑", "カーキ", "緑", "ライトグリーン", "スモーキーグリーン",
    "ダークグリーン", "青", "スカイブルー", "ネイビーブルー", "パープル",
    "ライラック", "ふじ色", "白", "グレー", "黒", "ゴールド", "シルバー",
]


def _find_column(df: pd.DataFrame, prefix: str) -> str | None:
    return next((str(column) for column in df.columns if str(column).startswith(prefix)), None)


def _normalize_color(value: object) -> str:
    text = str(value).strip()
    match = re.match(r"^(\d+)[.．]?\s*", text)
    if match:
        number = int(match.group(1))
        if 1 <= number <= len(_COLOR_NAMES):
            return _COLOR_NAMES[number - 1]
    return text


def _normalize_dashboard_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    aliases = {
        "年代": "年齢", "年齢層": "年齢", "都道府県": "居住地",
        "地域": "居住地", "世帯構成": "同居家族", "家族構成": "同居家族",
        "年収": "世帯年収", "幸福度": "幸福度スコア",
        "幸福度平均値": "幸福度平均", "現在の幸福度": "現在の幸福状態",
        "自由記述": "コメント", "好きな色（3つ）": COLOR_COL,
        "幸福度項目（5軸）": "幸福度項目",
    }
    rename_map = {
        source: target for source, target in aliases.items()
        if source in df.columns and target not in df.columns
    }
    df = df.rename(columns=rename_map).copy()
    prefix_aliases = {
        "◆性別": GENDER_COL, "◆年齢": "年齢", "◆居住地": "居住地",
        "◆同居家族": "同居家族", "◆職業": "職業",
        "◆あなたの世帯年収": "世帯年収",
        "◆あなたにとって「幸せ」に必要": "幸せに必要なこと",
        "◆好きな色を3つ選んでください": COLOR_COL,
        "インテリアスタイル｜選択肢5つ": "好きなインテリアスタイル",
        "好きなインテリアスタイル｜選択肢5つ": "好きなインテリアスタイル",
        "◆あなたが好きなインテリアスタイル": "好きなインテリアスタイル",
        "◆あなたにとって理想の暮らし方": "理想の暮らし方",
        "1つ以上、5つまで選んでください。": "理想の暮らし方",
        "あなたが好きなファッションスタイルを選んでください。（1つだけ選択）": "好きなファッションスタイル",
        "◆あなたが好きなファッションスタイル": "好きなファッションスタイル",
        "2024年特別設問｜これらピンクの中に「しあわせ」を感じる": "幸せを感じるピンク",
        "◆あなたが今後やりたいこと": "今後やりたいこと",
        "◆あなたの現在の状況": "現在の幸福状態",
    }
    for prefix, target in prefix_aliases.items():
        source = next((column for column in df.columns if column.startswith(prefix)), None)
        if source and target not in df.columns:
            df[target] = df[source]
    if "世帯年収" not in df.columns:
        income_column = next((column for column in df.columns if "年収" in column), None)
        if income_column:
            df["世帯年収"] = df[income_column]
    if "年度" not in df.columns and "タイムスタンプ" in df.columns:
        df["年度"] = pd.to_datetime(df["タイムスタンプ"], errors="coerce").dt.year

    calculated_scores = current_pentagon_scores(df)
    for column in calculated_scores:
        df[column] = calculated_scores[column]
    if "年度" in df.columns:
        numeric_year = pd.to_numeric(df["年度"], errors="coerce")
        df["年度"] = numeric_year.where(numeric_year.notna(), df["年度"])
    return df


def _read_uploaded_csv(uploaded_file: object) -> pd.DataFrame:
    raw = uploaded_file.getvalue()
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "cp932", "shift_jis", "utf-16"):
        try:
            return pd.read_csv(BytesIO(raw), encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError) as error:
            last_error = error
    raise ValueError(f"CSVを読み込めませんでした: {last_error}")


def load_data(path: str | Path | object | None = None) -> pd.DataFrame:
    """Load the survey CSV and expose the canonical columns used by analyses."""
    if path is not None and hasattr(path, "getvalue"):
        df = _read_uploaded_csv(path)
    else:
        csv_path = (
            Path(path)
            if path is not None
            else Path(__file__).resolve().parents[1]
            / "data"
            / "U.Ge「幸せ」アンケート集計データ_version27_.csv"
        )
        df = pd.read_csv(csv_path, encoding="utf-8")
    df = _normalize_dashboard_columns(df)

    gender_source = _find_column(df, "◆性別") or GENDER_COL
    age_source = _find_column(df, "◆年齢") or "年齢"
    color_source = _find_column(df, "◆好きな色を3つ選んでください") or COLOR_COL
    lifestyle_columns = [
        column for column in df.columns
        if "理想の暮らし" in str(column)
        or str(column).startswith("1つ以上、5つまで選んでください。")
    ]
    if gender_source not in df.columns or age_source not in df.columns or color_source not in df.columns:
        missing = [
            name for name, source in [
                (GENDER_COL, gender_source),
                (AGE_COL, age_source),
                (COLOR_COL, color_source),
            ]
            if source is None
        ]
        raise ValueError("共通データ列が見つかりません：" + "、".join(missing))

    df = df.copy()
    df[GENDER_COL] = df[gender_source].fillna("").astype("string").str.strip()
    df[AGE_COL] = df[age_source].fillna("").astype("string").str.strip()
    df[COLOR_COL] = (
        df[color_source]
        .fillna("")
        .astype("string")
        .str.split(r"[,|\n]", regex=True)
        .map(lambda values: ",".join(_normalize_color(value) for value in values if str(value).strip()))
    )

    iot_mask = pd.Series(False, index=df.index)
    for column in lifestyle_columns:
        answers = df[column].astype("string")
        iot_mask |= (
            answers.str.contains("スマートホーム", regex=False, na=False)
            | answers.str.contains(r"(?:^|[,|\n])\s*18\s*(?:$|[,|\n])", regex=True, na=False)
        )
    df[COURSE_COL] = iot_mask.map({True: "IoT", False: "その他"})
    return df


def filter_iot(df: pd.DataFrame) -> pd.DataFrame:
    return df[df[COURSE_COL].astype("string").str.contains("IoT", case=False, na=False)]


def filter_others(df: pd.DataFrame) -> pd.DataFrame:
    return df[~df[COURSE_COL].astype("string").str.contains("IoT", case=False, na=False)]


def count_colors(df: pd.DataFrame) -> pd.Series:
    colors = (
        df[COLOR_COL]
        .fillna("")
        .astype("string")
        .str.split(r"[,|\n]", regex=True)
        .explode()
        .str.strip()
    )
    return colors[colors.ne("")].value_counts().sort_index()
