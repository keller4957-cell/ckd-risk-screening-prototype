"""NHANES 원자료에서 개별 선별 화면용 연령·성별 참고집단 요약치를 생성함.

이 스크립트는 원자료를 앱에 포함하지 않고, 앱에 필요한 집계 통계만
``reference_profiles.json`` 파일로 저장함.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


OUTPUT_PATH = Path(__file__).resolve().parent / "reference_profiles.json"

AGE_BANDS = [
    (18, 25, "18–24세"),
    (25, 35, "25–34세"),
    (35, 45, "35–44세"),
    (45, 55, "45–54세"),
    (55, 65, "55–64세"),
    (65, 75, "65–74세"),
    (75, 85, "75–84세"),
    (85, 121, "85세 이상"),
]

METRICS = {
    "mean_sbp_mmhg": ("Mean_SBP_mmHg", "평균 수축기혈압", "mmHg"),
    "mean_dbp_mmhg": ("Mean_DBP_mmHg", "평균 이완기혈압", "mmHg"),
    "hemoglobin_g_dl": ("Hemoglobin_g_dL", "헤모글로빈", "g/dL"),
    "hba1c_percent": ("HbA1c_percent", "당화혈색소", "%"),
}


def summarize_metric(values: pd.Series) -> dict[str, float | int]:
    """결측치를 제외한 평균과 25·75백분위수를 JSON에 저장 가능한 값으로 변환함."""
    values = values.dropna()
    return {
        "n": int(values.shape[0]),
        "mean": round(float(values.mean()), 2),
        "q25": round(float(values.quantile(0.25)), 2),
        "q75": round(float(values.quantile(0.75)), 2),
    }


def build_profiles(source_path: Path = SOURCE_DATA) -> dict:
    """신장검사상 이상 소견이 없는 성인 참고집단의 요약 프로필을 계산함."""
    data = pd.read_csv(source_path)
    reference = data.loc[
        data["kidney_abnormality_screening_label"].eq(0)
        & data["Age_years"].between(18, 120)
    ].copy()

    profiles: dict[str, dict] = {}
    for sex_code, sex_key in ((1, "male"), (2, "female")):
        sex_data = reference.loc[reference["Sex_code"].eq(sex_code)]
        profiles[sex_key] = {}
        for minimum_age, maximum_age, label in AGE_BANDS:
            group = sex_data.loc[sex_data["Age_years"].between(minimum_age, maximum_age - 1)]
            profiles[sex_key][label] = {
                "group_n": int(group.shape[0]),
                "metrics": {
                    key: {
                        "label": metric_label,
                        "unit": unit,
                        **summarize_metric(group[column]),
                    }
                    for key, (column, metric_label, unit) in METRICS.items()
                },
            }

    return {
        "reference_name": "현재 신장검사상 이상 소견이 없는 NHANES 참고집단",
        "source": "CDC NHANES 2021–2023 성인 공개자료",
        "reference_definition": "eGFR 60 이상 및 UACR 30 mg/g 미만인 성인. 건강 확정 또는 진단 기준이 아님.",
        "age_band_method": "입력 연령을 8개 연령대로 분류하여 동일 성별 참고집단과 비교함.",
        "reference_total_n": int(reference.shape[0]),
        "profiles": profiles,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "사용법: python build_reference_profiles.py <nhanes_ckd_screening_labeled_dataset.csv>"
        )
    profile_data = build_profiles(Path(sys.argv[1]))
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(profile_data, file, ensure_ascii=False, indent=2)
    print(f"참고집단 요약 파일 생성 완료: {OUTPUT_PATH}")
