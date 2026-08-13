import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const [sourcePath, outputPath] = process.argv.slice(2);
if (!sourcePath || !outputPath) {
  throw new Error("Usage: node build_public_dataset.mjs <source.xlsx> <output.xlsx>");
}

const sourceBlob = await FileBlob.load(sourcePath);
const sourceWorkbook = await SpreadsheetFile.importXlsx(sourceBlob);

const sourceInputSheet = sourceWorkbook.worksheets.getItem("모델입력_정제자료");
const sourcePredictionSheet = sourceWorkbook.worksheets.getItem("검증예측결과");
const sourcePerformanceSheet = sourceWorkbook.worksheets.getItem("모델성능_검증");

const sourceInput = await sourceInputSheet.getUsedRange().values;
const sourcePredictions = await sourcePredictionSheet.getUsedRange().values;
const sourcePerformance = await sourcePerformanceSheet.getUsedRange().values;

function columnIndex(headers, name) {
  const index = headers.indexOf(name);
  if (index < 0) throw new Error(`Required column not found: ${name}`);
  return index;
}

function pickColumns(sourceRows, selectedColumns) {
  const headers = sourceRows[0].map((value) => String(value));
  const indexes = selectedColumns.map((name) => columnIndex(headers, name));
  return sourceRows.slice(1).map((row) => indexes.map((index) => row[index] ?? null));
}

const inputHeaders = sourceInput[0].map((value) => String(value));
const sourceSeqnIndex = columnIndex(inputHeaders, "SEQN");
const publicIdBySeqn = new Map();
for (let index = 1; index < sourceInput.length; index += 1) {
  publicIdBySeqn.set(String(sourceInput[index][sourceSeqnIndex]), `CASE-${String(index).padStart(5, "0")}`);
}

const publicInputColumns = [
  "Age_years",
  "Sex_code",
  "Mean_SBP_mmHg",
  "Mean_DBP_mmHg",
  "Hemoglobin_g_dL",
  "HbA1c_percent",
  "kidney_abnormality_screening_label",
  "data_split",
];
const publicInputRows = pickColumns(sourceInput, publicInputColumns).map((row, index) => [
  `CASE-${String(index + 1).padStart(5, "0")}`,
  ...row,
]);

const predictionHeaders = sourcePredictions[0].map((value) => String(value));
const predictionSeqnIndex = columnIndex(predictionHeaders, "SEQN");
const publicPredictionColumns = [
  "Age_years",
  "Sex_code",
  "kidney_abnormality_screening_label",
  "data_split",
  "predicted_risk",
  "predicted_positive_at_selected_threshold",
];
const publicPredictionRows = pickColumns(sourcePredictions, publicPredictionColumns);
for (let rowIndex = 0; rowIndex < publicPredictionRows.length; rowIndex += 1) {
  const originalRow = sourcePredictions[rowIndex + 1];
  publicPredictionRows[rowIndex].unshift(publicIdBySeqn.get(String(originalRow[predictionSeqnIndex])) ?? null);
}

