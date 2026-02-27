from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analytics import ema, ema_alpha_from_days, sma


def test_sma_basic() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = sma(s, 2)
    assert out.round(3).tolist() == [1.0, 1.5, 2.5, 3.5]


def test_ema_basic() -> None:
    s = pd.Series([10.0, 10.0, 20.0])
    out = ema(s, 2)
    # alpha = 2/(2+1)=0.666..., third value = 0.666*20 + 0.333*10 = 16.666...
    assert round(float(out.iloc[2]), 3) == 16.667


def test_ema_alpha_from_days() -> None:
    assert round(ema_alpha_from_days(14), 6) == round(2.0 / 15.0, 6)


def test_sma_invalid_window() -> None:
    s = pd.Series([1.0])
    try:
        sma(s, 0)
    except ValueError:
        return
    assert False, "Expected ValueError"
