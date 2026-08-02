"""正規化Magnitude TI–信号強度曲線の単体テスト。"""

import numpy as np
import pytest

from model import (
    calculate_apparent_myocardial_concentration,
    calculate_corrected_null_ti,
    calculate_post_contrast_t1,
    generate_ti_signal_curve,
)


def test_default_ti_array_and_signal_bounds():
    ti, signal = generate_ti_signal_curve(250.0)
    assert ti[0] == 0.0
    assert ti[-1] == 700.0
    assert len(ti) == 701
    assert len(ti) == len(signal)
    assert np.all(signal >= 0.0)
    assert np.all(signal <= 100.0 + 1e-12)


def test_signal_is_zero_at_exact_null():
    ti, signal = generate_ti_signal_curve(250.0, 0.0, 700.0, 1.0)
    null_index = int(np.where(ti == 250.0)[0][0])
    assert signal[null_index] == pytest.approx(0.0, abs=1e-12)


def test_signal_decreases_before_and_increases_after_null():
    ti, signal = generate_ti_signal_curve(250.0)
    before = signal[(ti >= 200.0) & (ti <= 250.0)]
    after = signal[(ti >= 250.0) & (ti <= 300.0)]
    assert np.all(np.diff(before) < 0.0)
    assert np.all(np.diff(after) > 0.0)


def test_two_curves_use_identical_ti_array():
    ti_a, _ = generate_ti_signal_curve(236.0, 0.0, 700.0, 1.0)
    ti_b, _ = generate_ti_signal_curve(290.0, 0.0, 700.0, 1.0)
    assert np.array_equal(ti_a, ti_b)


def test_same_null_produces_same_curve():
    ti_a, signal_a = generate_ti_signal_curve(236.0)
    ti_b, signal_b = generate_ti_signal_curve(236.0)
    assert np.array_equal(ti_a, ti_b)
    assert np.allclose(signal_a, signal_b)


def test_30kg_and_50kg_results_and_curves_are_identical():
    """30～50 kgで体重当たり投与量が等しく、同条件の曲線が一致する。"""

    results = []
    for weight_kg in (30.0, 50.0):
        concentration = calculate_apparent_myocardial_concentration(
            weight_kg, 5.5
        ).total_concentration_mmol_per_l
        post_t1 = calculate_post_contrast_t1(1250.0, concentration)
        corrected_null_ti = calculate_corrected_null_ti(post_t1)
        ti, signal = generate_ti_signal_curve(corrected_null_ti)
        results.append((concentration, post_t1, corrected_null_ti, ti, signal))

    result_30kg, result_50kg = results
    assert result_30kg[0] == pytest.approx(result_50kg[0], abs=0.002)
    assert result_30kg[1] == pytest.approx(result_50kg[1], abs=1.0)
    assert result_30kg[2] == pytest.approx(result_50kg[2], abs=1.0)
    assert np.array_equal(result_30kg[3], result_50kg[3])
    assert np.allclose(result_30kg[4], result_50kg[4], atol=1e-12, rtol=0.0)


def test_non_divisible_step_stays_within_range_and_includes_end():
    ti, signal = generate_ti_signal_curve(250.0, 0.0, 700.0, 3.0)
    assert ti[-1] == 700.0
    assert np.all(ti <= 700.0)
    assert len(ti) == len(signal)


@pytest.mark.parametrize(
    "args",
    [
        (0.0, 0.0, 700.0, 1.0),
        (250.0, 700.0, 700.0, 1.0),
        (250.0, 701.0, 700.0, 1.0),
        (250.0, 0.0, 700.0, 0.0),
        (250.0, -1.0, 700.0, 1.0),
    ],
)
def test_invalid_curve_inputs(args):
    with pytest.raises(ValueError):
        generate_ti_signal_curve(*args)
