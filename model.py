"""心臓MRI TI scoutシミュレータの計算モデル。"""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Real

import numpy as np
from numpy.typing import NDArray

import config


@dataclass(frozen=True)
class DoseResult:
    """2回投与の体積、体重当たり投与量、注入時間を保持する。"""

    first_volume_ml: float
    second_volume_ml: float
    total_volume_ml: float
    first_dose_mmol_per_kg: float
    second_dose_mmol_per_kg: float
    total_dose_mmol_per_kg: float
    target_dose_ratio_percent: float
    first_injection_duration_s: float
    second_injection_duration_s: float


@dataclass(frozen=True)
class ConcentrationResult:
    """各投与由来および総心筋内見かけ濃度（mM）を保持する。"""

    first_concentration_mmol_per_l: float
    second_concentration_mmol_per_l: float
    total_concentration_mmol_per_l: float
    a_pk: float
    washout_rate_per_min: float
    second_injection_time_min: float


def _finite_number(value: float, label: str) -> float:
    """値を有限の実数として検証して返す。"""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label}は数値で入力してください。")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label}は有限の数値で入力してください。")
    return number


def _positive_number(value: float, label: str) -> float:
    """値を正の有限実数として検証して返す。"""

    number = _finite_number(value, label)
    if number <= 0.0:
        raise ValueError(f"{label}は0より大きい値を入力してください。")
    return number


def validate_weight(weight_kg: float) -> float:
    """体重が30～100 kgの入力範囲内であることを検証する。"""

    weight = _finite_number(weight_kg, "体重")
    if not config.MIN_WEIGHT_KG <= weight <= config.MAX_WEIGHT_KG:
        raise ValueError("体重は30～100 kgの範囲で入力してください。")
    return weight


def validate_native_t1(native_t1_ms: float) -> float:
    """正常心筋native T1が1000～1600 msの範囲内か検証する。"""

    native_t1 = _finite_number(native_t1_ms, "native T1")
    if not config.MIN_NATIVE_T1_MS <= native_t1 <= config.MAX_NATIVE_T1_MS:
        raise ValueError("native T1は1000～1600 msの範囲で入力してください。")
    return native_t1


def validate_scout_time(time_min: float) -> float:
    """TI scout撮像時刻が造影後2～15分の範囲内か検証する。"""

    time = _finite_number(time_min, "TI scout撮像時刻")
    if not config.MIN_SCOUT_TIME_MIN <= time <= config.MAX_SCOUT_TIME_MIN:
        raise ValueError("TI scout撮像時刻は2.0～15.0分の範囲で入力してください。")
    return time


def calculate_injection_duration(
    volume_ml: float,
    injection_rate_ml_s: float = config.CONTRAST_INJECTION_RATE_ML_S,
) -> float:
    """注入体積（mL）を注入速度（mL/s）で除し、注入時間（s）を返す。"""

    volume = _finite_number(volume_ml, "注入体積")
    rate = _positive_number(injection_rate_ml_s, "注入速度")
    if volume < 0.0:
        raise ValueError("注入体積は0以上で入力してください。")
    return volume / rate


def calculate_dose(weight_kg: float) -> DoseResult:
    """体重から2回分割投与量と10 mL上限、各注入時間を計算する。"""

    weight = validate_weight(weight_kg)

    # 1.0 mmol/mLなので、mmolとmLの数値は等しい。
    first_volume = config.FIRST_DOSE_MMOL_PER_KG * weight
    available_volume = config.MAX_TOTAL_VOLUME_ML - first_volume
    second_volume = min(
        config.SECOND_TARGET_DOSE_MMOL_PER_KG * weight,
        available_volume,
    )
    if second_volume < 0.0:
        raise ValueError("2回目投与量が負になりました。投与条件を確認してください。")

    total_volume = first_volume + second_volume
    if total_volume > config.MAX_TOTAL_VOLUME_ML + np.finfo(float).eps:
        raise ValueError("総投与量は10 mLを超えることができません。")

    first_dose = first_volume / weight
    second_dose = second_volume / weight
    total_dose = total_volume / weight
    return DoseResult(
        first_volume_ml=first_volume,
        second_volume_ml=second_volume,
        total_volume_ml=total_volume,
        first_dose_mmol_per_kg=first_dose,
        second_dose_mmol_per_kg=second_dose,
        total_dose_mmol_per_kg=total_dose,
        target_dose_ratio_percent=(
            total_dose / config.TARGET_TOTAL_DOSE_MMOL_PER_KG * 100.0
        ),
        first_injection_duration_s=calculate_injection_duration(first_volume),
        second_injection_duration_s=calculate_injection_duration(second_volume),
    )


def calculate_first_injection_concentration(
    weight_kg: float,
    time_min: float,
    a_pk: float = config.DEFAULT_A_PK,
    washout_rate_per_min: float = config.DEFAULT_WASHOUT_RATE_PER_MIN,
) -> float:
    """1回目投与由来の心筋内見かけ濃度（mM）を計算する。"""

    time = _finite_number(time_min, "造影後経過時間")
    if time < config.FIRST_INJECTION_TIME_MIN:
        raise ValueError("造影後経過時間は0分以上で入力してください。")
    amplitude = _positive_number(a_pk, "A_PK")
    washout = _positive_number(washout_rate_per_min, "k")
    dose = calculate_dose(weight_kg)
    return amplitude * dose.first_dose_mmol_per_kg * math.exp(-washout * time)