const workbook = Workbook.create();
const tealTitle = {
  fill: "#0F766E",
  font: { bold: true, color: "#FFFFFF", size: 14 },
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
const tableBorder = { preset: "outside", style: "thin", color: "#CBD5E1" };

const guide = workbook.worksheets.add("README_공개용");
guide.showGridLines = false;
guide.getRange("A1").values = [["만성 신장질환 위험 선별 프로젝트 | 공개용 정제 데이터셋"]];
guide.getRange("A1:F1").format = tealTitle;
guide.getRange("A1:F1").format.rowHeight = 32;
guide.getRange("A3:B11").values = [
  ["항목", "설명"],
  ["파일 목적", "GitHub 공개용 연구·교육·재현성 확인 자료"],
  ["원자료 출처", "CDC NHANES 2021–2023 공개자료"],
  ["분석대상", `정제 분석대상 ${publicInputRows.length.toLocaleString("en-US")}명`],
  ["제외한 식별자", "원자료의 SEQN을 제거하고 CASE-00001 형식의 새 공개용 행 ID를 부여함"],
  ["제외한 변수", "인종·소득·개별 반복 측정·신장 기능 표지자(eGFR·UACR) 등 모델 입력에 불필요한 변수"],
  ["포함한 변수", "모델 입력 6개 지표, 단일시점 신장 이상 선별 라벨, 학습·검증 분할, 검증 예측결과"],
  ["라벨 정의", "단일 검사 시점에서 eGFR < 60 또는 UACR ≥ 30 mg/g. CKD 확진이 아님"],
  ["이용 주의", "통계 분석·보고 목적의 연구용 자료이며, 진단·치료결정 또는 개인 재식별에 사용하면 안 됨"],
];
guide.getRange("A3:B3").format = tealHeader;
guide.getRange("A4:A11").format = { fill: "#F0FDFA", font: { bold: true }, verticalAlignment: "center" };
guide.getRange("A3:B11").format.wrapText = true;
guide.getRange("A3:B11").format.borders = tableBorder;
guide.getRange("A3:A11").format.columnWidth = 24;
guide.getRange("B3:B11").format.columnWidth = 100;
guide.getRange("A4:B11").format.rowHeight = 30;
guide.getRange("A14:B17").values = [
  ["공식 자료·정책", "URL"],
  ["NHANES 공개자료", "https://wwwn.cdc.gov/nchs/nhanes/"],
  ["NCHS Data User Agreement", "https://www.cdc.gov/nchs/policy/data-user-agreement.html"],
  ["프로젝트 저장소", "https://github.com/AceYD/ckd-risk-screening-prototype"],
];
guide.getRange("A14:B14").format = tealHeader;
guide.getRange("A15:A17").format = { fill: "#F0FDFA", font: { bold: true } };
guide.getRange("A14:B17").format.wrapText = true;
guide.getRange("A14:B17").format.borders = tableBorder;
guide.getRange("A14:A17").format.columnWidth = 28;
guide.getRange("B14:B17").format.columnWidth = 90;
guide.freezePanes.freezeRows(3);

const modelData = workbook.worksheets.add("모델입력_공개용");
modelData.showGridLines = false;
const publicInputHeaders = ["public_record_id", ...publicInputColumns];
modelData.getRangeByIndexes(0, 0, 1, publicInputHeaders.length).values = [publicInputHeaders];
modelData.getRangeByIndexes(1, 0, publicInputRows.length, publicInputHeaders.length).values = publicInputRows;
modelData.getRangeByIndexes(0, 0, 1, publicInputHeaders.length).format = tealHeader;
modelData.getRangeByIndexes(0, 0, 1, publicInputHeaders.length).format.rowHeight = 32;
modelData.getRange(`A1:I${publicInputRows.length + 1}`).format.borders = tableBorder;
modelData.freezePanes.freezeRows(1);
modelData.freezePanes.freezeColumns(1);
modelData.tables.add(`A1:I${publicInputRows.length + 1}`, true, "PublicModelInput");
for (const [range, width] of [
  [`A1:A${publicInputRows.length + 1}`, 19],
  [`B1:B${publicInputRows.length + 1}`, 14],
  [`C1:C${publicInputRows.length + 1}`, 12],
  [`D1:E${publicInputRows.length + 1}`, 20],
  [`F1:G${publicInputRows.length + 1}`, 19],
  [`H1:H${publicInputRows.length + 1}`, 28],
  [`I1:I${publicInputRows.length + 1}`, 14],
]) {
  modelData.getRange(range).format.columnWidth = width;
}
modelData.getRange(`B2:G${publicInputRows.length + 1}`).format.numberFormat = "0.0";
modelData.getRange(`H2:H${publicInputRows.length + 1}`).format.numberFormat = "0";

const predictionData = workbook.worksheets.add("검증예측결과_공개용");
predictionData.showGridLines = false;
const publicPredictionHeaders = ["public_record_id", ...publicPredictionColumns];
predictionData.getRangeByIndexes(0, 0, 1, publicPredictionHeaders.length).values = [publicPredictionHeaders];
predictionData.getRangeByIndexes(1, 0, publicPredictionRows.length, publicPredictionHeaders.length).values = publicPredictionRows;
predictionData.getRangeByIndexes(0, 0, 1, publicPredictionHeaders.length).format = tealHeader;
predictionData.getRangeByIndexes(0, 0, 1, publicPredictionHeaders.length).format.rowHeight = 32;
predictionData.getRange(`A1:G${publicPredictionRows.length + 1}`).format.borders = tableBorder;
predictionData.freezePanes.freezeRows(1);
predictionData.freezePanes.freezeColumns(1);
predictionData.tables.add(`A1:G${publicPredictionRows.length + 1}`, true, "PublicValidationPredictions");
for (const [range, width] of [
  [`A1:A${publicPredictionRows.length + 1}`, 19],
  [`B1:B${publicPredictionRows.length + 1}`, 14],
  [`C1:C${publicPredictionRows.length + 1}`, 12],
  [`D1:E${publicPredictionRows.length + 1}`, 28],
  [`F1:G${publicPredictionRows.length + 1}`, 24],
]) {
  predictionData.getRange(range).format.columnWidth = width;
}
predictionData.getRange(`F2:F${publicPredictionRows.length + 1}`).format.numberFormat = "0.0%";

const performance = workbook.worksheets.add("모델성능_요약");
const nonEmptyPerformanceRows = sourcePerformance.filter((row) => row.some((value) => value !== null && value !== undefined));
const performanceColumns = Math.max(...nonEmptyPerformanceRows.map((row) => row.length));
const normalizedPerformance = nonEmptyPerformanceRows.map((row) => Array.from({ length: performanceColumns }, (_, index) => row[index] ?? null));
performance.getRangeByIndexes(0, 0, normalizedPerformance.length, performanceColumns).values = normalizedPerformance;
performance.getRangeByIndexes(0, 0, 1, performanceColumns).format = tealHeader;
performance.getRangeByIndexes(0, 0, normalizedPerformance.length, performanceColumns).format.wrapText = true;
performance.getRangeByIndexes(0, 0, normalizedPerformance.length, performanceColumns).format.borders = tableBorder;
performance.getUsedRange().format.autofitColumns();
performance.freezePanes.freezeRows(1);

const codebook = workbook.worksheets.add("변수_코드북");
codebook.showGridLines = false;
codebook.getRange("A1").values = [["공개용 변수 정의"]];
codebook.getRange("A1:D1").format = tealTitle;
codebook.getRange("A3:D12").values = [
  ["시트", "변수명", "설명", "단위·코드"],
  ["모델입력_공개용", "public_record_id", "새로 부여한 공개용 행 식별자. SEQN이 아님", "CASE-00001 형식"],
  ["모델입력_공개용", "Age_years", "연령", "세"],
  ["모델입력_공개용", "Sex_code", "성별 코드", "1=남성, 2=여성"],
  ["모델입력_공개용", "Mean_SBP_mmHg", "반복 측정값의 평균 수축기혈압", "mmHg"],
  ["모델입력_공개용", "Mean_DBP_mmHg", "반복 측정값의 평균 이완기혈압", "mmHg"],
  ["모델입력_공개용", "Hemoglobin_g_dL", "헤모글로빈", "g/dL"],
  ["모델입력_공개용", "HbA1c_percent", "당화혈색소", "%"],
  ["모델입력_공개용", "kidney_abnormality_screening_label", "단일 검사 시점의 신장 이상 선별 라벨", "0=기준 미충족, 1=이상 소견"],
  ["모델입력_공개용", "data_split", "모델 학습·검증 분할", "Train / Validation / Test"],
];
codebook.getRange("A3:D3").format = tealHeader;
codebook.getRange("A4:A12").format = { fill: "#F0FDFA" };
codebook.getRange("A3:D12").format.borders = tableBorder;
codebook.getRange("A3:D12").format.wrapText = true;
for (const [range, width] of [["A3:A12", 24], ["B3:B12", 35], ["C3:C12", 65], ["D3:D12", 32]]) {
  codebook.getRange(range).format.columnWidth = width;
}
codebook.getRange("A4:D12").format.rowHeight = 29;

const modelCheck = await workbook.inspect({
  kind: "table",
  range: "모델입력_공개용!A1:I6",
  include: "values,formulas",
  tableMaxRows: 6,
  tableMaxCols: 10,
});
console.log(modelCheck.ndjson);
const errorCheck = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "public dataset formula error scan",
});
console.log(errorCheck.ndjson);

const preview = await workbook.render({
  sheetName: "README_공개용",
  range: "A1:B17",
  scale: 1.25,
  format: "png",
});
await fs.writeFile(path.join(path.dirname(outputPath), "public_dataset_preview.png"), new Uint8Array(await preview.arrayBuffer()));

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, inputRows: publicInputRows.length, predictionRows: publicPredictionRows.length }));
