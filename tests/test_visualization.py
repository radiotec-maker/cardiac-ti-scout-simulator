"""左室短軸模式図とTI選択信号の単体テスト。"""

import pytest

from visualization import (
    calculate_signal_at_ti,
    generate_lv_short_axis_svg,
    signal_percent_to_rgb,
    shift_illustration_ti,
    validate_illustration_ti,
)


def test_zero_percent_is_black():
    assert signal_percent_to_rgb(0.0) == (0, 0, 0)


def test_one_hundred_percent_is_white():
    assert signal_percent_to_rgb(100.0) == (255, 255, 255)


def test_fifty_percent_is_middle_gray():
    assert signal_percent_to_rgb(50.0) == (128, 128, 128)


def test_myocardial_gamma_keeps_null_black_and_brightens_low_signal():
    import config

    assert signal_percent_to_rgb(0.0, config.MYOCARDIAL_GRAYSCALE_GAMMA) == (0, 0, 0)
    gamma_gray = signal_percent_to_rgb(
        10.0, config.MYOCARDIAL_GRAYSCALE_GAMMA
    )[0]
    linear_gray = signal_percent_to_rgb(10.0)[0]
    assert gamma_gray > linear_gray


def test_signal_at_null_is_black():
    signal = calculate_signal_at_ti(250.0, 250.0)
    assert signal == pytest.approx(0.0, abs=1e-12)
    assert signal_percent_to_rgb(signal) == (0, 0, 0)


def test_signal_gets_brighter_away_from_null():
    at_null = calculate_signal_at_ti(250.0, 250.0)
    before_null = calculate_signal_at_ti(250.0, 150.0)
    after_null = calculate_signal_at_ti(250.0, 350.0)
    assert before_null > at_null
    assert after_null > at_null


def test_weight_curves_are_evaluated_independently():
    signal_a = calculate_signal_at_ti(232.0, 250.0)
    signal_b = calculate_signal_at_ti(285.0, 250.0)
    assert signal_a != pytest.approx(signal_b)


@pytest.mark.parametrize("invalid_ti", [-0.1, 700.1])
def test_out_of_range_ti_has_japanese_error(invalid_ti):
    with pytest.raises(ValueError, match="イラスト表示TIは0～700 ms"):
        validate_illustration_ti(invalid_ti)


@pytest.mark.parametrize("invalid_signal", [-0.1, 100.1, float("nan")])
def test_invalid_signal_is_rejected(invalid_signal):
    with pytest.raises(ValueError, match="正常心筋相対信号"):
        signal_percent_to_rgb(invalid_signal)


def test_svg_contains_independent_myocardial_and_blood_gray():
    svg = generate_lv_short_axis_svg(50.0, 25.0)
    assert 'fill="rgb(180,180,180)"' in svg
    assert 'fill="rgb(64,64,64)"' in svg
    assert "血液相対信号25.0パーセント" in svg


def test_svg_rejects_invalid_numeric_value():
    with pytest.raises(ValueError, match="正常心筋相対信号"):
        generate_lv_short_axis_svg(float("inf"), 50.0)


def test_svg_rejects_invalid_blood_signal():
    with pytest.raises(ValueError, match="血液相対信号"):
        generate_lv_short_axis_svg(50.0, float("inf"))


def test_left_operation_moves_250_to_240():
    assert shift_illustration_ti(250.0, -1) == 240.0


def test_right_operation_moves_250_to_260():
    assert shift_illustration_ti(250.0, 1) == 260.0


def test_left_operation_stays_at_zero_boundary():
    assert shift_illustration_ti(0.0, -1) == 0.0


def test_right_operation_stays_at_700_boundary():
    assert shift_illustration_ti(700.0, 1) == 700.0


def test_illustration_ti_step_is_10_ms():
    import config

    assert config.ILLUSTRATION_TI_STEP_MS == 10.0


def test_illustration_ti_large_step_is_30_ms():
    import config

    assert config.ILLUSTRATION_TI_LARGE_STEP_MS == 30.0


def test_svg_contains_both_ventricles_and_lv_structures():
    svg = generate_lv_short_axis_svg(50.0, 25.0)
    assert 'id="right-ventricle"' in svg
    assert 'id="left-ventricular-myocardium"' in svg
    assert 'id="left-ventricular-cavity"' in svg
    assert "左室・右室短軸模式図" in svg


def test_svg_pattern_ids_are_independent_for_a_and_b():
    svg_a = generate_lv_short_axis_svg(50.0, 25.0, "lv-cavity-hatch-a")
    svg_b = generate_lv_short_axis_svg(50.0, 25.0, "lv-cavity-hatch-b")
    assert svg_a == svg_b


def test_lv_cavity_and_rv_use_the_same_blood_gray():
    svg = generate_lv_short_axis_svg(80.0, 25.0)
    assert svg.count('fill="rgb(64,64,64)"') == 2


def test_invalid_grayscale_gamma_is_rejected():
    with pytest.raises(ValueError, match="グレースケールガンマ"):
        signal_percent_to_rgb(50.0, 0.0)
