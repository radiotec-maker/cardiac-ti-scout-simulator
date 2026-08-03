"""左室短軸模式図とTI選択表示のための純粋な可視化関数。"""

from __future__ import annotations

import math
from numbers import Real
import re

import config
from model import generate_ti_signal_curve


def _finite_number(value: float, label: str) -> float:
    """値を有限の実数として検証する。"""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label}は数値で入力してください。")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label}は有限の数値で入力してください。")
    return number


def validate_illustration_ti(ti_ms: float) -> float:
    """イラスト表示TIが0～700 msの範囲内であることを検証する。"""

    ti = _finite_number(ti_ms, "イラスト表示TI")
    if not config.MIN_ILLUSTRATION_TI_MS <= ti <= config.MAX_ILLUSTRATION_TI_MS:
        raise ValueError("イラスト表示TIは0～700 msの範囲で入力してください。")
    return ti


def shift_illustration_ti(ti_ms: float, direction: int) -> float:
    """イラスト表示TIを10 ms増減し、0～700 msの範囲内へ制限する。"""

    current_ti = validate_illustration_ti(ti_ms)
    if isinstance(direction, bool) or direction not in (-1, 1):
        raise ValueError("TIの変更方向は-1または1で指定してください。")
    shifted_ti = current_ti + direction * config.ILLUSTRATION_TI_STEP_MS
    return min(
        max(shifted_ti, config.MIN_ILLUSTRATION_TI_MS),
        config.MAX_ILLUSTRATION_TI_MS,
    )


def signal_percent_to_rgb(
    signal_percent: float,
    gamma: float = 1.0,
) -> tuple[int, int, int]:
    """0～100%の相対信号をガンマ補正付き8 bitグレースケールへ変換する。"""

    signal = _finite_number(signal_percent, "正常心筋相対信号")
    if not 0.0 <= signal <= 100.0:
        raise ValueError("正常心筋相対信号は0～100%の範囲で入力してください。")
    gamma_value = _finite_number(gamma, "グレースケールガンマ")
    if gamma_value <= 0.0:
        raise ValueError("グレースケールガンマは0より大きい値を入力してください。")
    gray = round(255.0 * (signal / 100.0) ** gamma_value)
    return gray, gray, gray


def calculate_signal_at_ti(null_ti_ms: float, ti_ms: float) -> float:
    """既存モデルから選択TIにおける正規化Magnitude信号（%）を取得する。"""

    null_ti = _finite_number(null_ti_ms, "推定null TI")
    if null_ti <= 0.0:
        raise ValueError("推定null TIは0より大きい値を入力してください。")
    ti = validate_illustration_ti(ti_ms)

    # 既存の信号曲線関数をそのまま使い、選択TIの1点を取り出す。
    if ti == config.MIN_ILLUSTRATION_TI_MS:
        ti_values, signal_values = generate_ti_signal_curve(
            null_ti, ti, ti + config.DEFAULT_TI_STEP_MS, config.DEFAULT_TI_STEP_MS
        )
        return float(signal_values[0])
    ti_values, signal_values = generate_ti_signal_curve(null_ti, 0.0, ti, ti)
    if not math.isclose(float(ti_values[-1]), ti):
        raise ValueError("選択したTIの信号値を取得できませんでした。")
    return float(signal_values[-1])


def _validate_pattern_id(pattern_id: str) -> str:
    """SVG pattern IDを安全な英数字・ハイフン・下線に制限する。"""

    if not isinstance(pattern_id, str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_-]*", pattern_id
    ):
        raise ValueError("SVG pattern IDは英数字、ハイフン、下線で指定してください。")
    return pattern_id


def generate_lv_short_axis_svg(
    signal_percent: float,
    blood_signal_percent: float,
    pattern_id: str = "lv-cavity-hatch",
) -> str:
    """心筋と血液の信号に連動する簡略短軸SVGを返す。"""

    signal = _finite_number(signal_percent, "正常心筋相対信号")
    red, green, blue = signal_percent_to_rgb(
        signal, config.MYOCARDIAL_GRAYSCALE_GAMMA
    )
    myocardial_fill = f"rgb({red},{green},{blue})"
    blood_signal = _finite_number(blood_signal_percent, "血液相対信号")
    blood_red, blood_green, blood_blue = signal_percent_to_rgb(blood_signal)
    blood_fill = f"rgb({blood_red},{blood_green},{blood_blue})"
    _validate_pattern_id(pattern_id)
    description = (
        f"正常心筋相対信号{signal:.1f}パーセント、血液相対信号"
        f"{blood_signal:.1f}パーセントの左室・右室短軸模式図"
    )
    return f"""<svg width="320" height="230" viewBox="0 0 360 240" role="img" aria-label="{description}" style="display:block;max-width:100%;height:auto;margin:0 auto" xmlns="http://www.w3.org/2000/svg">
  <title>{description}</title>
  <desc>右側の円環は正常左室心筋、中央の楕円と左側の三日月形は同じ血液信号で表示した左室・右室内腔です。</desc>
  <path id="right-ventricle" d="M 196 40 C 105 32 45 78 55 143 C 63 198 123 218 190 185 C 166 157 161 83 196 40 Z" fill="{blood_fill}" stroke="rgb(85,85,85)" stroke-width="3" />
  <ellipse id="left-ventricular-myocardium" cx="238" cy="120" rx="92" ry="94" fill="{myocardial_fill}" stroke="rgb(70,70,70)" stroke-width="4" />
  <ellipse id="left-ventricular-cavity" cx="238" cy="120" rx="50" ry="53" fill="{blood_fill}" stroke="rgb(70,70,70)" stroke-width="3" />
</svg>"""