def calculate_second_injection_concentration(
    weight_kg: float,
    time_min: float,
    a_pk: float = config.DEFAULT_A_PK,
    washout_rate_per_min: float = config.DEFAULT_WASHOUT_RATE_PER_MIN,
) -> float:
    """2回目投与由来の濃度（mM）を固定注入時刻2分の区分式で計算する。"""

    time = _finite_number(time_min, "造影後経過時間")
    if time < config.FIRST_INJECTION_TIME_MIN:
        raise ValueError("造影後経過時間は0分以上で入力してください。")
    amplitude = _positive_number(a_pk, "A_PK")
    washout = _positive_number(washout_rate_per_min, "k")
    if config.SECOND_INJECTION_TIME_MIN <= 0.0:
        raise ValueError("2回目注入時刻は0より大きい必要があります。")
    if time < config.SECOND_INJECTION_TIME_MIN:
        return 0.0
    dose = calculate_dose(weight_kg)
    elapsed = time - config.SECOND_INJECTION_TIME_MIN
    return amplitude * dose.second_dose_mmol_per_kg * math.exp(-washout * elapsed)


def calculate_apparent_myocardial_concentration(
    weight_kg: float,
    time_min: float,
    a_pk: float = config.DEFAULT_A_PK,
    washout_rate_per_min: float = config.DEFAULT_WASHOUT_RATE_PER_MIN,
) -> ConcentrationResult:
    """TI scout時点の2投与由来および総心筋内見かけ濃度（mM）を返す。"""

    time = validate_scout_time(time_min)
    amplitude = _positive_number(a_pk, "A_PK")
    washout = _positive_number(washout_rate_per_min, "k")
    first = calculate_first_injection_concentration(weight_kg, time, amplitude, washout)
    second = calculate_second_injection_concentration(weight_kg, time, amplitude, washout)
    return ConcentrationResult(
        first_concentration_mmol_per_l=first,
        second_concentration_mmol_per_l=second,
        total_concentration_mmol_per_l=first + second,
        a_pk=amplitude,
        washout_rate_per_min=washout,
        second_injection_time_min=config.SECOND_INJECTION_TIME_MIN,
    )


def calculate_post_contrast_t1(
    native_t1_ms: float,
    concentration_mmol_per_l: float,
    relaxivity_per_mmol_l_s: float = config.DEFAULT_RELAXIVITY_PER_MMOL_L_S,
) -> float:
    """R1=1000/native T1+r1*Cから造影後正常心筋T1（ms）を計算する。"""

    native_t1 = validate_native_t1(native_t1_ms)
    concentration = _finite_number(concentration_mmol_per_l, "心筋内見かけ濃度")
    if concentration < 0.0:
        raise ValueError("心筋内見かけ濃度は0以上で入力してください。")
    relaxivity = _positive_number(relaxivity_per_mmol_l_s, "r1")
    native_r1_per_s = 1000.0 / native_t1
    post_r1_per_s = native_r1_per_s + relaxivity * concentration
    return 1000.0 / post_r1_per_s


def calculate_ideal_null_ti(post_t1_ms: float) -> float:
    """理想反転回復式 T1×ln(2) から理想null TI（ms）を計算する。"""

    post_t1 = _positive_number(post_t1_ms, "造影後T1")
    return post_t1 * math.log(2.0)


def calculate_corrected_null_ti(
    post_t1_ms: float,
    facility_offset_ms: float = config.DEFAULT_FACILITY_OFFSET_MS,
) -> float:
    """理想null TIに施設校正値を加え、施設校正後null TI（ms）を返す。"""

    offset = _finite_number(facility_offset_ms, "施設校正値")
    corrected = calculate_ideal_null_ti(post_t1_ms) + offset
    if corrected <= 0.0:
        raise ValueError("施設校正後null TIは0より大きい必要があります。")
    return corrected


def generate_ti_signal_curve(
    null_ti_ms: float,
    ti_min_ms: float = config.DEFAULT_TI_MIN_MS,
    ti_max_ms: float = config.DEFAULT_TI_MAX_MS,
    step_ms: float = config.DEFAULT_TI_STEP_MS,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """TI配列と正規化Magnitude相対信号（%）の配列を生成する。"""

    null_ti = _positive_number(null_ti_ms, "施設校正後null TI")
    ti_min = _finite_number(ti_min_ms, "TI表示最小値")
    ti_max = _finite_number(ti_max_ms, "TI表示最大値")
    step = _positive_number(step_ms, "TI計算刻み")
    if ti_min < 0.0:
        raise ValueError("TI表示最小値は0以上で入力してください。")
    if ti_max <= ti_min:
        raise ValueError("TI表示最大値はTI表示最小値より大きくしてください。")

    count = math.floor((ti_max - ti_min) / step)
    ti_values = ti_min + np.arange(count + 1, dtype=np.float64) * step
    if not math.isclose(float(ti_values[-1]), ti_max):
        ti_values = np.append(ti_values, np.float64(ti_max))
    tau_display_ms = null_ti / math.log(2.0)
    signed_signal = 1.0 - 2.0 * np.exp(-ti_values / tau_display_ms)
    relative_signal_percent = 100.0 * np.abs(signed_signal)
    return ti_values, relative_signal_percent
