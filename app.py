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
    ConcentrationResult,
    DoseResult,
    calculate_apparent_myocardial_concentration,
    calculate_corrected_null_ti,
    calculate_dose,
    calculate_ideal_null_ti,
    calculate_post_contrast_t1,
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


DEFAULT_STATE = {
    "weight_a": config.DEFAULT_WEIGHT_A_KG,
    "weight_b": config.DEFAULT_WEIGHT_B_KG,
    "scout_time": config.DEFAULT_SCOUT_TIME_MIN,
    "psir_time": config.DEFAULT_PSIR_TIME_MIN,
    "illustration_ti": config.DEFAULT_ILLUSTRATION_TI_MS,
    "native_t1": config.DEFAULT_NATIVE_T1_MS,
    "a_pk": config.DEFAULT_A_PK,
    "washout_rate": config.DEFAULT_WASHOUT_RATE_PER_MIN,
    "relaxivity": config.DEFAULT_RELAXIVITY_PER_MMOL_L_S,
    "facility_offset": config.DEFAULT_FACILITY_OFFSET_MS,
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


def calculate_display_result(weight_kg: float) -> DisplayResult:
    """既存モデルを両撮像時刻へ適用し、1体重分の表示結果を計算する。"""

    dose = calculate_dose(weight_kg)
    psir_time = validate_psir_time(
        st.session_state.psir_time, st.session_state.scout_time
    )
    concentration = calculate_apparent_myocardial_concentration(
        weight_kg,
        st.session_state.scout_time,
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
    )


def render_primary_result_column(label: str, result: DisplayResult) -> None:
    """1体重分の主要結果を表示する。"""

    st.subheader(f"体重{label}：{result.weight_kg:.0f} kg")
    st.metric(
        "総投与量",
        f"{result.dose.total_dose_mmol_per_kg:.3f} mmol/kg",
    )
    st.metric(
        "TI scout時点の推定正常心筋null TI",
        f"{result.corrected_null_ti_ms:.0f} ms",
    )
    st.metric(
        "PSIR開始時点の推定正常心筋null TI",
        f"{result.psir_corrected_null_ti_ms:.0f} ms",
    )
    st.metric("null TIの推定変化量", f"{result.null_ti_change_ms:+.0f} ms")


def render_detail_column(label: str, result: DisplayResult) -> None:
    """1体重分の計算詳細表を表示する。"""

    st.markdown(f"#### 体重{label}：{result.weight_kg:.0f} kg")
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
            ],
        }
    )
    st.dataframe(details, hide_index=True, width="stretch")
    st.caption(
        "このT1値は、LGE撮像で設定するInversion Time（TI）ではありません。"
    )


def render_illustration_column(
    label: str,
    result: DisplayResult,
    display_ti_ms: float,
    signal_percent: float,
) -> None:
    """1体重分の左室短軸模式図と選択TIの数値を表示する。"""

    st.markdown(f"#### 体重{label}")
    pattern_id = f"lv-cavity-hatch-{label.lower()}"
    svg = generate_lv_short_axis_svg(signal_percent, pattern_id)
    components.html(
        f"""<div style="width:100%;height:240px;display:flex;align-items:center;justify-content:center;background:transparent;overflow:hidden">
{svg}
</div>""",
        height=250,
        scrolling=False,
    )
    st.markdown(
        f"""
- 体重：{result.weight_kg:.0f} kg
- 表示TI：{display_ti_ms:.0f} ms
- 正常心筋相対信号：{signal_percent:.1f} %
- 推定null TI：{result.corrected_null_ti_ms:.0f} ms
"""
    )
    st.caption("左室内腔：未モデル化")


