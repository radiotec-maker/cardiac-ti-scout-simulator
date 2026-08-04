"""心臓MRI 正常心筋TI–信号強度シミュレータのStreamlit画面。"""

from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import config
from model import (
    BloodConcentrationResult,
    ConcentrationResult,
    DoseResult,
    calculate_apparent_blood_concentration,
    calculate_apparent_myocardial_concentration,
    calculate_corrected_blood_null_ti,
    calculate_corrected_null_ti,
    calculate_dose,
    calculate_ideal_blood_null_ti,
    calculate_ideal_null_ti,
    calculate_post_contrast_blood_t1,
    calculate_post_contrast_t1,
    generate_blood_ti_signal_curve,
    generate_ti_signal_curve,
    validate_psir_time,
)
from visualization import (
    calculate_signal_at_ti,
    generate_lv_short_axis_svg,
    shift_illustration_ti,
)


@dataclass(frozen=True)
class DisplayResult:
    """画面表示に必要な1体重分の計算結果を保持する。"""

    weight_kg: float
    dose: DoseResult
    concentration: ConcentrationResult
    post_t1_ms: float
    ideal_null_ti_ms: float
    corrected_null_ti_ms: float
    psir_concentration: ConcentrationResult
    psir_post_t1_ms: float
    psir_ideal_null_ti_ms: float
    psir_corrected_null_ti_ms: float
    null_ti_change_ms: float
    ti_values_ms: object
    signal_percent: object
    blood_concentration: BloodConcentrationResult
    post_blood_t1_ms: float
    ideal_blood_null_ti_ms: float
    corrected_blood_null_ti_ms: float
    blood_signal_percent: object


DEFAULT_STATE = {
    "weight": config.DEFAULT_WEIGHT_A_KG,
    "scout_time_after_second": config.DEFAULT_SCOUT_TIME_AFTER_SECOND_MIN,
    "psir_time_after_second": config.DEFAULT_PSIR_TIME_AFTER_SECOND_MIN,
    "illustration_ti": config.DEFAULT_ILLUSTRATION_TI_MS,
    "native_t1": config.DEFAULT_NATIVE_T1_MS,
    "native_blood_t1": config.DEFAULT_NATIVE_BLOOD_T1_MS,
    "a_pk": config.DEFAULT_A_PK,
    "washout_rate": config.DEFAULT_WASHOUT_RATE_PER_MIN,
    "relaxivity": config.DEFAULT_RELAXIVITY_PER_MMOL_L_S,
    "facility_offset": config.DEFAULT_FACILITY_OFFSET_MS,
    "a_blood": config.DEFAULT_A_BLOOD,
    "blood_washout_rate": config.DEFAULT_BLOOD_WASHOUT_RATE_PER_MIN,
    "blood_relaxivity": config.DEFAULT_BLOOD_RELAXIVITY_PER_MMOL_L_S,
    "blood_facility_offset": config.DEFAULT_BLOOD_FACILITY_OFFSET_MS,
    "ti_min": config.DEFAULT_TI_MIN_MS,
    "ti_max": config.DEFAULT_TI_MAX_MS,
    "ti_step": config.DEFAULT_TI_STEP_MS,
}


def initialize_state() -> None:
    """未設定の入力値を仕様書の初期値で初期化する。"""

    for key, value in DEFAULT_STATE.items():
        st.session_state.setdefault(key, value)


def reset_defaults() -> None:
    """通常入力と詳細設定をすべて初期値へ戻す。"""

    for key, value in DEFAULT_STATE.items():
        st.session_state[key] = value


def decrease_illustration_ti() -> None:
    """イラスト表示TIを1段階減少させるボタンコールバック。"""

    st.session_state.illustration_ti = shift_illustration_ti(
        st.session_state.illustration_ti, -1
    )


def increase_illustration_ti() -> None:
    """イラスト表示TIを1段階増加させるボタンコールバック。"""

    st.session_state.illustration_ti = shift_illustration_ti(
        st.session_state.illustration_ti, 1
    )


def decrease_illustration_ti_30() -> None:
    """イラスト表示TIを30 ms減少させるボタンコールバック。"""

    for _ in range(3):
        st.session_state.illustration_ti = shift_illustration_ti(
            st.session_state.illustration_ti, -1
        )


def increase_illustration_ti_30() -> None:
    """イラスト表示TIを30 ms増加させるボタンコールバック。"""

    for _ in range(3):
        st.session_state.illustration_ti = shift_illustration_ti(
            st.session_state.illustration_ti, 1
        )


