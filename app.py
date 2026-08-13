"""Streamlit 기반 만성 신장질환 위험 선별 시제품 화면."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from pathlib import Path

from src.model_logic import (
    InputValidationError,
    get_reference_profile,
    interpret_confirmation_tests,
    load_model_config,
    load_reference_profiles,
    predict_batch,
    predict_single,
    read_uploaded_table,
)


st.set_page_config(
    page_title="신장 이상 위험 선별 시제품",
    page_icon="🩺",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main-title {font-size: 2.05rem; font-weight: 700; color: #0F766E; margin-bottom: 0.1rem;}
    .sub-title {font-size: 1.05rem; color: #475569; margin-bottom: 1rem;}
    .result-positive {padding: 1.1rem; border-radius: 0.6rem; background: #FFF7ED; border-left: 0.4rem solid #EA580C;}
    .result-negative {padding: 1.1rem; border-radius: 0.6rem; background: #F0FDFA; border-left: 0.4rem solid #0F766E;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_config() -> dict:
    return load_model_config()


@st.cache_data
def get_reference_profiles() -> dict:
    """개별 화면의 연령·성별 참고집단 집계 통계를 불러옴."""
    return load_reference_profiles()


def result_box(prediction: dict) -> None:
    """개별 분석 결과를 위험확률과 함께 표시함."""
    risk_percent = prediction["risk_probability"] * 100
    if prediction["screening_positive"]:
        st.markdown(
            f"""
            <div class="result-positive">
            <b>추가 신장기능 검사 권고</b><br>
            현재 입력값 기준 선별 위험확률은 <b>{risk_percent:.1f}%</b>임.
            eGFR·UACR 등 확인 검사를 의료진과 상의하는 것이 필요함.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="result-negative">
            <b>현재 기준상 낮은 선별 위험</b><br>
            현재 입력값 기준 선별 위험확률은 <b>{risk_percent:.1f}%</b>임.
            이 결과만으로 신장질환이 없다고 확정할 수는 없음.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if prediction["missing_inputs"]:
        st.warning(
            "다음 입력값은 비어 있어 학습자료 중앙값으로 대치했음: "
            + ", ".join(prediction["missing_inputs"])
        )


def to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    """한글이 깨지지 않도록 UTF-8 BOM 형식의 CSV를 만듦."""
    return dataframe.to_csv(index=False).encode("utf-8-sig")


def make_input_summary(
    age_years: int,
    sex: str,
    mean_sbp: float,
    mean_dbp: float,
    hemoglobin: float,
    hba1c: float,
) -> pd.DataFrame:
    """환자가 입력한 선별검사 정보를 한눈에 볼 수 있게 정리함."""
    return pd.DataFrame(
        [
            ["연령", f"{age_years}", "세"],
            ["성별", sex, ""],
            ["평균 수축기혈압", f"{mean_sbp:.1f}", "mmHg"],
            ["평균 이완기혈압", f"{mean_dbp:.1f}", "mmHg"],
            ["헤모글로빈", f"{hemoglobin:.1f}", "g/dL"],
            ["당화혈색소", f"{hba1c:.1f}", "%"],
        ],
        columns=["검사 지표", "입력값", "단위"],
    )


def make_global_importance_table(config: dict) -> pd.DataFrame:
    """전체 모델에서 각 입력변수의 상대적 계수 크기를 표시함."""
    rows = []
    for specification in config["input_specifications"]:
        feature_name = specification["model_feature"]
        coefficient = float(config["coefficients_standardized"][feature_name])
        rows.append(
            {
                "검사 지표": specification["label"],
                "표준화 계수": coefficient,
                "상대적 반영 크기": abs(coefficient),
                "방향": "값이 커질수록 위험확률 상승 방향" if coefficient > 0 else "값이 커질수록 위험확률 하락 방향",
            }
        )
    return pd.DataFrame(rows).sort_values("상대적 반영 크기", ascending=False, ignore_index=True)


