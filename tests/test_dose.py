"""投与量、注入時間、基本入力検証の単体テスト。"""

import math

import pytest

from model import (
    calculate_dose,
    calculate_injection_duration,
    validate_native_t1,
    validate_scout_time,
    validate_weight,
)


@pytest.mark.parametrize(
    ("weight", "first", "second", "total", "dose_per_kg"),
    [
        (30.0, 1.5, 4.5, 6.0, 0.200),
        (45.0, 2.3, 6.7, 9.0, 0.200),
        (50.0, 2.5, 7.5, 10.0, 0.200),
        (55.0, 2.8, 7.2, 10.0, 10.0 / 55.0),
        (70.0, 3.5, 6.5, 10.0, 10.0 / 70.0),
        (100.0, 5.0, 5.0, 10.0, 0.100),
    ],
)
def test_representative_doses(weight, first, second, total, dose_per_kg):
    result = calculate_dose(weight)
    assert result.first_volume_ml == pytest.approx(first, abs=0.001)
    assert result.second_volume_ml == pytest.approx(second, abs=0.001)
    assert result.total_volume_ml == pytest.approx(total, abs=0.001)
    assert result.total_dose_mmol_per_kg == pytest.approx(dose_per_kg)


@pytest.mark.parametrize("weight", range(30, 101))
def test_volume_limit_and_nonnegative_second_dose(weight):
    result = calculate_dose(float(weight))
    assert result.total_volume_ml <= 10.0
    assert result.second_volume_ml >= 0.0


@pytest.mark.parametrize("weight", [30.0, 40.0, 50.0])
def test_low_weight_total_dose_is_target(weight):
    assert calculate_dose(weight).total_dose_mmol_per_kg == pytest.approx(0.20)


def test_first_injection_is_rounded_up_to_injector_step():
    result = calculate_dose(45.0)
    assert result.first_volume_ml == pytest.approx(2.3)
    assert result.second_volume_ml == pytest.approx(6.7)
    assert result.total_dose_mmol_per_kg == pytest.approx(0.20)


def test_injection_durations():
    result = calculate_dose(50.0)
    assert result.first_injection_duration_s == pytest.approx(1.25)
    assert result.second_injection_duration_s == pytest.approx(3.75)
    assert calculate_injection_duration(6.0, 2.0) == pytest.approx(3.0)


@pytest.mark.parametrize("invalid", [29.9, 100.1, math.inf, math.nan, "50", True])
def test_invalid_weight(invalid):
    with pytest.raises(ValueError, match="体重"):
        validate_weight(invalid)


@pytest.mark.parametrize("valid", [30.0, 100.0])
def test_weight_boundaries(valid):
    assert validate_weight(valid) == valid


@pytest.mark.parametrize("invalid", [999.0, 1601.0])
def test_invalid_native_t1(invalid):
    with pytest.raises(ValueError, match="native T1"):
        validate_native_t1(invalid)


@pytest.mark.parametrize("invalid", [1.9, 16.6])
def test_invalid_scout_time(invalid):
    with pytest.raises(ValueError, match="TI scout撮像時刻"):
        validate_scout_time(invalid)


@pytest.mark.parametrize("volume, rate", [(-1.0, 2.0), (1.0, 0.0), (1.0, -2.0)])
def test_invalid_injection_inputs(volume, rate):
    with pytest.raises(ValueError):
        calculate_injection_duration(volume, rate)