def calculate_display_result(weight_kg: float) -> DisplayResult:
    """既存モデルを両撮像時刻へ適用し、1体重分の表示結果を計算する。"""

    dose = calculate_dose(weight_kg)
    scout_time_from_first = (
        config.SECOND_INJECTION_TIME_MIN
        + st.session_state.scout_time_after_second
    )
    psir_time_from_first = (
        config.SECOND_INJECTION_TIME_MIN
        + st.session_state.psir_time_after_second
    )
    psir_time = validate_psir_time(psir_time_from_first, scout_time_from_first)
    concentration = calculate_apparent_myocardial_concentration(
        weight_kg,
        scout_time_from_first,
        a_pk=st.session_state.a_pk,
        washout_rate_per_min=st.session_state.washout_rate,
    )
    post_t1 = calculate_post_contrast_t1(
        st.session_state.native_t1,
        concentration.total_concentration_mmol_per_l,
        relaxivity_per_mmol_l_s=st.session_state.relaxivity,
    )
    ideal_null_ti = calculate_ideal_null_ti(post_t1)
    corrected_null_ti = calculate_corrected_null_ti(
        post_t1, st.session_state.facility_offset
    )
    psir_concentration = calculate_apparent_myocardial_concentration(
        weight_kg,
        psir_time,
        a_pk=st.session_state.a_pk,
        washout_rate_per_min=st.session_state.washout_rate,
    )
    psir_post_t1 = calculate_post_contrast_t1(
        st.session_state.native_t1,
        psir_concentration.total_concentration_mmol_per_l,
        relaxivity_per_mmol_l_s=st.session_state.relaxivity,
    )
    psir_ideal_null_ti = calculate_ideal_null_ti(psir_post_t1)
    psir_corrected_null_ti = calculate_corrected_null_ti(
        psir_post_t1, st.session_state.facility_offset
    )
    ti_values, signal = generate_ti_signal_curve(
        # Magnitude曲線は従来どおりTI scout時点のnull TIを使用する。
        corrected_null_ti,
        st.session_state.ti_min,
        st.session_state.ti_max,
        st.session_state.ti_step,
    )
    blood_concentration = calculate_apparent_blood_concentration(
        weight_kg,
        scout_time_from_first,
        a_blood=st.session_state.a_blood,
        washout_rate_per_min=st.session_state.blood_washout_rate,
    )
    post_blood_t1 = calculate_post_contrast_blood_t1(
        st.session_state.native_blood_t1,
        blood_concentration.total_concentration_mmol_per_l,
        relaxivity_per_mmol_l_s=st.session_state.blood_relaxivity,
    )
    ideal_blood_null_ti = calculate_ideal_blood_null_ti(post_blood_t1)
    corrected_blood_null_ti = calculate_corrected_blood_null_ti(
        post_blood_t1, st.session_state.blood_facility_offset
    )
    _, blood_signal = generate_blood_ti_signal_curve(
        corrected_blood_null_ti,
        st.session_state.ti_min,
        st.session_state.ti_max,
        st.session_state.ti_step,
    )
    return DisplayResult(
        weight_kg=weight_kg,
        dose=dose,
        concentration=concentration,
        post_t1_ms=post_t1,
        ideal_null_ti_ms=ideal_null_ti,
        corrected_null_ti_ms=corrected_null_ti,
        psir_concentration=psir_concentration,
        psir_post_t1_ms=psir_post_t1,
        psir_ideal_null_ti_ms=psir_ideal_null_ti,
        psir_corrected_null_ti_ms=psir_corrected_null_ti,
        null_ti_change_ms=psir_corrected_null_ti - corrected_null_ti,
        ti_values_ms=ti_values,
        signal_percent=signal,
        blood_concentration=blood_concentration,
        post_blood_t1_ms=post_blood_t1,
        ideal_blood_null_ti_ms=ideal_blood_null_ti,
        corrected_blood_null_ti_ms=corrected_blood_null_ti,
        blood_signal_percent=blood_signal,
    )


