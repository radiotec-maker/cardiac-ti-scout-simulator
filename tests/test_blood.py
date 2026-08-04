"""第28節の左室血液プール計算モデルの単体テスト。"""

import math

import numpy as np
import pytest

import config
from model import (
    calculate_apparent_blood_concentration,
    calculate_corrected_blood_null_ti,
    calculate_corrected_null_ti,
    calculate_dose,
    calculate_first_injection_blood_concentration,
    calculate_ideal_blood_null_ti,
    calculate_post_contrast_blood_t1,
    calculate_second_injection_blood_concentration,
    generate_blood_ti_signal_curve,
    validate_blood_facility_offset,
    validate_native_blood_t1,
)


def _blood_results(weight_kg: float, time_min: float = 5.0):
    """第28.10節の共通条件で血液モデルの主要値を返す。"""

    concentration = calculate_apparent_blood_concentration(weight_kg, time_min)
    post_t1 = calculate_post_contrast_blood_t1(
        config.DEFAULT_NATIVE_BLOOD_T1_MS,
        concentration.total_concentration_mmol_per_l,
    )
    ideal_null = calculate_ideal_blood_null_ti(post_t1)
    corrected_null = calculate_corrected_blood_null_ti(post_t1)
    return concentration, post_t1, ideal_null, corrected_null


def test_blood_configuration_matches_section_28():
    assert config.DEFAULT_A_BLOOD == 5.86776
    assert config.DEFAULT_BLOOD_WASHOUT_RATE_PER_MIN == 0.07316
    assert config.DEFAULT_BLOOD_RELAXIVITY_PER_MMOL_L_S == 5.0
    assert config.DEFAULT_NATIVE_BLOOD_T1_MS == 1800.0
    assert config.MIN_NATIVE_BLOOD_T1_MS == 1400.0
    assert config.MAX_NATIVE_BLOOD_T1_MS == 2200.0
    assert config.NATIVE_BLOOD_T1_STEP_MS == 10.0
    assert config.DEFAULT_BLOOD_FACILITY_OFFSET_MS == 0.0
    assert config.MIN_BLOOD_FACILITY_OFFSET_MS == -100.0
    assert config.MAX_BLOOD_FACILITY_OFFSET_MS == 100.0
    assert config.BLOOD_FACILITY_OFFSET_STEP_MS == 1.0


def test_myocardial_configuration_is_unchanged_and_independent():
    assert config.DEFAULT_A_PK == 3.82385
    assert config.DEFAULT_WASHOUT_RATE_PER_MIN == 0.054457
    assert config.DEFAULT_RELAXIVITY_PER_MMOL_L_S == 5.0
    assert config.DEFAULT_FACILITY_OFFSET_MS == 57.0
    assert config.DEFAULT_A_BLOOD != config.DEFAULT_A_PK
    assert (
        config.DEFAULT_BLOOD_WASHOUT_RATE_PER_MIN
        != config.DEFAULT_WASHOUT_RATE_PER_MIN
    )


@pytest.mark.parametrize(
    ("weight", "expected_concentration", "expected_t1", "expected_null"),
    [
        (50.0, 0.885, 201.0, 139.0),
        (55.0, 0.802, 219.0, 152.0),
        (70.0, 0.625, 272.0, 188.0),
    ],
)
def test_section_28_reference_values(
    weight, expected_concentration, expected_t1, expected_null
):
    concentration, post_t1, ideal_null, corrected_null = _blood_results(weight)
    assert concentration.total_concentration_mmol_per_l == pytest.approx(
        expected_concentration, abs=0.002
    )
    assert post_t1 == pytest.approx(expected_t1, abs=1.0)
    assert ideal_null == pytest.approx(expected_null, abs=1.0)
    assert corrected_null == pytest.approx(expected_null, abs=1.0)