def render_signal_graph(
    result_a: DisplayResult,
    result_b: DisplayResult,
    illustration_ti_ms: float,
    illustration_signal_a: float,
    illustration_signal_b: float,
) -> None:
    """2体重のMagnitude TI–信号強度曲線とnull位置を表示する。"""

    figure = go.Figure()
    colors = {"A": "#1f77b4", "B": "#d62728"}
    selected_signals = {
        "A": illustration_signal_a,
        "B": illustration_signal_b,
    }
    for label, result in (("A", result_a), ("B", result_b)):
        name = (
            f"体重{label} {result.weight_kg:.0f} kg "
            f"({result.dose.total_dose_mmol_per_kg:.3f} mmol/kg)"
        )
        figure.add_trace(
            go.Scatter(
                x=result.ti_values_ms,
                y=result.signal_percent,
                mode="lines",
                name=name,
                line={"color": colors[label], "width": 3},
                hovertemplate="TI: %{x:.0f} ms<br>相対信号: %{y:.1f}%<extra>%{fullData.name}</extra>",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[result.corrected_null_ti_ms],
                y=[0.0],
                mode="markers+text",
                name=f"体重{label} null",
                marker={"color": colors[label], "size": 10, "symbol": "circle"},
                text=[f"推定null TI：{result.corrected_null_ti_ms:.0f} ms"],
                textposition="top center",
                showlegend=False,
                hovertemplate=(
                    f"体重{label}<br>推定null TI："
                    "%{x:.0f} ms<extra></extra>"
                ),
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[illustration_ti_ms],
                y=[selected_signals[label]],
                mode="markers",
                name=f"体重{label} イラスト表示TI",
                marker={"color": colors[label], "size": 11, "symbol": "diamond"},
                showlegend=False,
                hovertemplate=(
                    f"体重{label}<br>イラスト表示TI：%{{x:.0f}} ms"
                    "<br>相対信号：%{y:.1f}%<extra></extra>"
                ),
            )
        )
        figure.add_vline(
            x=result.corrected_null_ti_ms,
            line_color=colors[label],
            line_dash="dash",
            line_width=1.5,
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
        title="TI scoutにおける正常心筋Magnitude信号曲線",
        xaxis_title="Inversion Time（TI）［ms］",
        yaxis_title="正常心筋の正規化Magnitude信号［%］",
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
input_columns = st.columns(5)
with input_columns[0]:
    weight_a = st.number_input(
        "比較体重A［kg］",
        min_value=config.MIN_WEIGHT_KG,
        max_value=config.MAX_WEIGHT_KG,
        step=config.WEIGHT_STEP_KG,
        key="weight_a",
    )
with input_columns[1]:
    weight_b = st.number_input(
        "比較体重B［kg］",
        min_value=config.MIN_WEIGHT_KG,
        max_value=config.MAX_WEIGHT_KG,
        step=config.WEIGHT_STEP_KG,
        key="weight_b",
    )
with input_columns[2]:
    st.number_input(
        "TI scout撮像時刻［min］",
        min_value=config.MIN_SCOUT_TIME_MIN,
        max_value=config.MAX_SCOUT_TIME_MIN,
        step=config.SCOUT_TIME_STEP_MIN,
        key="scout_time",
        format="%.1f",
    )
with input_columns[3]:
    st.number_input(
        "PSIR撮像開始時刻［min］",
        min_value=config.MIN_PSIR_TIME_MIN,
        max_value=config.MAX_PSIR_TIME_MIN,
        step=config.PSIR_TIME_STEP_MIN,
        key="psir_time",
        format="%.1f",
    )
with input_columns[4]:
    st.number_input(
        "正常心筋native T1［ms］",
        min_value=config.MIN_NATIVE_T1_MS,
        max_value=config.MAX_NATIVE_T1_MS,
        step=config.NATIVE_T1_STEP_MS,
        key="native_t1",
        format="%.0f",
    )

with st.expander("詳細設定", expanded=False):
    detail_columns = st.columns(4)
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
if not math.isclose(
    st.session_state.facility_offset, config.DEFAULT_FACILITY_OFFSET_MS
):
    st.warning(
        "施設校正値が初期値から変更されています。推定null TIおよび"
        "信号曲線に変更が反映されています。"
    )

try:
    result_a = calculate_display_result(weight_a)
    result_b = calculate_display_result(weight_b)
    illustration_signal_a = calculate_signal_at_ti(
        result_a.corrected_null_ti_ms, st.session_state.illustration_ti
    )
    illustration_signal_b = calculate_signal_at_ti(
        result_b.corrected_null_ti_ms, st.session_state.illustration_ti
    )
except ValueError as error:
    st.error(str(error))
    st.stop()

st.subheader("主要結果")
result_columns = st.columns(2)
with result_columns[0]:
    render_primary_result_column("A", result_a)
with result_columns[1]:
    render_primary_result_column("B", result_b)

null_difference_ms = abs(
    result_a.corrected_null_ti_ms - result_b.corrected_null_ti_ms
)
st.caption(
    f"体重AとBのnull TI差：{null_difference_ms:.0f} ms ／ "
    f"TI scout：1回目注入後{st.session_state.scout_time:.1f} min ／ "
    f"TI scout：2回目注入後"
    f"{st.session_state.scout_time - config.SECOND_INJECTION_TIME_MIN:.1f} min ／ "
    f"PSIR開始：1回目注入後{st.session_state.psir_time:.1f} min ／ "
    f"native T1：{st.session_state.native_t1:.0f} ms ／ 磁場強度：3 T"
)

if math.isclose(
    result_a.dose.total_dose_mmol_per_kg,
    result_b.dose.total_dose_mmol_per_kg,
):
    st.info(
        "現在の条件では、体重Aと体重Bの体重当たり総投与量が同一であるため、"
        "2本の曲線は重なっています。"
    )

render_signal_graph(
    result_a,
    result_b,
    st.session_state.illustration_ti,
    illustration_signal_a,
    illustration_signal_b,
)

illustration_control_columns = st.columns([1, 1.4, 1])
with illustration_control_columns[0]:
    st.button(
        f"← {config.ILLUSTRATION_TI_STEP_MS:.0f} ms",
        on_click=decrease_illustration_ti,
        disabled=(
            st.session_state.illustration_ti <= config.MIN_ILLUSTRATION_TI_MS
        ),
        width="stretch",
    )
with illustration_control_columns[1]:
    st.markdown(
        f"<h3 style='text-align:center'>表示TI："
        f"{st.session_state.illustration_ti:.0f} ms</h3>",
        unsafe_allow_html=True,
    )
with illustration_control_columns[2]:
    st.button(
        f"{config.ILLUSTRATION_TI_STEP_MS:.0f} ms →",
        on_click=increase_illustration_ti,
        disabled=(
            st.session_state.illustration_ti >= config.MAX_ILLUSTRATION_TI_MS
        ),
        width="stretch",
    )

st.subheader("左室短軸イラスト")
illustration_columns = st.columns(2)
with illustration_columns[0]:
    render_illustration_column(
        "A",
        result_a,
        st.session_state.illustration_ti,
        illustration_signal_a,
    )
with illustration_columns[1]:
    render_illustration_column(
        "B",
        result_b,
        st.session_state.illustration_ti,
        illustration_signal_b,
    )

st.subheader("計算詳細")
detail_columns = st.columns(2)
with detail_columns[0]:
    render_detail_column("A", result_a)
with detail_columns[1]:
    render_detail_column("B", result_b)

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