def make_reference_comparison_table(reference_profile: dict, input_values: dict[str, float]) -> pd.DataFrame:
    """그래프의 수치 근거를 표로도 확인할 수 있게 정리함."""
    rows = []
    for key, input_value in input_values.items():
        metric = reference_profile["metrics"][key]
        rows.append(
            {
                "검사 지표": f"{metric['label']} ({metric['unit']})",
                "현재 입력값": input_value,
                "참고집단 평균": metric["mean"],
                "참고 범위(25~75백분위)": f"{metric['q25']:.1f} ~ {metric['q75']:.1f}",
                "해당 지표 표본 수": metric["n"],
            }
        )
    return pd.DataFrame(rows)


def make_reference_comparison_chart(reference_profile: dict, input_values: dict[str, float]):
    """환자 입력값과 같은 연령대·성별 참고집단 분포를 한 화면에 비교함."""
    rows = []
    for key, input_value in input_values.items():
        metric = reference_profile["metrics"][key]
        rows.append(
            {
                "검사 지표": f"{metric['label']} ({metric['unit']})",
                "입력값": float(input_value),
                "참고집단 평균": metric["mean"],
                "참고범위 하한": metric["q25"],
                "참고범위 상한": metric["q75"],
                "표본 수": metric["n"],
            }
        )

    comparison = pd.DataFrame(rows)
    sort_order = comparison["검사 지표"].tolist()
    base = alt.Chart(comparison)
    reference_range = base.mark_rule(color="#CBD5E1", strokeWidth=16).encode(
        x=alt.X("참고범위 하한:Q", title=None, scale=alt.Scale(zero=False)),
        x2="참고범위 상한:Q",
        y=alt.value(30),
    )
    reference_mean = base.mark_tick(color="#0F766E", thickness=3, size=26).encode(
        x=alt.X("참고집단 평균:Q", title=None, scale=alt.Scale(zero=False)),
        y=alt.value(30),
    )
    patient_value = base.mark_point(color="#EA580C", filled=True, size=105).encode(
        x=alt.X("입력값:Q", title=None, scale=alt.Scale(zero=False)),
        y=alt.value(30),
        tooltip=[
            alt.Tooltip("검사 지표:N", title="검사 지표"),
            alt.Tooltip("입력값:Q", title="현재 입력값", format=".1f"),
            alt.Tooltip("참고집단 평균:Q", title="참고집단 평균", format=".1f"),
            alt.Tooltip("참고범위 하한:Q", title="참고범위 하한(25백분위)", format=".1f"),
            alt.Tooltip("참고범위 상한:Q", title="참고범위 상한(75백분위)", format=".1f"),
            alt.Tooltip("표본 수:Q", title="참고 표본 수"),
        ],
    )
    return (
        alt.layer(reference_range, reference_mean, patient_value)
        .properties(height=58)
        .facet(
            row=alt.Row(
                "검사 지표:N",
                sort=sort_order,
                title=None,
                header=alt.Header(labelAngle=0, labelFontSize=13, labelFontWeight="bold"),
            )
        )
        .resolve_scale(x="independent")
    )


@st.cache_data
def load_excel_template() -> bytes:
    """다인 분석용 Excel 입력 양식 파일을 내려받기용으로 읽음."""
    template_path = Path(__file__).resolve().parent / "ckd_screening_input_template.xlsx"
    return template_path.read_bytes()


config = get_config()
reference_profiles = get_reference_profiles()

st.markdown('<div class="main-title">신장 이상 위험 선별 시제품</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">NHANES 2021–2023 공개자료 기반 연구용 기준모델 · 확진·진단 용도 아님</div>',
    unsafe_allow_html=True,
)
st.warning(
    "중요: 이 프로그램은 한 번의 검사 시점에서 신장 이상 가능성을 선별하는 시제품임. "
    "결과만으로 만성 신장질환을 진단하거나 치료를 결정하면 안 되며, 의료진 판단과 확인검사가 필요함."
)