def render_primary_result(result: DisplayResult) -> None:
    """設定体重の主要結果を表示する。"""

    st.subheader(f"設定体重：{result.weight_kg:.0f} kg")
    columns = st.columns(4)
    columns[0].metric(
        "総投与量", f"{result.dose.total_dose_mmol_per_kg:.3f} mmol/kg"
    )
    columns[1].metric(
        f"TI scout {st.session_state.scout_time_after_second:.1f}分後の予想心筋null TI",
        f"{result.corrected_null_ti_ms:.0f} ms",
    )
    columns[2].metric(
        f"TI scout {st.session_state.scout_time_after_second:.1f}分後の予想血液null TI",
        f"{result.corrected_blood_null_ti_ms:.0f} ms",
    )
    scout_myo_blood_difference = (
        result.corrected_null_ti_ms - result.corrected_blood_null_ti_ms
    )
    psir_myo_blood_difference = (
        result.psir_corrected_null_ti_ms - result.corrected_blood_null_ti_ms
    )
    columns[2].markdown(
        '<div class="null-reference-stack">'
        '<div class="null-ti-difference">'
        '<span>TI scout正常心筋null TIとの差</span>'
        f'<strong>{scout_myo_blood_difference:+.0f} ms</strong>'
        '</div>'
        '<div class="null-ti-difference">'
        '<span>PSIR正常心筋null TIとの差</span>'
        f'<strong>{psir_myo_blood_difference:+.0f} ms</strong>'
        '</div>'
        '<small>参考値：心筋null TI − TI scout血液null TI</small>'
        '</div>',
        unsafe_allow_html=True,
    )
    columns[3].metric(
        f"PSIR {st.session_state.psir_time_after_second:.1f}分後の予想心筋null TI",
        f"{result.psir_corrected_null_ti_ms:.0f} ms",
    )
    columns[3].markdown(
        '<div class="null-ti-difference">'
        '<span>TI scout正常心筋null TIとの差</span>'
        f'<strong>{result.null_ti_change_ms:+.0f} ms</strong>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_injection_table(result: DisplayResult) -> None:
    """設定体重に対するインジェクター設定値を表形式で表示する。"""

    theoretical_first = config.FIRST_DOSE_MMOL_PER_KG * result.weight_kg
    required_total_volume = (
        config.TARGET_TOTAL_DOSE_MMOL_PER_KG * result.weight_kg
    )
    dose_shortfall = max(
        0.0,
        config.TARGET_TOTAL_DOSE_MMOL_PER_KG
        - result.dose.total_dose_mmol_per_kg,
    )
    meets_standard = math.isclose(
        result.dose.total_dose_mmol_per_kg,
        config.TARGET_TOTAL_DOSE_MMOL_PER_KG,
        abs_tol=1e-12,
    )
    dose_summary = pd.DataFrame(
        {
            "確認項目": [
                "ガドビスト使用可能総量",
                "規定投与量",
                "設定体重で規定量に必要な総量",
                "実際の総投与量",
                "体重当たり実投与量",
                "規定量に対する割合",
                "規定量との差",
                "判定",
            ],
            "値": [
                f"{config.MAX_TOTAL_VOLUME_ML:.1f} mL",
                f"{config.TARGET_TOTAL_DOSE_MMOL_PER_KG:.3f} mmol/kg",
                f"{required_total_volume:.1f} mL",
                f"{result.dose.total_volume_ml:.1f} mL",
                f"{result.dose.total_dose_mmol_per_kg:.3f} mmol/kg",
                f"{result.dose.target_dose_ratio_percent:.1f} %",
                f"-{dose_shortfall:.3f} mmol/kg" if dose_shortfall > 0 else "差なし",
                "規定量を満たす" if meets_standard else "規定量を満たさない",
            ],
        }
    )
    injection_table = pd.DataFrame(
        {
            "項目": [
                "目標・計算量",
                "インジェクター設定量",
                "実投与量",
                "注入速度",
                "造影剤注入時間",
            ],
            "1回目（perfusion）": [
                f"0.05 mmol/kg = {theoretical_first:.2f} mL",
                f"{result.dose.first_volume_ml:.1f} mL（0.1 mL単位で切り上げ）",
                f"{result.dose.first_dose_mmol_per_kg:.3f} mmol/kg",
                f"{config.CONTRAST_INJECTION_RATE_ML_S:.1f} mL/s",
                f"{result.dose.first_injection_duration_s:.2f} s",
            ],
            "2回目（追加注入）": [
                "総投与量が目標値となる残量",
                f"{result.dose.second_volume_ml:.1f} mL",
                f"{result.dose.second_dose_mmol_per_kg:.3f} mmol/kg",
                f"{config.CONTRAST_INJECTION_RATE_ML_S:.1f} mL/s",
                f"{result.dose.second_injection_duration_s:.2f} s",
            ],
        }
    )
    st.subheader("造影剤投与量")
    st.caption(
        f"設定体重 {result.weight_kg:.0f} kg に対するインジェクター設定値です。"
        "体重を変更すると自動的に再計算されます。"
    )
    dose_columns = st.columns(3)
    dose_columns[0].metric(
        "1回目（perfusion）", f"{result.dose.first_volume_ml:.1f} mL"
    )
    dose_columns[1].metric(
        "2回目（追加注入）", f"{result.dose.second_volume_ml:.1f} mL"
    )
    dose_columns[2].metric(
        f"実投与量（目標 {config.TARGET_TOTAL_DOSE_MMOL_PER_KG:.3f} mmol/kg）",
        f"{result.dose.total_dose_mmol_per_kg:.3f} mmol/kg",
    )

    with st.expander("造影剤注入条件の詳細を確認", expanded=False):
        st.dataframe(dose_summary, hide_index=True, width="stretch")
        if result.weight_kg <= 50.0:
            st.info(
                f"{result.weight_kg:.0f} kg：目標0.200 mmol/kgを維持し、"
                "インジェクター設定量を自動計算しています。"
            )
        else:
            st.warning(
                f"{result.weight_kg:.0f} kg：総量10.0 mLを上限として、"
                f"実投与量は{result.dose.total_dose_mmol_per_kg:.3f} mmol/kgです。"
                f"目標0.200 mmol/kgを{dose_shortfall:.3f} mmol/kg下回ります。"
            )
        st.dataframe(injection_table, hide_index=True, width="stretch")


def render_psir_ti_guide(result: DisplayResult) -> None:
    """選択したPSIR開始時刻から15分までの推定心筋null TIを表示する。"""

    guide_start_min = float(st.session_state.psir_time_after_second)
    guide_start_label = (
        f"{guide_start_min:.0f}"
        if guide_start_min.is_integer()
        else f"{guide_start_min:.1f}"
    )
    baseline_time_from_first = config.SECOND_INJECTION_TIME_MIN + guide_start_min
    baseline_concentration = calculate_apparent_myocardial_concentration(
        result.weight_kg,
        baseline_time_from_first,
        a_pk=st.session_state.a_pk,
        washout_rate_per_min=st.session_state.washout_rate,
    )
    baseline_post_t1 = calculate_post_contrast_t1(
        st.session_state.native_t1,
        baseline_concentration.total_concentration_mmol_per_l,
        relaxivity_per_mmol_l_s=st.session_state.relaxivity,
    )
    baseline_null_ti = calculate_corrected_null_ti(
        baseline_post_t1, st.session_state.facility_offset
    )
    table_data: dict[str, list[str]] = {
        "項目": ["設定TI目安", f"{guide_start_label}分からの変化"]
    }
    number_of_minutes = int(
        math.floor(config.MAX_PSIR_TIME_AFTER_SECOND_MIN - guide_start_min + 1e-9)
    )
    guide_times = [guide_start_min + offset for offset in range(number_of_minutes + 1)]
    for elapsed_after_second in guide_times:
        time_from_first = config.SECOND_INJECTION_TIME_MIN + elapsed_after_second
        concentration = calculate_apparent_myocardial_concentration(
            result.weight_kg,
            time_from_first,
            a_pk=st.session_state.a_pk,
            washout_rate_per_min=st.session_state.washout_rate,
        )
        post_t1 = calculate_post_contrast_t1(
            st.session_state.native_t1,
            concentration.total_concentration_mmol_per_l,
            relaxivity_per_mmol_l_s=st.session_state.relaxivity,
        )
        null_ti = calculate_corrected_null_ti(
            post_t1, st.session_state.facility_offset
        )
        time_label = (
            f"{elapsed_after_second:.0f}"
            if elapsed_after_second.is_integer()
            else f"{elapsed_after_second:.1f}"
        )
        table_data[f"{time_label}分"] = [
            f"{null_ti:.0f} ms",
            (
                "±0 ms"
                if math.isclose(elapsed_after_second, guide_start_min)
                else f"{null_ti - baseline_null_ti:+.0f} ms"
            ),
        ]
    st.subheader("PSIR撮像時の設定TI目安")
    st.markdown(
        "**PSIR撮像開始時刻［2回目注入後 min］**"
    )
    st.caption(
        f"設定体重：{result.weight_kg:.0f} kgで計算した推定値です。"
    )
    guide_table = pd.DataFrame(table_data).to_html(
        index=False,
        classes="psir-guide-table",
        border=0,
        escape=True,
    )
    st.markdown(
        f'<div class="psir-guide-wrap">{guide_table}</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "時間はインジェクターの2回目造影剤注入開始を0分とした経過時間です。"
        "表示値は推定正常心筋null TIであり、PSIR撮像時の設定TIを考えるための目安です。"
        f"予想変化は{guide_start_label}分時点の推定値を基準としています。"
    )
def render_detail(result: DisplayResult) -> None:
    """設定体重の計算詳細表を表示する。"""

    st.markdown(f"#### 設定体重：{result.weight_kg:.0f} kg")
    details = pd.DataFrame(
        {
            "項目": [
                "1回目投与量",
                "1回目体重当たり投与量",
                "1回目注入時間",
                "2回目投与量",
                "2回目体重当たり投与量",
                "2回目注入時間",
                "総投与量",
                "目標量に対する割合",
                "1回目由来見かけ濃度",
                "2回目由来見かけ濃度",
                "総心筋内見かけ濃度",
                "モデル内部の推定造影後心筋T1",
                "理想null TI",
                "PSIR開始時点の総心筋内見かけ濃度",
                "PSIR開始時点のモデル内部の推定造影後心筋T1",
                "PSIR開始時点の理想null TI",
                "TI scout時点の総血液内見かけ濃度",
                "TI scout時点の推定造影後血液T1",
                "理論blood null TI",
                "血液専用校正後null TI",
            ],
            "値": [
                f"{result.dose.first_volume_ml:.2f} mL",
                f"{result.dose.first_dose_mmol_per_kg:.3f} mmol/kg",
                f"{result.dose.first_injection_duration_s:.2f} s",
                f"{result.dose.second_volume_ml:.2f} mL",
                f"{result.dose.second_dose_mmol_per_kg:.3f} mmol/kg",
                f"{result.dose.second_injection_duration_s:.2f} s",
                f"{result.dose.total_volume_ml:.2f} mL",
                f"{result.dose.target_dose_ratio_percent:.1f} %",
                f"{result.concentration.first_concentration_mmol_per_l:.3f} mM",
                f"{result.concentration.second_concentration_mmol_per_l:.3f} mM",
                f"{result.concentration.total_concentration_mmol_per_l:.3f} mM",
                f"{result.post_t1_ms:.0f} ms",
                f"{result.ideal_null_ti_ms:.0f} ms",
                f"{result.psir_concentration.total_concentration_mmol_per_l:.3f} mM",
                f"{result.psir_post_t1_ms:.0f} ms",
                f"{result.psir_ideal_null_ti_ms:.0f} ms",
                f"{result.blood_concentration.total_concentration_mmol_per_l:.3f} mM",
                f"{result.post_blood_t1_ms:.0f} ms",
                f"{result.ideal_blood_null_ti_ms:.0f} ms",
                f"{result.corrected_blood_null_ti_ms:.0f} ms",
            ],
        }
    )
    st.dataframe(details, hide_index=True, width="stretch")
    st.caption(
        "このT1値は、LGE撮像で設定するInversion Time（TI）ではありません。"
    )


def render_illustration_column(
    result: DisplayResult,
    display_ti_ms: float,
    signal_percent: float,
    blood_signal_percent: float,
) -> None:
    """設定体重の左室短軸模式図と選択TIの数値を表示する。"""

    pattern_id = "lv-cavity-hatch"
    svg = generate_lv_short_axis_svg(signal_percent, blood_signal_percent, pattern_id)
    components.html(
        f"""<div style="width:100%;height:240px;display:flex;align-items:center;justify-content:center;background:transparent;overflow:hidden">
{svg}
</div>""",
        height=250,
        scrolling=False,
    )


def render_signal_graph(
    result: DisplayResult,
    illustration_ti_ms: float,
    illustration_signal: float,
    illustration_blood_signal: float,
) -> None:
    """設定体重の心筋・血液Magnitude曲線とnull位置を表示する。"""

    figure = go.Figure()
    myocardial_color = "#1f77b4"
    blood_color = "#555555"
    figure.add_trace(go.Scatter(
        x=result.ti_values_ms, y=result.signal_percent, mode="lines",
        name=f"正常心筋（{result.weight_kg:.0f} kg）",
        line={"color": myocardial_color, "width": 3},
        hovertemplate="TI: %{x:.0f} ms<br>心筋相対信号: %{y:.1f}%<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=result.ti_values_ms, y=result.blood_signal_percent, mode="lines",
        name="血液", line={"color": blood_color, "width": 2.5, "dash": "dot"},
        hovertemplate="TI: %{x:.0f} ms<br>血液相対信号: %{y:.1f}%<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=[result.corrected_null_ti_ms], y=[0.0], mode="markers+text",
        marker={"color": myocardial_color, "size": 10, "symbol": "circle"},
        text=[f"心筋null：{result.corrected_null_ti_ms:.0f} ms"],
        textposition="top center", showlegend=False,
        hovertemplate="心筋null：%{x:.0f} ms<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=[result.corrected_blood_null_ti_ms], y=[0.0], mode="markers+text",
        marker={"color": blood_color, "size": 9, "symbol": "diamond-open"},
        text=[f"血液null：{result.corrected_blood_null_ti_ms:.0f} ms"],
        textposition="bottom center", showlegend=False,
        hovertemplate="血液null：%{x:.0f} ms<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=[illustration_ti_ms], y=[illustration_signal], mode="markers",
        marker={"color": myocardial_color, "size": 11, "symbol": "diamond"},
        showlegend=False,
        hovertemplate="設定TI：%{x:.0f} ms<br>心筋相対信号：%{y:.1f}%<extra></extra>",
    ))
    figure.add_trace(go.Scatter(
        x=[illustration_ti_ms], y=[illustration_blood_signal], mode="markers",
        marker={"color": blood_color, "size": 10, "symbol": "diamond-open"},
        showlegend=False,
        hovertemplate="設定TI：%{x:.0f} ms<br>血液相対信号：%{y:.1f}%<extra></extra>",
    ))
    figure.add_vline(
        x=result.corrected_null_ti_ms, line_color=myocardial_color,
        line_dash="dash", line_width=1.5,
    )

    figure.add_vline(
        x=illustration_ti_ms,
        line_color="rgb(90,90,90)",
        line_dash="dot",
        line_width=2,
        annotation_text="イラスト表示TI",
        annotation_position="top",
    )

    figure.update_layout(
        title="TI scoutにおける正常心筋・血液Magnitude信号曲線",
        xaxis_title="Inversion Time（TI）［ms］",
        yaxis_title="正規化Magnitude信号［%］",
        xaxis={"range": [st.session_state.ti_min, st.session_state.ti_max]},
        yaxis={"range": [0, 100]},
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.02, "x": 0.0},
        margin={"l": 50, "r": 30, "t": 90, "b": 50},
    )
    st.plotly_chart(figure, width="stretch")


