import pandas as pd

# 共通の列名
COURSE_COL = "選択コース"
COLOR_COL = "好きな色"
GENDER_COL = "性別"
AGE_COL = "年代"

def load_data(path="./data/U.Ge[幸せ]アンケート集計データ_version27_.csv"):
    df = pd.read_csv(path, encoding="utf-8")

    # 前処理：空白除去・欠損補完
    df[COURSE_COL] = df[COURSE_COL].fillna("").str.strip()
    df[COLOR_COL] = df[COLOR_COL].fillna("").str.strip()
    df[GENDER_COL] = df[GENDER_COL].fillna("").str.strip()
    df[AGE_COL] = df[AGE_COL].fillna("").str.strip()

    return df


def filter_iot(df):
    """IoT選択者だけ抽出"""
    return df[df[COURSE_COL].str.contains("IoT", case=False, na=False)]


def filter_others(df):
    """IoT以外を抽出"""
    return df[~df[COURSE_COL].str.contains("IoT", case=False, na=False)]


def count_colors(df):
    """色の出現数を返す"""
    return df[COLOR_COL].value_counts().sort_index()