tab_single, tab_batch, tab_info = st.tabs(["개별 선별", "다인 일괄분석", "모델 정보·주의사항"])

with tab_single:
    st.subheader("환자 1명 선별")
    st.caption("혈압은 가능하면 같은 날 2~3회 측정한 평균값을 입력함.")
    with st.form("single_screening_form"):
        left, right = st.columns(2)
        with left:
            age_years = st.number_input("연령 (세)", min_value=18, max_value=120, value=56, step=1)
            sex = st.radio("성별", options=["남성", "여성"], horizontal=True)
            mean_sbp = st.number_input("평균 수축기혈압 (mmHg)", min_value=50.0, max_value=260.0, value=120.0, step=1.0)
        with right:
            mean_dbp = st.number_input("평균 이완기혈압 (mmHg)", min_value=30.0, max_value=160.0, value=74.0, step=1.0)
            hemoglobin = st.number_input("헤모글로빈 (g/dL)", min_value=3.0, max_value=25.0, value=14.0, step=0.1)
            hba1c = st.number_input("당화혈색소 (HbA1c, %)", min_value=3.0, max_value=20.0, value=5.5, step=0.1)
        with st.expander("확인 검사값 입력 (선택)"):
            st.caption("eGFR과 UACR은 위험확률 계산에는 사용하지 않고, 검사상 이상 소견만 별도로 해석함.")
            check_left, check_right = st.columns(2)
            with check_left:
                egfr_input = st.text_input("eGFR (mL/min/1.73m², 선택)", placeholder="예: 85")
            with check_right:
                uacr_input = st.text_input("UACR (mg/g, 선택)", placeholder="예: 12")
        submitted = st.form_submit_button("위험 선별 결과 확인", type="primary")

    if submitted:
        try:
            prediction = predict_single(
                {
                    "age_years": age_years,
                    "female": sex,
                    "mean_sbp_mmhg": mean_sbp,
                    "mean_dbp_mmhg": mean_dbp,
                    "hemoglobin_g_dl": hemoglobin,
                    "hba1c_percent": hba1c,
                },
                config,
            )
            first, second, third = st.columns(3)
            first.metric("선별 위험확률", f"{prediction['risk_probability'] * 100:.1f}%")
            second.metric("선별 임계값", f"{prediction['threshold'] * 100:.1f}%")
            third.metric("모델 버전", prediction["model_version"])
            result_box(prediction)
            st.subheader("환자별 입력 검사 결과")
            st.dataframe(
                make_input_summary(age_years, sex, mean_sbp, mean_dbp, hemoglobin, hba1c),
                use_container_width=True,
                hide_index=True,
            )

            reference_profile = get_reference_profile(age_years, sex, reference_profiles)
            reference_input_values = {
                "mean_sbp_mmhg": mean_sbp,
                "mean_dbp_mmhg": mean_dbp,
                "hemoglobin_g_dl": hemoglobin,
                "hba1c_percent": hba1c,
            }
            st.subheader("같은 연령대·성별 참고집단과의 비교")
            st.caption(
                f"{reference_profile['sex_label']} {reference_profile['age_band']} 참고집단 "
                f"(n={reference_profile['group_n']:,}) · 주황 점: 현재 입력값 · "
                "청록 선: 참고집단 평균 · 회색 막대: 25~75백분위 범위"
            )
            st.altair_chart(
                make_reference_comparison_chart(reference_profile, reference_input_values),
                use_container_width=True,
            )
            st.dataframe(
                make_reference_comparison_table(reference_profile, reference_input_values),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "참고집단은 CDC NHANES 2021–2023 성인 중 eGFR 60 이상 및 UACR 30 mg/g 미만인 "
                "사람의 집계 통계임. 미국 자료 기반의 비교 참고치이며, 개인의 건강 여부나 질병을 진단하지 않음."
            )

            st.subheader("입력값별 모델 반영 방향")
            contributions = pd.DataFrame(prediction["feature_contributions"])
            contributions = contributions.sort_values("contribution_to_model_score", key=lambda values: values.abs(), ascending=False)
            contributions = contributions.rename(
                columns={
                    "indicator": "검사 지표",
                    "input_value": "모델에 사용된 값",
                    "was_imputed": "결측 대치 여부",
                    "contribution_to_model_score": "모델 점수 기여도",
                    "direction": "반영 방향",
                }
            )
            contributions["결측 대치 여부"] = contributions["결측 대치 여부"].map({True: "대치함", False: "입력값 사용"})
            st.bar_chart(contributions.set_index("검사 지표")["모델 점수 기여도"])
            st.dataframe(contributions, use_container_width=True, hide_index=True)
            st.caption(
                "모델 점수 기여도는 이 환자의 입력값이 학습자료 평균과 비교해 위험확률을 어느 방향으로 움직였는지 보여 주는 기술적 지표임. "
                "질병의 원인이나 임상적 중요도를 뜻하지 않음."
            )

            try:
                confirmation = interpret_confirmation_tests(egfr_input, uacr_input)
                if confirmation["provided"]:
                    st.subheader("eGFR·UACR 확인 검사 해석")
                    check_one, check_two, check_three = st.columns(3)
                    check_one.metric("eGFR", f"{confirmation['egfr']:.1f}" if confirmation["egfr"] is not None else "미입력")
                    check_two.metric("UACR", f"{confirmation['uacr']:.1f}" if confirmation["uacr"] is not None else "미입력")
                    check_three.metric(
                        "단일 검사 시점 이상 소견",
                        "있음" if confirmation["single_visit_abnormality"] else "현재 기준 미충족",
                    )
                    st.dataframe(
                        pd.DataFrame(
                            [
                                ["eGFR", confirmation["egfr_status"]],
                                ["UACR", confirmation["uacr_status"]],
                            ],
                            columns=["확인 항목", "해석"],
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )
                    if confirmation["single_visit_abnormality"]:
                        st.error(confirmation["interpretation"])
                    else:
                        st.info(confirmation["interpretation"])
                    st.caption("이 항목은 CKD 확진 여부가 아니라 단일 검사 시점의 이상 소견을 표시함.")
            except InputValidationError as confirmation_error:
                st.error(f"확인 검사값 입력 오류: {confirmation_error}")
            st.caption("입력값은 이 화면의 결과 계산에만 사용하며 프로그램 내부에 저장하지 않음.")
        except InputValidationError as error:
            st.error(str(error))

with tab_batch:
    st.subheader("Excel 또는 CSV 파일 여러 명 일괄분석")
    st.write("한 행에 한 사람씩 입력한 Excel(.xlsx) 또는 CSV 파일을 올리면 여러 명을 동시에 선별함.")
    try:
        st.download_button(
            "다인 분석용 Excel 양식 다운로드",
            data=load_excel_template(),
            file_name="ckd_screening_input_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except FileNotFoundError:
        st.error("Excel 양식 파일을 찾지 못했음. 프로그램 폴더의 양식 파일을 확인해야 함.")
    with st.expander("Excel 입력 규격 보기"):
        st.markdown(
            """
            - 필수 열: `age_years`, `sex`
            - 선택 열: `patient_id`, `mean_sbp_mmhg`, `mean_dbp_mmhg`, `hemoglobin_g_dl`, `hba1c_percent`
            - 확인 검사 선택 열: `egfr_optional`, `uacr_optional`
            - `patient_id`에는 성명·주민등록번호·연락처 대신 익명 관리번호만 입력함.
            - eGFR·UACR은 위험확률 계산에는 쓰지 않고, 단일 검사 시점 이상 소견을 별도로 표시함.
            """
        )
    uploaded_file = st.file_uploader("분석할 Excel 또는 CSV 파일 선택", type=["xlsx", "csv"])
    if uploaded_file is not None:
        try:
            uploaded = read_uploaded_table(uploaded_file)
            result, warnings = predict_batch(uploaded, config)
            successful = result["input_error"].eq("").sum()
            failed = len(result) - successful
            screening_positive = result["screening_result"].eq("추가 신장기능 검사 권고").sum()
            confirmation_abnormal = result["confirmation_test_status"].eq("단일 검사 시점 이상 소견 있음").sum()
            one, two, three, four = st.columns(4)
            one.metric("분석 성공", f"{successful:,}건")
            two.metric("입력 오류", f"{failed:,}건")
            three.metric("추가 검사 권고", f"{screening_positive:,}건")
            four.metric("확인검사 이상 소견", f"{confirmation_abnormal:,}건")
            display_columns = [
                column for column in [
                    "patient_id", "age_years", "sex", "risk_percent", "screening_result",
                    "confirmation_test_status", "egfr_test_interpretation", "uacr_test_interpretation",
                    "imputed_missing_inputs", "input_error",
                ] if column in result.columns
            ]
            result_display = result[display_columns].rename(
                columns={
                    "patient_id": "익명 관리번호", "age_years": "연령", "sex": "성별",
                    "risk_percent": "선별 위험확률(%)", "screening_result": "선별 결과",
                    "confirmation_test_status": "확인검사 상태", "egfr_test_interpretation": "eGFR 해석",
                    "uacr_test_interpretation": "UACR 해석", "imputed_missing_inputs": "대치된 결측값",
                    "input_error": "입력 오류",
                }
            )
            st.dataframe(result_display, use_container_width=True, hide_index=True)
            st.download_button(
                "전체 분석 결과 CSV 다운로드",
                data=to_csv_bytes(result),
                file_name="ckd_screening_result.csv",
                mime="text/csv",
            )
            for warning in warnings:
                st.info(warning)
        except (InputValidationError, UnicodeDecodeError, pd.errors.ParserError) as error:
            st.error(f"CSV 분석 중 문제가 발생함: {error}")

with tab_info:
    st.subheader("모델의 목적과 한계")
    st.markdown(
        """
        - **학습자료:** 미국 CDC NHANES 2021–2023 공개자료의 성인 5,552명임.
        - **선별 정답값:** 단일 검사 시점의 `eGFR < 60` 또는 `UACR ≥ 30 mg/g`임.
        - **입력변수:** 연령, 성별, 평균 수축기·이완기혈압, 헤모글로빈, 당화혈색소임.
        - **제외변수:** 혈청 크레아티닌, 소변 알부민·크레아티닌, UACR, 계산 eGFR은 정답값 구성에 쓰이므로 입력에서 제외함.
        - **성능:** 독립 테스트 자료에서 민감도 약 79.5%, 음성예측도 약 93.0%였음.
        - **중요 한계:** 미국 자료로 학습했으며, 연령대별 성능 차이가 확인됐음. 한국 적용 전 국내자료 외부검증·재보정·재학습이 필요함.
        """
    )
    st.subheader("모델 전체의 주요 검사 지표 반영 크기")
    global_importance = make_global_importance_table(config)
    st.dataframe(global_importance, use_container_width=True, hide_index=True)
    st.bar_chart(global_importance.set_index("검사 지표")["상대적 반영 크기"])
    st.caption("표준화 계수의 절댓값을 비교한 기술적 지표임. 질병 원인 또는 임상적 우선순위를 의미하지 않음.")
    st.subheader("개인정보 보호 안내")
    st.write(
        "이 시제품은 입력값을 별도 파일이나 서버에 저장하지 않도록 설계했음. "
        "다만 실제 환자정보를 다룰 때는 성명·주민등록번호·연락처 등 식별정보를 입력하지 말고, "
        "기관의 개인정보보호 및 보안 절차를 따라야 함."
    )
    with st.expander("기술 설정 보기"):
        st.json(
            {
                "model_version": config["model_version"],
                "selected_threshold": config["selected_threshold"],
                "input_features": [spec["label"] for spec in config["input_specifications"]],
            }
        )
