from __future__ import annotations

import pandas as pd


def link_matrix(frame: pd.DataFrame, *, link_family: str, row_col: str, col_col: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=[row_col, col_col, "count"])
    subset = frame[frame["link_family"] == link_family].copy()
    if subset.empty:
        return pd.DataFrame(columns=[row_col, col_col, "count"])
    return subset.groupby([row_col, col_col]).size().reset_index(name="count").sort_values("count", ascending=False)
