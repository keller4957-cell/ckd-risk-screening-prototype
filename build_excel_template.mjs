import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectDir = path.resolve(".");
const outputPath = path.join(projectDir, "ckd_screening_input_template.xlsx");
const workbook = Workbook.create();

const tealTitle = {
  fill: "#0F766E",
  font: { bold: true, color: "#FFFFFF", size: 15 },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
const tealHeader = {
  fill: "#155E75",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
const tableBorder = { preset: "all", style: "thin", color: "#CBD5E1" };

// Input is placed first so that it is the default sheet when users open or upload the file.
const input = workbook.worksheets.add("입력양식");
input.showGridLines = false;
input.getRange("A1:I1").values = [[
  "patient_id (선택)",
  "age_years *",
  "sex *",
  "mean_sbp_mmhg",
  "mean_dbp_mmhg",
  "hemoglobin_g_dl",
  "hba1c_percent",
  "egfr_optional",
  "uacr_optional",
]];
input.getRange("A2:I2").values = [[null, null, null, null, null, null, null, null, null]];
input.getRange("A1:I1").format = tealHeader;
input.getRange("A1:I1").format.rowHeight = 38;
input.getRange("A2:I20").format = {
  fill: "#FFFBEB",
  borders: { insideHorizontal: { style: "thin", color: "#E5E7EB" } },
  verticalAlignment: "center",
};
input.getRange("A1:I20").format.borders = tableBorder;
for (const [range, width] of [
  ["A1:A20", 20], ["B1:B20", 16], ["C1:C20", 16], ["D1:E20", 22],
  ["F1:F20", 22], ["G1:G20", 18], ["H1:I20", 18],
]) {
  input.getRange(range).format.columnWidth = width;
}
input.getRange("B2:B20").format.numberFormat = "0";
input.getRange("D2:I20").format.numberFormat = "0.0";
input.getRange("C2:C501").dataValidation = {
  rule: { type: "list", values: ["남성", "여성"] },
};
input.getRange("B2:B501").dataValidation = {
  rule: { type: "whole", operator: "between", formula1: 18, formula2: 120 },
};
input.getRange("D2:D501").dataValidation = {
  rule: { type: "decimal", operator: "between", formula1: 50, formula2: 260 },
};
input.getRange("E2:E501").dataValidation = {
  rule: { type: "decimal", operator: "between", formula1: 30, formula2: 160 },
};
input.getRange("F2:F501").dataValidation = {
  rule: { type: "decimal", operator: "between", formula1: 3, formula2: 25 },
};
input.getRange("G2:G501").dataValidation = {
  rule: { type: "decimal", operator: "between", formula1: 3, formula2: 20 },
};
input.getRange("H2:H501").dataValidation = {
  rule: { type: "decimal", operator: "between", formula1: 1, formula2: 180 },
};
input.getRange("I2:I501").dataValidation = {
  rule: { type: "decimal", operator: "between", formula1: 0, formula2: 10000 },
};
input.getRange("A22:I22").merge();
input.getRange("A22").values = [["입력 안내: * 표시된 age_years와 sex는 필수임. patient_id에는 성명·주민등록번호 등 직접 식별정보를 넣지 말고 임의 관리번호만 입력함. 나머지 항목은 선택이지만, 비어 있으면 학습자료 중앙값으로 대치되어 결과에 표시됨."]];
input.getRange("A22:I22").format = {
  fill: "#E0F2FE",
  font: { color: "#0C4A6E" },
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#7DD3FC" },
};
input.getRange("A22:I22").format.rowHeight = 38;
input.freezePanes.freezeRows(1);
input.freezePanes.freezeColumns(1);
input.tables.add("A1:I2", true, "CKDScreeningInput");

const guide = workbook.worksheets.add("작성안내");
guide.showGridLines = false;
guide.getRange("A1:D1").merge();
guide.getRange("A1").values = [["신장 이상 위험 선별 프로그램 | 다인 분석용 Excel 양식"]];
guide.getRange("A1:D1").format = tealTitle;
guide.getRange("A1:D1").format.rowHeight = 34;
guide.getRange("A3:B8").values = [
  ["사용 순서", "설명"],
  ["1", "입력양식 시트의 2행부터 한 행에 한 사람씩 입력함."],
  ["2", "age_years(연령)와 sex(남성 또는 여성)는 반드시 입력함."],
  ["3", "입력을 마친 뒤 파일을 저장하고, 프로그램의 ‘다인 일괄분석’ 탭에서 이 파일을 업로드함."],
  ["4", "프로그램에서 결과표를 확인하고 CSV로 내려받음."],
  ["5", "선별 양성 또는 eGFR/UACR 이상 소견은 확진이 아니며, 확인검사와 의료진 판단이 필요함."],
];
guide.getRange("B3:D3").merge();
for (let row = 4; row <= 8; row += 1) guide.getRange(`B${row}:D${row}`).merge();
guide.getRange("A3:B3").format = tealHeader;
guide.getRange("A4:A8").format = { fill: "#F0FDFA", font: { bold: true }, horizontalAlignment: "center" };
guide.getRange("A3:D8").format.borders = tableBorder;
guide.getRange("A3:D8").format.wrapText = true;
guide.getRange("A3:A8").format.columnWidth = 14;
guide.getRange("B3:D8").format.columnWidth = 35;
guide.getRange("A4:D8").format.rowHeight = 35;

guide.getRange("A11:D20").values = [
  ["열 이름", "필수", "단위/입력 예", "설명"],
  ["patient_id", "선택", "예: P-001", "익명 관리번호. 성명·주민등록번호·연락처 등 직접 식별정보 입력 금지"],
  ["age_years", "필수", "세, 예: 56", "18~120의 정수"],
  ["sex", "필수", "남성 또는 여성", "성별"],
  ["mean_sbp_mmhg", "선택", "mmHg, 예: 120", "평균 수축기혈압"],
  ["mean_dbp_mmhg", "선택", "mmHg, 예: 74", "평균 이완기혈압"],
  ["hemoglobin_g_dl", "선택", "g/dL, 예: 14.0", "헤모글로빈"],
  ["hba1c_percent", "선택", "%, 예: 5.5", "당화혈색소"],
  ["egfr_optional", "선택", "mL/min/1.73m², 예: 85", "위험확률에는 사용하지 않고 확인검사 해석에만 사용"],
  ["uacr_optional", "선택", "mg/g, 예: 12", "위험확률에는 사용하지 않고 확인검사 해석에만 사용"],
];
guide.getRange("A11:D11").format = tealHeader;
guide.getRange("A12:A20").format = { fill: "#F0FDFA", font: { bold: true } };
guide.getRange("A11:D20").format.borders = tableBorder;
guide.getRange("A11:D20").format.wrapText = true;
for (const [range, width] of [["A11:A20", 26], ["B11:B20", 14], ["C11:C20", 34], ["D11:D20", 70]]) {
  guide.getRange(range).format.columnWidth = width;
}
guide.getRange("A12:D20").format.rowHeight = 31;

guide.getRange("A23:D26").merge();
guide.getRange("A23").values = [["임상적 주의: 본 프로그램은 미국 NHANES 2021–2023 공개자료 기반 연구용 선별 시제품임. 단일 검사 시점의 위험을 선별할 뿐, CKD를 확진·치료결정하지 않음. 실제 임상 적용 전 국내자료 외부검증, 재보정 및 의료진 검토가 필요함."]];
guide.getRange("A23:D26").format = {
  fill: "#FFFBEB",
  font: { color: "#78350F" },
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "outside", style: "thin", color: "#F59E0B" },
};
guide.getRange("A23:D26").format.rowHeight = 30;

const check = await workbook.inspect({
  kind: "table",
  range: "입력양식!A1:I22",
  include: "values,formulas",
  tableMaxRows: 24,
  tableMaxCols: 10,
});
console.log(check.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "template formula error scan",
});
console.log(errors.ndjson);

for (const [sheetName, range, fileName] of [
  ["입력양식", "A1:I22", "template_preview_input.png"],
  ["작성안내", "A1:D26", "template_preview_guide.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1.25, format: "png" });
  await fs.writeFile(path.join(projectDir, fileName), new Uint8Array(await preview.arrayBuffer()));
}

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath }));
