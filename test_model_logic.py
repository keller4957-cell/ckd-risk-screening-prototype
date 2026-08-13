"""핵심 예측 로직의 간단한 회귀 테스트."""

import unittest
from io import BytesIO

import pandas as pd

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


class ModelLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_model_config()
        cls.reference_profiles = load_reference_profiles()

    def test_valid_input_returns_probability_between_zero_and_one(self):
        prediction = predict_single(
            {
                "age_years": 56,
                "female": "여성",
                "mean_sbp_mmhg": 120,
                "mean_dbp_mmhg": 74,
                "hemoglobin_g_dl": 14,
                "hba1c_percent": 5.5,
            },
            self.config,
        )
        self.assertGreaterEqual(prediction["risk_probability"], 0)
        self.assertLessEqual(prediction["risk_probability"], 1)
        self.assertEqual(prediction["missing_inputs"], [])
        self.assertEqual(len(prediction["feature_contributions"]), 6)

    def test_missing_optional_lab_is_imputed(self):
        prediction = predict_single(
            {
                "age_years": 56,
                "female": "남성",
                "mean_sbp_mmhg": None,
                "mean_dbp_mmhg": 74,
                "hemoglobin_g_dl": 14,
                "hba1c_percent": 5.5,
            },
            self.config,
        )
        self.assertIn("평균 수축기혈압", prediction["missing_inputs"])

    def test_underage_input_is_rejected(self):
        with self.assertRaises(InputValidationError):
            predict_single(
                {
                    "age_years": 17,
                    "female": "여성",
                    "mean_sbp_mmhg": 120,
                    "mean_dbp_mmhg": 74,
                    "hemoglobin_g_dl": 14,
                    "hba1c_percent": 5.5,
                },
                self.config,
            )

    def test_batch_output_has_required_result_columns(self):
        result, _ = predict_batch(
            pd.DataFrame(
                [{"age_years": 56, "sex": "여성", "mean_sbp_mmhg": 120, "mean_dbp_mmhg": 74, "hemoglobin_g_dl": 14, "hba1c_percent": 5.5}]
            ),
            self.config,
        )
        self.assertIn("risk_probability", result.columns)
        self.assertIn("screening_result", result.columns)

    def test_batch_interprets_optional_confirmation_tests(self):
        result, _ = predict_batch(
            pd.DataFrame(
                [{"age_years": 56, "sex": "여성", "egfr_optional": 55, "uacr_optional": 10}]
            ),
            self.config,
        )
        self.assertEqual(result.loc[0, "confirmation_test_status"], "단일 검사 시점 이상 소견 있음")

    def test_excel_template_can_be_read_as_batch_input(self):
        workbook_bytes = BytesIO()
        with pd.ExcelWriter(workbook_bytes, engine="openpyxl") as writer:
            pd.DataFrame([{"age_years": 56, "sex": "여성"}]).to_excel(writer, sheet_name="입력양식", index=False)
        workbook_bytes.name = "sample.xlsx"
        parsed = read_uploaded_table(workbook_bytes)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed.loc[0, "age_years"], 56)

    def test_confirmation_test_abnormality_is_not_ckd_diagnosis(self):
        result = interpret_confirmation_tests(55, 10)
        self.assertTrue(result["single_visit_abnormality"])
        self.assertIn("CKD 확진", result["interpretation"])

    def test_confirmation_test_can_be_left_blank(self):
        result = interpret_confirmation_tests("", "")
        self.assertFalse(result["provided"])

    def test_reference_profile_matches_age_and_sex(self):
        profile = get_reference_profile(56, "남성", self.reference_profiles)
        self.assertEqual(profile["sex_label"], "남성")
        self.assertEqual(profile["age_band"], "55–64세")
        self.assertGreater(profile["group_n"], 0)
        self.assertIn("mean_sbp_mmhg", profile["metrics"])
        self.assertLess(
            profile["metrics"]["hba1c_percent"]["q25"],
            profile["metrics"]["hba1c_percent"]["q75"],
        )


if __name__ == "__main__":
    unittest.main()
