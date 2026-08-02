"""見かけ濃度、T1、null TIの単体テスト。"""

import math

import pytest

import config
from model import (
    calculate_apparent_myocardial_concentration,
    calculate_corrected_null_ti,
    calculate_dose,
    calculate_first_injection_concentration,
    calculate_ideal_null_ti,
    calculate_post_contrast_t1,
    calculate_second_injection_concentration,
    validate_psir_time,
)


def _model_results(weight, time=5.5, native_t1=1250.0):
    concentration = calculate_apparent_myocardial_concentration(weight, time)
    post_t1 = calculate_post_contrast_t1(
        native_t1, concentration.total_concentration_mmol_per_l
    )
    null_ti = calculate_corrected_null_ti(post_t1)
    return concentration, post_t1, null_ti


@pytest.mark.parametrize(
    ("weight", "expected_concentration", "expected_t1", "expected_null"),
    [
        (50.0, 0.616, 258.0, 236.0),
        (55.0, 0.558, 278.0, 250.0),
        (70.0, 0.435, 336.0, 290.0),
    ],
)
def test_reference_calculations(weight, expected_concentration, expected_t1, expected_null):
    concentration, post_t1, null_ti = _model_results(weight)
    assert concentration.total_concentration_mmol_per_l == pytest.approx(
        expected_concentration, abs=0.002
    )
    assert post_t1 == pytest.approx(expected_t1, abs=1.0)
    assert null_ti == pytest.approx(expected_null, abs=1.0)


def test_concentration_is_sum_of_two_injections():
    result = calculate_apparent_myocardial_concentration(55.0, 5.5)
    assert result.first_concentration_mmol_per_l == pytest.approx(
        calculate_first_injection_concentration(55.0, 5.5)
    )
    assert result.second_concentration_mmol_per_l == pytest.approx(
        calculate_second_injection_concentration(55.0, 5.5)
    )
    assert result.total_concentration_mmol_per_l == pytest.approx(
        result.first_concentration_mmol_per_l
        + result.second_concentration_mmol_per_l
    )


def test_second_injection_piecewise_model():
    assert calculate_second_injection_concentration(50.0, 1.999) == 0.0
    assert calculate_second_injection_concentration(50.0, 2.0) > 0.0


def test_t1_and_ideal_null_equations():
    concentration = 0.5
    expected_t1 = 1000.0 / (1000.0 / 1250.0 + 5.0 * concentration)
    post_t1 = calculate_post_contrast_t1(1250.0, concentration)
    assert post_t1 == pytest.approx(expected_t1)
    assert calculate_ideal_null_ti(post_t1) == pytest.approx(post_t1 * math.log(2.0))
    assert calculate_corrected_null_ti(post_t1, 57.0) == pytest.approx(
        post_t1 * math.log(2.0) + 57.0
    )


def test_weight_dependence_above_50_kg():
    weights = [55.0, 70.0, 100.0]
    doses = [calculate_dose(weight).total_dose_mmol_per_kg for weight in weights]
    results = [_model_results(weight) for weight in weights]
    t1_values = [item[1] for item in results]
    null_values = [item[2] for item in results]
    assert doses == sorted(doses, reverse=True)
    assert t1_values == sorted(t1_values)
    assert null_values == sorted(null_values)


def test_time_dependence():
    results = [_model_results(55.0, time=time) for time in (2.0, 5.5, 15.0)]
    concentrations = [item[0].total_concentration_mmol_per_l for item in results]
    t1_values = [item[1] for item in results]
    null_values = [item[2] for item in results]
    assert concentrations == sorted(concentrations, reverse=True)
    assert t1_values == sorted(t1_values)
    assert null_values == sorted(null_values)


def test_calibration_point_is_about_250_ms():
    _, _, null_ti = _model_results(55.0, 5.5, 1250.0)
    assert null_ti == pytest.approx(250.0, abs=1.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"a_pk": 0.0},
        {"a_pk": -1.0},
        {"washout_rate_per_min": 0.0},
        {"washout_rate_per_min": -1.0},
    ],
)
def test_invalid_model_coefficients(kwargs):
    with pytest.raises(ValueError):
        calculate_apparent_myocardial_concentration(50.0, 5.5, **kwargs)


def test_invalid_relaxivity_and_concentration():
    with pytest.raises(ValueError):
        calculate_post_contrast_t1(1250.0, -0.1)
    with pytest.raises(ValueError):
        calculate_post_contrast_t1(1250.0, 0.1, 0.0)


def test_corrected_null_must_be_positive():
    with pytest.raises(ValueError, match="施設校正後null TI"):
        calculate_corrected_null_ti(100.0, -1000.0)


def test_result_records_used_coefficients():
    result = calculate_apparent_myocardial_concentration(50.0, 5.5)
    assert result.a_pk == config.DEFAULT_A_PK
    assert result.washout_rate_per_min == config.DEFAULT_WASHOUT_RATE_PER_MIN
    assert result.second_injection_time_min == config.SECOND_INJECTION_TIME_MIN


def test_psir_time_configuration():
    assert config.DEFAULT_PSIR_TIME_MIN == 8.0
    assert config.MAX_PSIR_TIME_MIN == 15.0
    assert config.PSIR_TIME_STEP_MIN == 0.1


def test_psir_time_may_equal_scout_time():
    assert validate_psir_time(5.5, 5.5) == 5.5


@pytest.mark.parametrize("psir_time", [1.9, 15.1])
def test_psir_time_must_be_in_input_range(psir_time):
    with pytest.raises(ValueError, match="PSIR撮像開始時刻"):
        validate_psir_time(psir_time, 5.5)


def test_psir_time_must_not_precede_scout_time():
    with pytest.raises(
        ValueError, match="PSIR撮像開始時刻はTI scout撮像時刻以上"
    ):
        validate_psir_time(5.4, 5.5)


@pytest.mark.parametrize(
    ("weight", "expected_scout_null", "expected_psir_null"),
    [
        (50.0, 236.0, 256.0),
        (70.0, 290.0, 315.0),
    ],
)
def test_v1_1_reference_null_ti_values(
    weight, expected_scout_null, expected_psir_null
):
    scout_concentration = calculate_apparent_myocardial_concentration(weight, 5.5)
    scout_t1 = calculate_post_contrast_t1(
        1250.0, scout_concentration.total_concentration_mmol_per_l
    )
    scout_null = calculate_corrected_null_ti(scout_t1)

    psir_time = validate_psir_time(8.0, 5.5)
    psir_concentration = calculate_apparent_myocardial_concentration(
        weight, psir_time
    )
    psir_t1 = calculate_post_contrast_t1(
        1250.0, psir_concentration.total_concentration_mmol_per_l
    )
    psir_null = calculate_corrected_null_ti(psir_t1)

    assert scout_null == pytest.approx(expected_scout_null, abs=1.0)
    assert psir_null == pytest.approx(expected_psir_null, abs=2.0)
    assert psir_null - scout_null > 0.0