def test_blood_concentration_is_sum_of_shared_two_injections():
    result = calculate_apparent_blood_concentration(55.0, 5.0)
    assert result.first_concentration_mmol_per_l == pytest.approx(
        calculate_first_injection_blood_concentration(55.0, 5.0)
    )
    assert result.second_concentration_mmol_per_l == pytest.approx(
        calculate_second_injection_blood_concentration(55.0, 5.0)
    )
    assert result.total_concentration_mmol_per_l == pytest.approx(
        result.first_concentration_mmol_per_l
        + result.second_concentration_mmol_per_l
    )
    assert result.second_injection_time_min == config.SECOND_INJECTION_TIME_MIN


def test_blood_components_use_existing_weight_based_doses():
    weight = 70.0
    time = 5.0
    dose = calculate_dose(weight)
    expected_first = (
        config.DEFAULT_A_BLOOD
        * dose.first_dose_mmol_per_kg
        * math.exp(-config.DEFAULT_BLOOD_WASHOUT_RATE_PER_MIN * time)
    )
    expected_second = (
        config.DEFAULT_A_BLOOD
        * dose.second_dose_mmol_per_kg
        * math.exp(
            -config.DEFAULT_BLOOD_WASHOUT_RATE_PER_MIN
            * (time - config.SECOND_INJECTION_TIME_MIN)
        )
    )
    assert calculate_first_injection_blood_concentration(
        weight, time
    ) == pytest.approx(expected_first)
    assert calculate_second_injection_blood_concentration(
        weight, time
    ) == pytest.approx(expected_second)


def test_second_blood_component_uses_shared_piecewise_injection_time():
    injection_time = config.SECOND_INJECTION_TIME_MIN
    assert (
        calculate_second_injection_blood_concentration(
            50.0, injection_time - 0.001
        )
        == 0.0
    )
    assert calculate_second_injection_blood_concentration(
        50.0, injection_time
    ) > 0.0


def test_30kg_and_50kg_blood_concentrations_are_identical():
    result_30 = calculate_apparent_blood_concentration(30.0, 5.0)
    result_50 = calculate_apparent_blood_concentration(50.0, 5.0)
    assert result_30.total_concentration_mmol_per_l == pytest.approx(
        result_50.total_concentration_mmol_per_l
    )


def test_blood_time_dependence():
    results = [_blood_results(55.0, time) for time in (2.0, 5.0, 15.0)]
    concentrations = [item[0].total_concentration_mmol_per_l for item in results]
    t1_values = [item[1] for item in results]
    null_values = [item[3] for item in results]
    assert concentrations == sorted(concentrations, reverse=True)
    assert t1_values == sorted(t1_values)
    assert null_values == sorted(null_values)


def test_post_blood_t1_and_ideal_null_equations():
    concentration = 0.5
    expected_t1 = 1000.0 / (1000.0 / 1800.0 + 5.0 * concentration)
    post_t1 = calculate_post_contrast_blood_t1(1800.0, concentration)
    assert post_t1 == pytest.approx(expected_t1)
    assert calculate_ideal_blood_null_ti(post_t1) == pytest.approx(
        post_t1 * math.log(2.0)
    )


def test_default_blood_correction_is_zero_and_does_not_reuse_57_ms():
    post_t1 = 200.0
    ideal = calculate_ideal_blood_null_ti(post_t1)
    blood_null = calculate_corrected_blood_null_ti(post_t1)
    myocardial_null = calculate_corrected_null_ti(post_t1)
    assert blood_null == pytest.approx(ideal)
    assert myocardial_null == pytest.approx(ideal + 57.0)
    assert blood_null != pytest.approx(myocardial_null)


def test_blood_correction_changes_only_blood_null_by_requested_amount():
    post_t1 = 200.0
    baseline = calculate_corrected_blood_null_ti(post_t1, 0.0)
    assert calculate_corrected_blood_null_ti(post_t1, 25.0) == pytest.approx(
        baseline + 25.0
    )
    assert calculate_corrected_null_ti(post_t1) == pytest.approx(
        post_t1 * math.log(2.0) + 57.0
    )