st.set_page_config(
    page_title="心臓MRI 正常心筋TI–信号強度シミュレータ",
    layout="wide",
)
initialize_state()

st.markdown(
    """
<style>
/* 入力項目名と数値を大きくし、各入力枠の高さをそろえる。 */
div[data-testid="stNumberInput"] label p {
    font-size: 1.08rem;
    font-weight: 700;
}
div[data-testid="stNumberInput"] [data-baseweb="input"] {
    min-height: 3.5rem;
}
div[data-testid="stNumberInput"] input {
    font-size: 1.45rem;
    font-weight: 700;
}
.psir-guide-wrap {
    width: 100%;
    overflow-x: auto;
    margin: 0.4rem 0 0.8rem 0;
}
.psir-guide-table {
    width: 100%;
    min-width: 900px;
    border-collapse: separate;
    border-spacing: 0;
    border: 1px solid #d9dde5;
    border-radius: 0.6rem;
    overflow: hidden;
}
.psir-guide-table th,
.psir-guide-table td {
    padding: 0.8rem 0.75rem;
    text-align: center;
    border-right: 1px solid #e1e4ea;
    border-bottom: 1px solid #e1e4ea;
    white-space: nowrap;
}
.psir-guide-table th {
    background: #f3f5f8;
    font-size: 1.15rem;
    font-weight: 750;
}
.psir-guide-table td {
    font-size: 1.22rem;
    font-weight: 700;
}
.psir-guide-table th:first-child,
.psir-guide-table td:first-child {
    text-align: left;
    font-weight: 750;
}
.psir-guide-table th:last-child,
.psir-guide-table td:last-child {
    border-right: 0;
}
.psir-guide-table tbody tr:last-child td {
    border-bottom: 0;
}
.null-ti-difference {
    display: inline-flex;
    flex-direction: column;
    gap: 0.15rem;
    margin-top: 0.25rem;
    padding: 0.45rem 0.8rem;
    border-left: 4px solid #4f6fa8;
    border-radius: 0.35rem;
    background: #eef2f8;
    color: #252a34;
}
.null-ti-difference span {
    font-size: 0.95rem;
    font-weight: 650;
}
.null-ti-difference strong {
    font-size: 1.25rem;
    line-height: 1.15;
}
.null-reference-stack {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.45rem;
    margin-top: 0.25rem;
}
.null-reference-stack .null-ti-difference {
    margin-top: 0;
}
.null-reference-stack small {
    color: #5f6672;
    font-size: 0.78rem;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("心臓MRI 正常心筋TI–信号強度シミュレータ")
st.caption("3 T・ガドビスト分割投与モデル")
st.info(
    "TI scoutで正常心筋のnull位置を確認し、PSIR LGEのTI設定を考えるための"
    "教育用シミュレータ"
)
st.warning(
    "本アプリは、文献値および施設経験値に基づく教育・施設内検討用"
    "シミュレータです。患者個別の最適TIや造影剤投与量を決定するものでは"
    "ありません。表示される信号値は正規化された相対値であり、実機の"
    "DICOM信号値を再現するものではありません。"
)

st.button("初期値に戻す", on_click=reset_defaults)

st.subheader("入力条件")
st.caption(
    "TI scoutおよびPSIRの撮像時刻は、インジェクターの2回目造影剤注入開始を"
    "0分とした経過時間です。"
)
input_columns = st.columns(3)
with input_columns[0]:
    weight = st.number_input(
        "設定体重［kg］",
        min_value=config.MIN_WEIGHT_KG,
        max_value=config.MAX_WEIGHT_KG,
        step=config.WEIGHT_STEP_KG,
        key="weight",
        format="%.0f",
    )
with input_columns[1]:
    st.number_input(
        "TI scout撮像時刻［2回目注入後 min］",
        min_value=config.MIN_SCOUT_TIME_AFTER_SECOND_MIN,
        max_value=config.MAX_SCOUT_TIME_AFTER_SECOND_MIN,
        step=config.SCOUT_TIME_AFTER_SECOND_STEP_MIN,
        key="scout_time_after_second",
        format="%.1f",
    )
with input_columns[2]:
    st.number_input(
        "PSIR撮像開始時刻［2回目注入後 min］",
        min_value=config.MIN_PSIR_TIME_AFTER_SECOND_MIN,
        max_value=config.MAX_PSIR_TIME_AFTER_SECOND_MIN,
        step=config.PSIR_TIME_AFTER_SECOND_STEP_MIN,
        key="psir_time_after_second",
        format="%.1f",
    )
with st.expander("詳細設定", expanded=False):
    t1_columns = st.columns(2)
    with t1_columns[0]:
        st.number_input(
            "正常心筋native T1［ms］",
            min_value=config.MIN_NATIVE_T1_MS,
            max_value=config.MAX_NATIVE_T1_MS,
            step=config.NATIVE_T1_STEP_MS,
            key="native_t1",
            format="%.0f",
        )
    with t1_columns[1]:
        st.number_input(
            "血液native T1［ms］",
            min_value=config.MIN_NATIVE_BLOOD_T1_MS,
            max_value=config.MAX_NATIVE_BLOOD_T1_MS,
            step=config.NATIVE_BLOOD_T1_STEP_MS,
            key="native_blood_t1",
            format="%.0f",
        )

    detail_columns = st.columns(5)
    with detail_columns[0]:
        st.number_input("A_PK", step=0.00001, key="a_pk", format="%.5f")
        st.number_input(
            "k［min⁻¹］", step=0.000001, key="washout_rate", format="%.6f"
        )
    with detail_columns[1]:
        st.number_input(
            "r1［mM⁻¹s⁻¹］", step=0.1, key="relaxivity", format="%.1f"
        )
        st.number_input(
            "施設校正値［ms］", step=1.0, key="facility_offset", format="%.0f"
        )
    with detail_columns[2]:
        st.number_input("TI表示最小値［ms］", step=1.0, key="ti_min")
        st.number_input("TI表示最大値［ms］", step=1.0, key="ti_max")
    with detail_columns[3]:
        st.number_input("TI計算刻み［ms］", step=1.0, key="ti_step")
        st.write(f"2回目注入時刻（固定）：{config.SECOND_INJECTION_TIME_MIN:.1f} min")
    with detail_columns[4]:
        st.number_input("A_blood", step=0.00001, key="a_blood", format="%.5f")
        st.number_input(
            "k_blood［min⁻¹］",
            step=0.00001,
            key="blood_washout_rate",
            format="%.5f",
        )
        st.number_input(
            "r1_blood［mM⁻¹s⁻¹］",
            step=0.1,
            key="blood_relaxivity",
            format="%.1f",
        )
        st.number_input(
            "血液専用施設校正値［ms］",
            min_value=config.MIN_BLOOD_FACILITY_OFFSET_MS,
            max_value=config.MAX_BLOOD_FACILITY_OFFSET_MS,
            step=config.BLOOD_FACILITY_OFFSET_STEP_MS,
            key="blood_facility_offset",
            format="%.0f",
        )

reference_changed = any(
    not math.isclose(current, default)
    for current, default in (
        (st.session_state.a_pk, config.DEFAULT_A_PK),
        (st.session_state.washout_rate, config.DEFAULT_WASHOUT_RATE_PER_MIN),
        (st.session_state.relaxivity, config.DEFAULT_RELAXIVITY_PER_MMOL_L_S),
    )
)
if reference_changed:
    st.warning(
        "文献参照モデルの係数が初期値から変更されています。"
        "表示結果は初版の基準モデルとは異なります。"
    )
blood_reference_changed = any(
    not math.isclose(current, default)
    for current, default in (
        (st.session_state.a_blood, config.DEFAULT_A_BLOOD),
        (
            st.session_state.blood_washout_rate,
            config.DEFAULT_BLOOD_WASHOUT_RATE_PER_MIN,
        ),
        (
            st.session_state.blood_relaxivity,
            config.DEFAULT_BLOOD_RELAXIVITY_PER_MMOL_L_S,
        ),
    )
)
if blood_reference_changed:
    st.warning("血液参照モデルの係数が初期値から変更されています。")
if not math.isclose(
    st.session_state.facility_offset, config.DEFAULT_FACILITY_OFFSET_MS
):
    st.warning(
        "施設校正値が初期値から変更されています。推定null TIおよび"
        "信号曲線に変更が反映されています。"
    )
if not math.isclose(
    st.session_state.blood_facility_offset,
    config.DEFAULT_BLOOD_FACILITY_OFFSET_MS,
):
    st.warning("血液専用施設校正値が初期値から変更されています。")

try:
    result = calculate_display_result(weight)
    illustration_signal = calculate_signal_at_ti(
        result.corrected_null_ti_ms, st.session_state.illustration_ti
    )
    illustration_blood_signal = calculate_signal_at_ti(
        result.corrected_blood_null_ti_ms, st.session_state.illustration_ti
    )
except ValueError as error:
    st.error(str(error))
    st.stop()

render_injection_table(result)

display_columns = st.columns([1.65, 1.0], gap="large")
with display_columns[0]:
    render_signal_graph(
        result,
        st.session_state.illustration_ti,
        illustration_signal,
        illustration_blood_signal,
    )

with display_columns[1]:
    st.subheader("左室短軸像")
    illustration_control_columns = st.columns([1, 1, 1.4, 1, 1])
    with illustration_control_columns[0]:
        st.button(
            f"← {config.ILLUSTRATION_TI_LARGE_STEP_MS:.0f}",
            on_click=decrease_illustration_ti_30,
            disabled=(
                st.session_state.illustration_ti <= config.MIN_ILLUSTRATION_TI_MS
            ),
            width="stretch",
        )
    with illustration_control_columns[1]:
        st.button(
            f"← {config.ILLUSTRATION_TI_STEP_MS:.0f}",
            on_click=decrease_illustration_ti,
            disabled=(
                st.session_state.illustration_ti <= config.MIN_ILLUSTRATION_TI_MS
            ),
            width="stretch",
        )
    with illustration_control_columns[2]:
        st.markdown(
            f"<h3 style='text-align:center;margin-top:0.2rem'>"
            f"TI：{st.session_state.illustration_ti:.0f} ms</h3>",
            unsafe_allow_html=True,
        )
    with illustration_control_columns[3]:
        st.button(
            f"{config.ILLUSTRATION_TI_STEP_MS:.0f} →",
            on_click=increase_illustration_ti,
            disabled=(
                st.session_state.illustration_ti >= config.MAX_ILLUSTRATION_TI_MS
            ),
            width="stretch",
        )
    with illustration_control_columns[4]:
        st.button(
            f"{config.ILLUSTRATION_TI_LARGE_STEP_MS:.0f} →",
            on_click=increase_illustration_ti_30,
            disabled=(
                st.session_state.illustration_ti >= config.MAX_ILLUSTRATION_TI_MS
            ),
            width="stretch",
        )

    render_illustration_column(
        result,
        st.session_state.illustration_ti,
        illustration_signal,
        illustration_blood_signal,
    )

st.subheader("主要結果")
render_primary_result(result)
st.caption(
    f"TI scout：2回目注入後{st.session_state.scout_time_after_second:.1f} min ／ "
    f"TI scout：1回目注入後"
    f"{st.session_state.scout_time_after_second + config.SECOND_INJECTION_TIME_MIN:.1f} min ／ "
    f"PSIR開始：2回目注入後{st.session_state.psir_time_after_second:.1f} min ／ "
    f"PSIR開始：1回目注入後"
    f"{st.session_state.psir_time_after_second + config.SECOND_INJECTION_TIME_MIN:.1f} min ／ "
    f"心筋native T1：{st.session_state.native_t1:.0f} ms ／ "
    f"血液native T1：{st.session_state.native_blood_t1:.0f} ms ／ 磁場強度：3 T"
)
render_psir_ti_guide(result)

with st.expander("計算詳細", expanded=False):
    render_detail(result)

with st.expander("自施設の投与プロトコル"):
    protocol = pd.DataFrame(
        {
            "条件": [
                "用途",
                "注入開始時刻",
                "目標投与量",
                "上限",
                "ガドビスト注入速度",
                "生理食塩水量",
                "生理食塩水注入速度",
            ],
            "1回目": [
                "perfusion",
                f"{config.FIRST_INJECTION_TIME_MIN:.1f} min",
                f"{config.FIRST_DOSE_MMOL_PER_KG:.2f} mmol/kg",
                "—",
                f"{config.CONTRAST_INJECTION_RATE_ML_S:.1f} mL/s",
                f"{config.FIRST_SALINE_VOLUME_ML:.0f} mL",
                f"{config.SALINE_INJECTION_RATE_ML_S:.1f} mL/s",
            ],
            "2回目": [
                "LGE用追加投与",
                f"{config.SECOND_INJECTION_TIME_MIN:.1f} min",
                f"{config.SECOND_TARGET_DOSE_MMOL_PER_KG:.2f} mmol/kg",
                f"総量{config.MAX_TOTAL_VOLUME_ML:.0f} mLまで",
                f"{config.CONTRAST_INJECTION_RATE_ML_S:.1f} mL/s",
                f"約{config.SECOND_SALINE_VOLUME_ML:.0f} mL",
                f"{config.SALINE_INJECTION_RATE_ML_S:.1f} mL/s",
            ],
        }
    )
    st.dataframe(protocol, hide_index=True, width="stretch")
    st.caption(
        "薬物動態計算では、各ガドビスト投与を注入開始時刻における"
        "瞬時投与として近似しています。"
    )

with st.expander("モデル説明"):
    st.markdown(
        """
- `A_PK`と`k`は、文献の平均心筋内見かけ濃度データから本アプリ用に算出した係数です。
- 表示濃度はT1から換算した見かけ濃度であり、真の組織濃度ではありません。
- 文献条件を超える投与量への適用には線形外挿が含まれます。
- 推定null TIには暫定的な施設校正値を使用しています。
- 信号曲線は正規化されたMagnitude相対信号で、実測DICOM信号値ではありません。
- 本アプリはMagnitude TI scoutの信号曲線を簡略表示するもので、PSIR画像そのものの信号を再現するものではありません。
- 実機固有のLook-Locker挙動、患者の腎機能・心拍出量などは反映していません。
- 入力値や計算結果を保存せず、患者を特定できる情報も扱いません。
- 本モデルは教育・施設内検討用であり、臨床的な個人予測や推奨を保証しません。
"""
    )
