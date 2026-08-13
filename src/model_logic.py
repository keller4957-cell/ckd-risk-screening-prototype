"""신장 이상 위험 선별 시제품의 예측 로직.

이 모듈은 진단용이 아님. 한 번의 검사 시점에서 eGFR < 60 또는
UACR >= 30 mg/g일 가능성을 선별하는 연구용 기준모델임.
"""

from __future__ import annotations

import json
import math
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_DIR / "model_config.json"
DEFAULT_REFERENCE_PROFILE_PATH = PROJECT_DIR / "reference_profiles.json"


class InputValidationError(ValueError):
    """입력값이 모델이 허용하는 기본 범위를 벗어난 경우 발생함."""


def load_model_config(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """프로그램과 분리된 JSON 파일에서 모델 설정값을 불러옴."""
    with config_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_reference_profiles(profile_path: Path = DEFAULT_REFERENCE_PROFILE_PATH) -> dict[str, Any]:
    """연령·성별 참고집단의 집계 통계를 불러옴.

    이 파일에는 개인 단위 원자료가 아니라 연령대·성별·검사지표별 평균과
    25·75백분위수만 포함됨.
    """
    with profile_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_reference_profile(
    age_years: Any,
    sex: Any,
    reference_profiles: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """입력 연령·성별에 맞는 NHANES 참고집단 요약치를 반환함."""
    age = _as_optional_number(age_years, "연령")
    if age is None or not 18 <= age <= 120:
        raise InputValidationError("연령은 18~120세 범위로 입력해야 함.")

    profiles = reference_profiles or load_reference_profiles()
    sex_key = "female" if normalize_sex_to_female(sex) == 1.0 else "male"
    age_band_rules = (
        (18, 25, "18–24세"),
        (25, 35, "25–34세"),
        (35, 45, "35–44세"),
        (45, 55, "45–54세"),
        (55, 65, "55–64세"),
        (65, 75, "65–74세"),
        (75, 85, "75–84세"),
        (85, 121, "85세 이상"),
    )
    age_band = next(
        label for minimum, maximum, label in age_band_rules if minimum <= age < maximum
    )
    profile = profiles["profiles"][sex_key][age_band]

    return {
        "reference_name": profiles["reference_name"],
        "source": profiles["source"],
        "reference_definition": profiles["reference_definition"],
        "age_band_method": profiles["age_band_method"],
        "age_band": age_band,
        "sex_label": "여성" if sex_key == "female" else "남성",
        "group_n": profile["group_n"],
        "metrics": profile["metrics"],
    }


def normalize_sex_to_female(value: Any) -> float:
    """성별 입력을 여성 여부(여성=1, 남성=0)로 통일함."""
    text = str(value).strip().lower()
    if text in {"여성", "female", "f", "2", "2.0"}:
        return 1.0
    if text in {"남성", "male", "m", "1", "1.0"}:
        return 0.0
    raise InputValidationError("성별은 '남성' 또는 '여성'으로 입력해야 함.")


def _as_optional_number(value: Any, label: str) -> float | None:
    """빈 값은 None으로, 숫자는 float로 바꿈."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise InputValidationError(f"{label}은(는) 숫자로 입력해야 함.") from error


def _validate_range(value: float | None, spec: dict[str, Any]) -> None:
    """입력된 수치가 시제품에서 허용하는 물리적으로 타당한 범위인지 확인함."""
    if value is None:
        return
    minimum = spec.get("min")
    maximum = spec.get("max")
    if minimum is not None and value < minimum:
        raise InputValidationError(f"{spec['label']}은(는) {minimum} 이상이어야 함.")
    if maximum is not None and value > maximum:
        raise InputValidationError(f"{spec['label']}은(는) {maximum} 이하여야 함.")


def _sigmoid(value: float) -> float:
    """수치 안정성을 고려한 sigmoid 계산."""
    value = max(min(value, 35.0), -35.0)
    return 1.0 / (1.0 + math.exp(-value))


def interpret_confirmation_tests(egfr_value: Any, uacr_value: Any) -> dict[str, Any]:
    """선택 입력한 eGFR·UACR을 선별모델과 분리하여 해석함.

    두 값은 모델이 위험확률을 계산할 때 사용하지 않음. 따라서 예측값을
    부풀리는 데이터 누출 없이, 확인검사 결과를 같은 화면에서 볼 수 있음.
    """
    egfr = _as_optional_number(egfr_value, "eGFR")
    uacr = _as_optional_number(uacr_value, "UACR")
    if egfr is not None and not 1 <= egfr <= 180:
        raise InputValidationError("eGFR은 1~180 mL/min/1.73m² 범위로 입력해야 함.")
    if uacr is not None and not 0 <= uacr <= 10000:
        raise InputValidationError("UACR은 0~10,000 mg/g 범위로 입력해야 함.")

    if egfr is None and uacr is None:
        return {
            "provided": False,
            "single_visit_abnormality": None,
            "egfr_status": "입력 안 함",
            "uacr_status": "입력 안 함",
            "interpretation": "확인검사값이 입력되지 않음.",
        }

    egfr_abnormal = egfr is not None and egfr < 60
    uacr_abnormal = uacr is not None and uacr >= 30
    single_visit_abnormality = egfr_abnormal or uacr_abnormal
    egfr_status = (
        "입력 안 함" if egfr is None else "기준 미만(eGFR < 60)" if egfr_abnormal else "현재 기준 이상(eGFR ≥ 60)"
    )
    uacr_status = (
        "입력 안 함" if uacr is None else "알부민뇨 기준 충족(UACR ≥ 30)" if uacr_abnormal else "현재 기준 미만(UACR < 30)"
    )

    if single_visit_abnormality:
        interpretation = (
            "입력된 확인검사에서 신장 이상 소견이 있음. 그러나 CKD 확진에는 "
            "최소 3개월 이상 지속 여부 확인과 의료진 판단이 필요함."
        )
    elif egfr is not None and uacr is not None:
        interpretation = (
            "입력된 두 확인검사 모두 현재 선별 기준에 해당하지 않음. "
            "이 결과만으로 CKD가 없다고 확진할 수는 없음."
        )
    else:
        interpretation = (
            "확인검사가 하나만 입력되어 종합 판정이 제한됨. "
            "eGFR과 UACR을 함께 확인하는 것이 바람직함."
        )

    return {
        "provided": True,
        "egfr": egfr,
        "uacr": uacr,
        "egfr_abnormal": egfr_abnormal,
        "uacr_abnormal": uacr_abnormal,
        "single_visit_abnormality": single_visit_abnormality,
        "egfr_status": egfr_status,
        "uacr_status": uacr_status,
        "interpretation": interpretation,
    }


def predict_single(values: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """입력 1건에 대한 위험확률과 선별 결과를 반환함."""
    config = config or load_model_config()
    specifications = config["input_specifications"]
    prepared: dict[str, float] = {}
    missing_inputs: list[str] = []

    for spec in specifications:
        key = spec["key"]
        label = spec["label"]
        if key == "female":
            raw_value = values.get(key)
            if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
                raise InputValidationError("성별은 반드시 선택해야 함.")
            prepared[key] = normalize_sex_to_female(raw_value)
            continue

        numeric_value = _as_optional_number(values.get(key), label)
        _validate_range(numeric_value, spec)
        if numeric_value is None:
            if not spec.get("allow_missing", False):
                raise InputValidationError(f"{label}은(는) 반드시 입력해야 함.")
            prepared[key] = float(config["train_medians"][spec["model_feature"]])
            missing_inputs.append(label)
        else:
            prepared[key] = numeric_value

    linear_score = float(config["intercept_standardized"])
    feature_contributions: list[dict[str, Any]] = []
    for spec in specifications:
        key = spec["key"]
        imputed_name = spec["model_feature"]
        flag_name = f"{imputed_name.replace('_imputed', '')}_missing_flag"
        is_missing = 1.0 if spec["label"] in missing_inputs else 0.0

        standardized_value = (
            prepared[key] - float(config["standardization_means"][imputed_name])
        ) / float(config["standardization_stds"][imputed_name])
        standardized_flag = (
            is_missing - float(config["standardization_means"][flag_name])
        ) / float(config["standardization_stds"][flag_name])
        value_contribution = float(config["coefficients_standardized"][imputed_name]) * standardized_value
        missing_contribution = float(config["coefficients_standardized"][flag_name]) * standardized_flag
        total_contribution = value_contribution + missing_contribution
        linear_score += total_contribution
        feature_contributions.append(
            {
                "indicator": spec["label"],
                "input_value": prepared[key],
                "was_imputed": bool(is_missing),
                "contribution_to_model_score": total_contribution,
                "direction": "위험확률을 높이는 방향" if total_contribution > 0.01 else "위험확률을 낮추는 방향" if total_contribution < -0.01 else "영향이 거의 없는 방향",
            }
        )

    risk_probability = _sigmoid(linear_score)
    threshold = float(config["selected_threshold"])
    screening_positive = risk_probability >= threshold

    return {
        "risk_probability": risk_probability,
        "screening_positive": screening_positive,
        "threshold": threshold,
        "missing_inputs": missing_inputs,
        "prepared_inputs": prepared,
        "feature_contributions": feature_contributions,
        "model_version": config["model_version"],
    }


def _normalized_column_map(dataframe: pd.DataFrame) -> dict[str, str]:
    """영문·한글 열 이름을 프로그램 내부의 표준 열 이름으로 연결함."""
    aliases = {
        "age_years": {"age_years", "age", "연령", "나이"},
        "sex": {"sex", "gender", "성별"},
        "mean_sbp_mmhg": {"mean_sbp_mmhg", "sbp", "systolic_bp", "수축기혈압", "평균수축기혈압"},
        "mean_dbp_mmhg": {"mean_dbp_mmhg", "dbp", "diastolic_bp", "이완기혈압", "평균이완기혈압"},
        "hemoglobin_g_dl": {"hemoglobin_g_dl", "hemoglobin", "hgb", "헤모글로빈"},
        "hba1c_percent": {"hba1c_percent", "hba1c", "a1c", "당화혈색소"},
        "egfr_optional": {"egfr_optional", "egfr", "egfr_ml_min", "추정사구체여과율"},
        "uacr_optional": {"uacr_optional", "uacr", "uacr_mg_g", "알부민크레아티닌비"},
    }
    original_by_normalized = {str(column).strip().lower(): str(column) for column in dataframe.columns}
    resolved: dict[str, str] = {}
    for internal_name, accepted_names in aliases.items():
        for candidate in accepted_names:
            if candidate.lower() in original_by_normalized:
                resolved[internal_name] = original_by_normalized[candidate.lower()]
                break
    return resolved


def read_uploaded_table(uploaded_file: Any) -> pd.DataFrame:
    """업로드한 프로그램 양식 Excel 또는 CSV를 데이터표로 읽음."""
    file_name = str(getattr(uploaded_file, "name", "")).lower()
    if file_name.endswith(".xlsx"):
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_name = "입력양식" if "입력양식" in excel_file.sheet_names else excel_file.sheet_names[0]
        return pd.read_excel(excel_file, sheet_name=sheet_name)
    if file_name.endswith(".csv"):
        file_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
        for encoding in ("utf-8-sig", "utf-8", "cp949"):
            try:
                return pd.read_csv(BytesIO(file_bytes), encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise InputValidationError("CSV 인코딩을 읽을 수 없음. UTF-8 또는 CP949 형식으로 저장해야 함.")
    raise InputValidationError("Excel(.xlsx) 또는 CSV 파일만 업로드할 수 있음.")


def predict_batch(dataframe: pd.DataFrame, config: dict[str, Any] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """CSV에서 읽은 여러 건을 분석하고, 유효하지 않은 행은 오류를 함께 반환함."""
    config = config or load_model_config()
    if len(dataframe) == 0:
        raise InputValidationError("CSV 파일에 분석할 행이 없음.")
    if len(dataframe) > 5000:
        raise InputValidationError("시제품에서는 한 번에 최대 5,000건까지만 분석할 수 있음.")

    column_map = _normalized_column_map(dataframe)
    missing_required_columns = [name for name in ("age_years", "sex") if name not in column_map]
    if missing_required_columns:
        translated = {"age_years": "age_years(연령)", "sex": "sex(성별)"}
        labels = ", ".join(translated[name] for name in missing_required_columns)
        raise InputValidationError(f"CSV에 필수 열이 없음: {labels}")

    output = dataframe.copy()
    risk_values: list[float | None] = []
    positive_values: list[str] = []
    missing_messages: list[str] = []
    error_messages: list[str] = []
    confirmation_statuses: list[str] = []
    egfr_interpretations: list[str] = []
    uacr_interpretations: list[str] = []
    confirmation_interpretations: list[str] = []

    for _, row in dataframe.iterrows():
        values = {
            "age_years": row[column_map["age_years"]],
            "female": row[column_map["sex"]],
            "mean_sbp_mmhg": row[column_map["mean_sbp_mmhg"]] if "mean_sbp_mmhg" in column_map else None,
            "mean_dbp_mmhg": row[column_map["mean_dbp_mmhg"]] if "mean_dbp_mmhg" in column_map else None,
            "hemoglobin_g_dl": row[column_map["hemoglobin_g_dl"]] if "hemoglobin_g_dl" in column_map else None,
            "hba1c_percent": row[column_map["hba1c_percent"]] if "hba1c_percent" in column_map else None,
        }
        try:
            prediction = predict_single(values, config)
            confirmation = interpret_confirmation_tests(
                row[column_map["egfr_optional"]] if "egfr_optional" in column_map else None,
                row[column_map["uacr_optional"]] if "uacr_optional" in column_map else None,
            )
            risk_values.append(prediction["risk_probability"])
            positive_values.append("추가 신장기능 검사 권고" if prediction["screening_positive"] else "현재 기준상 낮은 선별 위험")
            missing_messages.append(", ".join(prediction["missing_inputs"]) if prediction["missing_inputs"] else "없음")
            error_messages.append("")
            if not confirmation["provided"]:
                confirmation_statuses.append("확인 검사값 미입력")
            elif confirmation["single_visit_abnormality"]:
                confirmation_statuses.append("단일 검사 시점 이상 소견 있음")
            else:
                confirmation_statuses.append("현재 입력 검사기준 미충족")
            egfr_interpretations.append(confirmation["egfr_status"])
            uacr_interpretations.append(confirmation["uacr_status"])
            confirmation_interpretations.append(confirmation["interpretation"])
        except InputValidationError as error:
            risk_values.append(None)
            positive_values.append("분석 불가")
            missing_messages.append("")
            error_messages.append(str(error))
            confirmation_statuses.append("")
            egfr_interpretations.append("")
            uacr_interpretations.append("")
            confirmation_interpretations.append("")

    output["risk_probability"] = risk_values
    output["risk_percent"] = [round(value * 100, 1) if value is not None else None for value in risk_values]
    output["screening_result"] = positive_values
    output["imputed_missing_inputs"] = missing_messages
    output["input_error"] = error_messages
    output["confirmation_test_status"] = confirmation_statuses
    output["egfr_test_interpretation"] = egfr_interpretations
    output["uacr_test_interpretation"] = uacr_interpretations
    output["confirmation_interpretation"] = confirmation_interpretations
    output["model_version"] = config["model_version"]
    warnings = [
        "결과는 확진 진단이 아닌 연구용 선별 결과임.",
        "CSV에는 개인을 직접 식별할 수 있는 정보(성명, 주민등록번호, 연락처)를 넣지 않는 것을 권장함.",
    ]
    return output, warnings