@pytest.mark.parametrize("valid", [1400.0, 1800.0, 2200.0])
def test_native_blood_t1_valid_values(valid):
    assert validate_native_blood_t1(valid) == valid


@pytest.mark.parametrize(
    "invalid", [1390.0, 2210.0, 1805.0, math.inf, math.nan, "1800", True]
)
def test_invalid_native_blood_t1_has_japanese_error(invalid):
    with pytest.raises(ValueError, match="native blood T1"):
        validate_native_blood_t1(invalid)


@pytest.mark.parametrize("valid", [-100.0, 0.0, 100.0])
def test_blood_facility_offset_valid_values(valid):
    assert validate_blood_facility_offset(valid) == valid


@pytest.mark.parametrize(
    "invalid", [-101.0, 101.0, 0.5, math.inf, math.nan, "0", True]
)
def test_invalid_blood_facility_offset_has_japanese_error(invalid):
    with pytest.raises(ValueError, match="血液専用施設校正値"):
        validate_blood_facility_offset(invalid)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"a_blood": 0.0},
        {"a_blood": -1.0},
        {"washout_rate_per_min": 0.0},
        {"washout_rate_per_min": -1.0},
    ],
)
def test_invalid_blood_model_coefficients_have_japanese_error(kwargs):
    with pytest.raises(ValueError, match="A_blood|k_blood"):
        calculate_apparent_blood_concentration(50.0, 5.0, **kwargs)


def test_invalid_blood_relaxivity_and_concentration_have_japanese_error():
    with pytest.raises(ValueError, match="血液内見かけ濃度"):
        calculate_post_contrast_blood_t1(1800.0, -0.1)
    with pytest.raises(ValueError, match="r1_blood"):
        calculate_post_contrast_blood_t1(1800.0, 0.1, 0.0)


def test_corrected_blood_null_must_be_positive():
    with pytest.raises(ValueError, match="血液専用施設校正後null TI"):
        calculate_corrected_blood_null_ti(1.0, -100.0)


def test_blood_result_records_its_own_coefficients():
    result = calculate_apparent_blood_concentration(50.0, 5.0)
    assert result.a_blood == config.DEFAULT_A_BLOOD
    assert result.washout_rate_per_min == config.DEFAULT_BLOOD_WASHOUT_RATE_PER_MIN
    assert result.second_injection_time_min == config.SECOND_INJECTION_TIME_MIN


def test_blood_signal_curve_bounds_and_length():
    ti, signal = generate_blood_ti_signal_curve(150.0)
    assert ti[0] == 0.0
    assert ti[-1] == 700.0
    assert len(ti) == len(signal) == 701
    assert np.all(signal >= 0.0)
    assert np.all(signal <= 100.0 + 1e-12)


def test_blood_signal_curve_zero_matches_corrected_null():
    ti, signal = generate_blood_ti_signal_curve(150.0)
    null_index = int(np.where(ti == 150.0)[0][0])
    assert signal[null_index] == pytest.approx(0.0, abs=1e-12)


def test_blood_signal_decreases_then_increases_around_null():
    ti, signal = generate_blood_ti_signal_curve(150.0)
    before = signal[(ti >= 100.0) & (ti <= 150.0)]
    after = signal[(ti >= 150.0) & (ti <= 200.0)]
    assert np.all(np.diff(before) < 0.0)
    assert np.all(np.diff(after) > 0.0)


@pytest.mark.parametrize(
    "args",
    [
        (0.0, 0.0, 700.0, 1.0),
        (150.0, -1.0, 700.0, 1.0),
        (150.0, 700.0, 700.0, 1.0),
        (150.0, 0.0, 700.0, 0.0),
    ],
)
def test_invalid_blood_curve_inputs_have_japanese_error(args):
    with pytest.raises(ValueError):
        generate_blood_ti_signal_curve(*args)
