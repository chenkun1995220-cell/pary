import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = path.resolve("outputs");
const outputPath = path.join(outputDir, "美股港股A股低估筛选模板.xlsx");

function colName(n) {
  let s = "";
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function writeRows(sheet, startCell, rows) {
  const range = sheet.getRange(startCell).resize(rows.length, rows[0].length);
  range.values = rows;
  return range;
}

function styleTitle(range) {
  range.format = {
    fill: "#1F4E78",
    font: { bold: true, color: "#FFFFFF", size: 14 },
    horizontalAlignment: "left",
    verticalAlignment: "middle",
  };
}

function styleHeader(range, fill = "#305496") {
  range.format = {
    fill,
    font: { bold: true, color: "#FFFFFF" },
    borders: { preset: "all", style: "thin", color: "#BFBFBF" },
    horizontalAlignment: "center",
    verticalAlignment: "middle",
    wrapText: true,
  };
}

function styleBody(range) {
  range.format = {
    borders: { preset: "all", style: "thin", color: "#D9E2F3" },
    verticalAlignment: "middle",
    wrapText: true,
  };
}

const workbook = Workbook.create();

const cover = workbook.worksheets.add("封面");
const screen = workbook.worksheets.add("输入与打分");
const industry = workbook.worksheets.add("行业阈值");
const dictionary = workbook.worksheets.add("数据字典");
const sources = workbook.worksheets.add("来源与口径");
const checks = workbook.worksheets.add("检查");

for (const sheet of [cover, screen, industry, dictionary, sources, checks]) {
  sheet.showGridLines = false;
}

cover.getRange("A1:H1").merge();
cover.getRange("A1").values = [["美股/港股/A股低估公司筛选模板"]];
styleTitle(cover.getRange("A1:H1"));
cover.getRange("A3:H8").values = [
  ["使用步骤", "", "", "", "", "", "", ""],
  ["1", "先在“行业阈值”维护行业估值中位数和风险阈值。", "", "", "", "", "", ""],
  ["2", "在“输入与打分”录入公司基础财务数据、估值指标、风险标记。", "", "", "", "", "", ""],
  ["3", "表格自动计算六维评分、总分、候选等级和动作建议。", "", "", "", "", "", ""],
  ["4", "在“来源与口径”记录数据来源和报告期，避免混用不同口径。", "", "", "", "", "", ""],
  ["5", "用“检查”页查看缺失数据和高风险标记。", "", "", "", "", "", ""],
];
styleHeader(cover.getRange("A3:H3"), "#5B9BD5");
styleBody(cover.getRange("A4:H8"));

cover.getRange("A10:H16").values = [
  ["评分等级", "分数区间", "含义", "建议动作", "", "", "", ""],
  ["A", "90-100", "高优先级深研", "进入年报、行业、估值模型和风险核验", "", "", "", ""],
  ["B", "80-89", "重点观察", "进入跟踪池，等待价格或基本面确认", "", "", "", ""],
  ["C", "70-79", "普通观察", "保留但不优先", "", "", "", ""],
  ["D", "60-69", "暂不深研", "仅在估值继续下修或行业变化时复看", "", "", "", ""],
  ["E", "0-59", "剔除", "不进入候选池", "", "", "", ""],
  ["注意", "低估筛选不是买入建议", "必须结合后续个股研究和仓位管理", "", "", "", "", ""],
];
styleHeader(cover.getRange("A10:H10"), "#70AD47");
styleBody(cover.getRange("A11:H16"));

cover.getRange("A18:H24").values = [
  ["评分权重", "权重", "说明", "", "", "", "", ""],
  ["估值折价", 30, "PE/PB/EV/EBITDA 相对行业折价，FCF 收益率", "", "", "", "", ""],
  ["盈利质量", 25, "ROE、ROIC、毛利率、净利率", "", "", "", "", ""],
  ["资产负债安全", 15, "资产负债率、净负债/EBITDA、流动比率", "", "", "", "", ""],
  ["现金流质量", 15, "经营现金流、自由现金流、FCF 收益率", "", "", "", "", ""],
  ["成长与稳定", 10, "收入和净利润 3 年 CAGR", "", "", "", "", ""],
  ["治理与流动性风险", 5, "审计意见、ST/退市风险、重大风险标记", "", "", "", "", ""],
];
styleHeader(cover.getRange("A18:H18"), "#4472C4");
styleBody(cover.getRange("A19:H24"));

cover.getRange("A26:H28").values = [
  ["口径提醒", "", "", "", "", "", "", ""],
  ["本模板使用 TTM 优先、同行业比较、同币种比较原则。金融、地产、周期、亏损成长股建议使用专门行业口径。", "", "", "", "", "", "", ""],
  ["可先人工录入 50-200 只股票测试模型，再扩展为自动化数据导入。", "", "", "", "", "", "", ""],
];
styleHeader(cover.getRange("A26:H26"), "#A64D79");
styleBody(cover.getRange("A27:H28"));

const headers = [
  "市场", "股票代码", "公司名称", "行业", "货币", "数据日期", "股价",
  "总市值", "企业价值EV", "净资产", "收入TTM", "净利润TTM", "EBITDA",
  "经营现金流", "资本开支", "自由现金流", "PE", "PB", "PS", "EV/EBITDA",
  "FCF收益率", "股息率", "行业PE中位数", "行业PB中位数", "行业EV/EBITDA中位数",
  "ROE", "ROIC", "毛利率", "净利率", "资产负债率", "净负债/EBITDA",
  "流动比率", "3年收入CAGR", "3年净利CAGR", "审计意见", "风险标记",
  "估值分", "盈利质量分", "资产负债分", "现金流分", "成长稳定分",
  "治理风险分", "总分", "等级", "操作建议", "备注"
];

screen.getRange("A1:AT1").merge();
screen.getRange("A1").values = [["输入与打分"]];
styleTitle(screen.getRange("A1:AT1"));
screen.getRange("A3:AT3").values = [headers];
styleHeader(screen.getRange("A3:AT3"), "#203864");
screen.freezePanes.freezeRows(3);

const rows = 200;
const startRow = 4;
const endRow = startRow + rows - 1;
const sampleRows = [
  ["A股", "示例001", "示例消费公司", "消费", "CNY", "2026-06-16", 20, 50000, 48000, 25000, 30000, 3500, 5000, 4200, -1200, null, null, null, null, null, null, 0.025, 22, 3.0, 12, 0.14, 0.12, 0.42, null, 0.38, 1.2, 1.8, 0.08, 0.10, "标准无保留", "无", null, null, null, null, null, null, null, null, null, "示例：资本开支用负数录入"],
  ["港股", "00000.HK", "示例公用事业", "公用事业", "HKD", "2026-06-16", 8, 30000, 42000, 18000, 12000, 2200, 4500, 3000, -900, null, null, null, null, null, null, 0.055, 14, 1.5, 9, 0.10, 0.08, 0.35, null, 0.55, 2.2, 1.1, 0.03, 0.04, "标准无保留", "无", null, null, null, null, null, null, null, null, null, "示例：高分红但需核查负债期限"],
  ["美股", "DEMO", "示例软件公司", "科技软件", "USD", "2026-06-16", 45, 90000, 85000, 12000, 18000, 1500, 2500, 2800, -500, null, null, null, null, null, null, 0, 35, 7.0, 22, 0.11, 0.09, 0.72, null, 0.28, 0.5, 2.5, 0.18, 0.15, "标准无保留", "无", null, null, null, null, null, null, null, null, null, "示例：成长股估值需看留存率和续费质量"],
];
screen.getRange(`A${startRow}:AT${startRow + sampleRows.length - 1}`).values = sampleRows;

for (let r = startRow; r <= endRow; r++) {
  screen.getRange(`P${r}`).formulas = [[`=IF(OR(N${r}="",O${r}=""),"",N${r}+O${r})`]];
  screen.getRange(`Q${r}`).formulas = [[`=IF(OR(H${r}="",L${r}="",L${r}<=0),"",H${r}/L${r})`]];
  screen.getRange(`R${r}`).formulas = [[`=IF(OR(H${r}="",J${r}="",J${r}<=0),"",H${r}/J${r})`]];
  screen.getRange(`S${r}`).formulas = [[`=IF(OR(H${r}="",K${r}="",K${r}<=0),"",H${r}/K${r})`]];
  screen.getRange(`T${r}`).formulas = [[`=IF(OR(I${r}="",M${r}="",M${r}<=0),"",I${r}/M${r})`]];
  screen.getRange(`U${r}`).formulas = [[`=IF(OR(P${r}="",H${r}="",H${r}<=0),"",P${r}/H${r})`]];
  screen.getRange(`AC${r}`).formulas = [[`=IF(OR(L${r}="",K${r}="",K${r}=0),"",L${r}/K${r})`]];
  screen.getRange(`AK${r}`).formulas = [[`=IF(C${r}="","",MIN(30,IF(AND(Q${r}<>"",W${r}<>"",Q${r}<=W${r}*0.7),9,IF(AND(Q${r}<>"",W${r}<>"",Q${r}<=W${r}*0.85),6,IF(AND(Q${r}<>"",W${r}<>"",Q${r}<=W${r}),3,0)))+IF(AND(R${r}<>"",X${r}<>"",R${r}<=X${r}*0.7),7,IF(AND(R${r}<>"",X${r}<>"",R${r}<=X${r}*0.85),5,IF(AND(R${r}<>"",X${r}<>"",R${r}<=X${r}),2,0)))+IF(AND(T${r}<>"",Y${r}<>"",T${r}<=Y${r}*0.7),7,IF(AND(T${r}<>"",Y${r}<>"",T${r}<=Y${r}*0.85),5,IF(AND(T${r}<>"",Y${r}<>"",T${r}<=Y${r}),2,0)))+IF(U${r}>=0.08,7,IF(U${r}>=0.05,5,IF(U${r}>=0.03,2,0)))))`]];
  screen.getRange(`AL${r}`).formulas = [[`=IF(C${r}="","",MIN(25,IF(Z${r}>=0.15,7,IF(Z${r}>=0.10,5,IF(Z${r}>0,2,0)))+IF(AA${r}>=0.12,7,IF(AA${r}>=0.08,5,IF(AA${r}>0,2,0)))+IF(AB${r}>=0.40,6,IF(AB${r}>=0.25,4,IF(AB${r}>0,1,0)))+IF(AC${r}>=0.15,5,IF(AC${r}>=0.08,3,IF(AC${r}>0,1,0)))))`]];
  screen.getRange(`AM${r}`).formulas = [[`=IF(C${r}="","",MIN(15,IF(AD${r}<=0.4,5,IF(AD${r}<=0.6,3,IF(AD${r}<>"",1,0)))+IF(AE${r}<=1,5,IF(AE${r}<=2.5,3,IF(AE${r}<>"",1,0)))+IF(AF${r}>=1.5,5,IF(AF${r}>=1,3,IF(AF${r}<>"",1,0)))))`]];
  screen.getRange(`AN${r}`).formulas = [[`=IF(C${r}="","",MIN(15,IF(P${r}>0,4,0)+IF(U${r}>=0.08,5,IF(U${r}>=0.05,3,IF(U${r}>=0.03,1,0)))+IF(AND(N${r}<>"",L${r}<>"",L${r}>0,N${r}/L${r}>=1),6,IF(AND(N${r}<>"",L${r}<>"",L${r}>0,N${r}/L${r}>=0.7),3,0))))`]];
  screen.getRange(`AO${r}`).formulas = [[`=IF(C${r}="","",MIN(10,IF(AG${r}>=0.10,5,IF(AG${r}>=0.03,3,IF(AG${r}>0,1,0)))+IF(AH${r}>=0.10,5,IF(AH${r}>=0.03,3,IF(AH${r}>0,1,0)))))`]];
  screen.getRange(`AP${r}`).formulas = [[`=IF(C${r}="","",IF(AND(AI${r}="标准无保留",AJ${r}="无"),5,IF(AND(AI${r}="标准无保留",AJ${r}<>"重大"),3,1)))`]];
  screen.getRange(`AQ${r}`).formulas = [[`=IF(C${r}="","",SUM(AK${r}:AP${r}))`]];
  screen.getRange(`AR${r}`).formulas = [[`=IF(AQ${r}="","",IF(AQ${r}>=90,"A 高优先级深研",IF(AQ${r}>=80,"B 重点观察",IF(AQ${r}>=70,"C 普通观察",IF(AQ${r}>=60,"D 暂不深研","E 剔除")))))`]];
  screen.getRange(`AS${r}`).formulas = [[`=IF(AR${r}="","",IF(LEFT(AR${r},1)="A","进入年报/行业/估值模型深研",IF(LEFT(AR${r},1)="B","加入重点跟踪池",IF(LEFT(AR${r},1)="C","普通观察，等待确认",IF(LEFT(AR${r},1)="D","暂不深研，仅复看","剔除")))))`]];
}

styleBody(screen.getRange(`A${startRow}:AT${endRow}`));
screen.getRange(`G${startRow}:O${endRow}`).format.numberFormat = "#,##0.00;[Red](#,##0.00);-";
screen.getRange(`Q${startRow}:T${endRow}`).format.numberFormat = "0.0x;[Red](0.0x);-";
screen.getRange(`U${startRow}:V${endRow}`).format.numberFormat = "0.0%;[Red](0.0%);-";
screen.getRange(`Z${startRow}:AH${endRow}`).format.numberFormat = "0.0%;[Red](0.0%);-";
screen.getRange(`AK${startRow}:AQ${endRow}`).format.numberFormat = "0";
screen.getRange(`A${startRow}:A${endRow}`).dataValidation = { rule: { type: "list", values: ["美股", "港股", "A股"] } };
screen.getRange(`E${startRow}:E${endRow}`).dataValidation = { rule: { type: "list", values: ["USD", "HKD", "CNY"] } };
screen.getRange(`AI${startRow}:AI${endRow}`).dataValidation = { rule: { type: "list", values: ["标准无保留", "带强调事项", "保留意见", "否定意见", "无法表示意见"] } };
screen.getRange(`AJ${startRow}:AJ${endRow}`).dataValidation = { rule: { type: "list", values: ["无", "轻微", "重大"] } };
const industryRows = [
  ["行业", "市场", "PE中位数", "PB中位数", "EV/EBITDA中位数", "ROE优秀线", "资产负债率警戒线", "净负债/EBITDA警戒线", "备注"],
  ["消费", "通用", 22, 3.0, 12, 0.15, 0.60, 2.5, "品牌和渠道稳定性权重更高"],
  ["科技软件", "通用", 35, 7.0, 22, 0.12, 0.50, 2.0, "未盈利公司需使用收入增长和现金消耗口径"],
  ["制造业", "通用", 18, 2.0, 10, 0.12, 0.65, 2.5, "重点看 ROIC、应收和存货周转"],
  ["公用事业", "通用", 14, 1.5, 9, 0.09, 0.75, 4.0, "分红、监管回报和负债期限结构更重要"],
  ["周期资源", "通用", 10, 1.2, 6, 0.12, 0.65, 2.5, "避免周期顶部低 PE 陷阱"],
  ["银行", "通用", "", 0.8, "", 0.10, "", "", "银行应单独使用 PB、ROE、不良率和资本充足率"],
  ["地产", "通用", 8, 0.7, "", 0.08, 0.75, 3.5, "现金短债比和预售/回款质量优先"],
];
writeRows(industry, "A1", industryRows);
styleHeader(industry.getRange("A1:I1"), "#548235");
styleBody(industry.getRange(`A2:I${industryRows.length}`));
industry.freezePanes.freezeRows(1);

const dictionaryRows = [
  ["字段", "定义/录入口径", "注意事项"],
  ["总市值", "股价乘以总股本，建议与数据源市值核对", "不同市场货币不同，跨市场比较需统一币种"],
  ["企业价值EV", "市值 + 有息债务 + 少数股东权益 + 优先股 - 现金及等价物", "金融行业慎用"],
  ["资本开支", "购建固定资产、无形资产等现金流出", "模板中建议用负数录入，因此 FCF = CFO + Capex"],
  ["自由现金流", "经营现金流 + 资本开支", "资本开支若用正数录入，需要手动改公式"],
  ["FCF收益率", "自由现金流 / 总市值", "应结合资本开支周期和一次性现金流判断"],
  ["行业中位数", "同市场、同行业、同商业模式公司的估值中位数", "不要跨行业直接比较"],
  ["风险标记", "无/轻微/重大", "重大风险包括退市、审计、监管、质押、重大诉讼等"],
  ["总分", "六维评分合计", "70 分以上进入观察，80 分以上进入重点研究"],
];
writeRows(dictionary, "A1", dictionaryRows);
styleHeader(dictionary.getRange("A1:C1"), "#5B9BD5");
styleBody(dictionary.getRange(`A2:C${dictionaryRows.length}`));
dictionary.freezePanes.freezeRows(1);

const sourceRows = [
  ["市场", "来源名称", "链接", "主要用途", "更新/核验说明"],
  ["美股", "SEC EDGAR API", "https://www.sec.gov/search-filings/edgar-application-programming-interfaces", "10-K/10-Q/20-F/6-K、XBRL 公司事实数据", "官方 API，适合后续自动化"],
  ["美股", "NYSE Listings Directory", "https://www.nyse.com/listings_directory/stock", "NYSE 股票池", "交易所入口"],
  ["美股", "Nasdaq Stock Screener", "https://www.nasdaq.com/market-activity/stocks/screener", "Nasdaq 股票池和基础筛选", "交易所入口"],
  ["港股", "HKEXnews 披露易", "https://www.hkexnews.hk/index.htm", "公告、年报、中报", "官方披露入口"],
  ["港股", "HKEX Equities", "https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities?sc_lang=en", "港股证券与行情入口", "交易所入口"],
  ["A股", "巨潮资讯网", "https://www.cninfo.com.cn/new/index", "公告、年报、季报", "官方指定信息披露平台之一"],
  ["A股", "上海证券交易所股票列表", "https://www.sse.com.cn/assortment/stock/list/share/", "上交所股票池", "交易所入口"],
  ["A股", "深圳证券交易所股票列表", "https://www.szse.cn/market/product/stock/list/index.html", "深交所股票池", "交易所入口"],
];
writeRows(sources, "A1", sourceRows);
styleHeader(sources.getRange("A1:E1"), "#8064A2");
styleBody(sources.getRange(`A2:E${sourceRows.length}`));
sources.freezePanes.freezeRows(1);

checks.getRange("A1:H1").merge();
checks.getRange("A1").values = [["检查"]];
styleTitle(checks.getRange("A1:H1"));
checks.getRange("A3:E12").values = [
  ["检查项", "结果", "说明", "处理建议", "公式/口径"],
  ["已录入公司数", "", "公司名称不为空的行数", "若为 0，请先填入输入表", "COUNTIF"],
  ["缺失行业中位数", "", "已录入公司但行业估值中位数缺失", "补充 W/X/Y 列或行业阈值", "COUNTIFS"],
  ["重大风险标记", "", "风险标记为“重大”的公司数量", "无论分数高低都应降级复核", "COUNTIF"],
  ["A/B 级候选数", "", "进入重点深研或重点观察的公司数量", "优先核验来源和财报", "COUNTIF"],
  ["公式错误检查", "", "检查常见 Excel 错误", "若不为 0，请定位输入表公式", "COUNTIF"],
  ["说明", "", "模板是初筛工具，不替代深度研究", "正式使用前先用样本回测", ""],
  ["数据口径", "", "跨市场比较需统一货币和报告期", "同市场同行业比较优先", ""],
  ["行业口径", "", "金融、地产、周期、亏损成长股需专门模型", "不要直接套普通行业阈值", ""],
  ["更新日期", "2026-06-16", "模板创建日期", "后续更新请记录版本", ""],
];
styleHeader(checks.getRange("A3:E3"), "#C55A11");
styleBody(checks.getRange("A4:E12"));
checks.getRange("B4").formulas = [[`=COUNTIF('输入与打分'!C${startRow}:C${endRow},"<>")`]];
checks.getRange("B5").formulas = [[`=COUNTIFS('输入与打分'!C${startRow}:C${endRow},"<>",'输入与打分'!W${startRow}:W${endRow},"")+COUNTIFS('输入与打分'!C${startRow}:C${endRow},"<>",'输入与打分'!X${startRow}:X${endRow},"")+COUNTIFS('输入与打分'!C${startRow}:C${endRow},"<>",'输入与打分'!Y${startRow}:Y${endRow},"")`]];
checks.getRange("B6").formulas = [[`=COUNTIF('输入与打分'!AJ${startRow}:AJ${endRow},"重大")`]];
checks.getRange("B7").formulas = [[`=COUNTIF('输入与打分'!AR${startRow}:AR${endRow},"A*")+COUNTIF('输入与打分'!AR${startRow}:AR${endRow},"B*")`]];
checks.getRange("B8").formulas = [[`=COUNTIF('输入与打分'!A${startRow}:AT${endRow},"#REF!")+COUNTIF('输入与打分'!A${startRow}:AT${endRow},"#DIV/0!")+COUNTIF('输入与打分'!A${startRow}:AT${endRow},"#VALUE!")+COUNTIF('输入与打分'!A${startRow}:AT${endRow},"#NAME?")`]];

for (const sheet of [cover, industry, dictionary, sources, checks]) {
  const used = sheet.getUsedRange();
  used.format.autofitColumns();
  used.format.autofitRows();
}
screen.getRange("A:AT").format.columnWidthPx = 110;
screen.getRange("C:C").format.columnWidthPx = 150;
screen.getRange("D:D").format.columnWidthPx = 120;
screen.getRange("AS:AT").format.columnWidthPx = 220;
screen.getRange("A3:AT3").format.rowHeightPx = 44;

await fs.mkdir(outputDir, { recursive: true });

for (const sheetName of ["封面", "输入与打分", "行业阈值", "数据字典", "来源与口径", "检查"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(outputDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const formulaErrors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});
console.log(formulaErrors.ndjson);

const scorePreview = await workbook.inspect({
  kind: "table",
  range: "输入与打分!A3:AT8",
  include: "values,formulas",
  tableMaxRows: 8,
  tableMaxCols: 46,
  maxChars: 8000,
});
console.log(scorePreview.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(`saved ${outputPath}`);
