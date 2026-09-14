# 金標人工抽樣核對清單（B1–B3）

共 24 題，抽樣種子 20260725（可重現）。
抽樣**刻意偏向風險最高處**：自動稽核 `audit_datasets.py` 對圖譜題只檢查 D3
（金標是否毀損），完全沒有驗證答案內容；口語詞義映射與「較高／趨勢」方向
也是機器無法自我驗證的語意約定。held-out 孿生集為新生成、從未經人工檢視，故優先抽驗。

**每題提供**：題目、金標、**系統實際輸出**（含 EM 判定與路由）、以及自動抽出的財報原始欄位／表格證據。

**填寫方式**：每題在「判定」欄勾選 `正確` / `錯誤` / `存疑`，需要時在「備註」補充。
填完把結果回填 `results/gold_verification_sheet.json` 的 `verdict` 欄即可統計。

> 注意：「EM ✓ 相符」只代表系統輸出與金標字串相同，**不代表金標本身正確**——
> 本次抽驗要驗的正是金標。已知無效題已在標題下標註。

## 速覽

| # | id | 題型 | 來源 | 金標 | EM |
|---:|---|---|---|---|:--:|
| 1 | `ho_graph_nat_001` | investment_graph | held-out | `WPG South Asia Pte. Ltd.` | ✓ |
| 2 | `ho_arch_077` | investment_graph | held-out | `source_kind` | ✓ |
| 3 | `arch_test_076` | investment_graph | dev | `Integrated Solutions Enterprise Eu` | ✓ |
| 4 | `ho_arch_086` | related_party_transaction_graph | held-out | `666,004` | ✓ |
| 5 | `ho_arch_088` | related_party_transaction_graph | held-out | `312,357` | ✓ |
| 6 | `arch_test_090` | related_party_transaction_graph | dev | `2,414` | ✓ |
| 7 | `ho_graph_nat_030` | mainland_investment_graph | held-out | `旺矽科技(蘇州)有限公司；本期認列投資損益：85,157` | ✓ |
| 8 | `arch_test_085` | mainland_investment_graph | dev | `日月光半導體（上海）有限公司；本期認列投資損益：55,724` | ✓ |
| 9 | `ho_graph_nat_022` | supply_chain_graph | held-out | `上游；IC設計` | ✓ |
| 10 | `arch_test_094` | supply_chain_graph | dev | `上游；IP設計/IC設計代工服務` | ✓ |
| 11 | `ho_arch_097` | risk_event_graph | held-out | `營運資金壓力` | ✓ |
| 12 | `ho_arch_098` | risk_event_graph | held-out | `營運資金壓力` | ✓ |
| 13 | `arch_test_096` | risk_event_graph | dev | `營運資金壓力` | ✓ |
| 14 | `ho_arch_033` | cross_company_compare | held-out | `創意電子: 24,791 ｜ 力成科技: 2,286,381` | ✓ |
| 15 | `arch_test_031` | cross_company_compare | dev | `穩懋半導體: 4,743,834 ｜ 環球晶圓: 13,745,45` | ✓ |
| 16 | `ho_arch_059` | cross_period_compare | held-out | `113Q1: 3,683,750 ｜ 113Q3: 1,942,63` | ✓ |
| 17 | `arch_test_055` | cross_period_compare | dev | `113Q3: 276,444,716 ｜ 114Q3: 265,29` | ✓ |
| 18 | `ho_colloq_063` | colloquial_period_compare | held-out | `113Q3: 60,894,868 ｜ 113Q4: 93,872,` | ✓ |
| 19 | `ho_colloq_045` | colloquial_company_compare | held-out | `穩懋半導體: 1,693,801 ｜ 智原科技: 731,331 ｜` | ✓ |
| 20 | `ho_colloq_nat_048` | colloquial_natural | held-out | `3,798,689` | ✓ |
| 21 | `ho_colloq_nat_088` | colloquial_natural | held-out | `1,916,310` | ✓ |
| 22 | `colloq_nat_051` | colloquial_natural | dev | `14,918,538` | ✓ |
| 23 | `ho_arch_020` | direct_numeric_lookup | held-out | `118,423` | ✓ |
| 24 | `ho_colloq_021` | colloquial_single_metric | held-out | `5,714,806` | ✓ |

---

## 01. `ho_graph_nat_001`　[held-out]　investment_graph

- **抽樣理由**：B1 圖譜題（自動稽核只驗 D3）
- **題庫**：`questions/heldout/heldout_graph_nat_30.json`
- **評測檔**：`results/heldout/eval_heldout_graph_nat_30.json`

**題目**

> 大聯大控股在113Q3揭露的投資方大聯大控股投資了哪一家所在地為新加坡的被投資公司？

**金標（expected_answer）**：`WPG South Asia Pte. Ltd.`

**系統輸出（EM ✓ 相符｜路由 graph_rag_local）**：

```
WPG South Asia Pte. Ltd.
```

**對應之財報原始欄位／表格**

```
投資方=大聯大控股 → 被投資=WPG South Asia Pte. Ltd.
鑑別子句={"column": "location", "value": "新加坡"}
來源=（見 investment_graph_output）
```

**請確認**：①鑑別子句（所在地／主要業務）在該公司該期是否**只**對到這一家被投資公司？②被投資公司名稱是否與原表一致（含法人後綴、大小寫）？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 02. `ho_arch_077`　[held-out]　investment_graph

> ⚠ **本題已知無效**：實體欄位被填入語料欄位名 `record_type`, `row_text`, `source_kind`，語意上不可回答。金標與系統輸出同源於同一筆損壞資料，故雖判 EM=1 仍屬**假性通過**。請直接記為「錯誤」，毋須細查。

- **抽樣理由**：B1 圖譜題（自動稽核只驗 D3）
- **題庫**：`questions/heldout/heldout_arch_100.json`
- **評測檔**：`results/heldout/eval_heldout_arch_100.json`

**題目**

> 根據投資關係圖譜，【日月光投資控股】在【114Q2】揭露的投資方【record_type】投資了哪一家所在地為【row_text】的被投資公司？

**金標（expected_answer）**：`source_kind`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
source_kind
```

**對應之財報原始欄位／表格**

```
投資方=record_type → 被投資=source_kind
鑑別子句={"column": "location", "value": "row_text"}
來源=（見 investment_graph_output）
```

**請確認**：①鑑別子句（所在地／主要業務）在該公司該期是否**只**對到這一家被投資公司？②被投資公司名稱是否與原表一致（含法人後綴、大小寫）？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 03. `arch_test_076`　[dev]　investment_graph

- **抽樣理由**：B1 圖譜題（自動稽核只驗 D3）
- **題庫**：`questions/system_architecture_test_questions_100_v4.json`
- **評測檔**：`results/rerun/eval_arch100_v4_v3.json`

**題目**

> 根據投資關係圖譜，【日月光投資控股】在【113Q3】揭露的投資方【A.S.E. Holding Limited】投資了哪一家所在地為【比利時】的被投資公司？

**金標（expected_answer）**：`Integrated Solutions Enterprise Europe`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
Integrated Solutions Enterprise Europe
```

**對應之財報原始欄位／表格**

```
投資方=A.S.E. Holding Limited → 被投資=Integrated Solutions Enterprise Europe
鑑別子句={"column": "location", "value": "比利時"}
來源=reports_csv_output/3711_日月光投資控股/113Q3/3711_113Q3_被投資公司名稱、所在地區…等相關資訊.csv
```

**請確認**：①鑑別子句（所在地／主要業務）在該公司該期是否**只**對到這一家被投資公司？②被投資公司名稱是否與原表一致（含法人後綴、大小寫）？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 04. `ho_arch_086`　[held-out]　related_party_transaction_graph

- **抽樣理由**：B1 圖譜題（三元主鍵唯一性）
- **題庫**：`questions/heldout/heldout_arch_100.json`
- **評測檔**：`results/heldout/eval_heldout_arch_100.json`

**題目**

> 根據關係人交易圖譜，【環球晶圓】在【114Q2】，【GWS】與【MEMC Sdn Bhd】之間的【進貨】交易金額是多少？

**金標（expected_answer）**：`666,004`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
666,004
```

**對應之財報原始欄位／表格**

```
來源表=reports_csv_output/6488_環球晶圓/114Q2/6488_114Q2_母子公司間業務關係及重要交易往來情形.csv
  party=GWS | account=2
  amount_summary=value_2=MEMC LLC; value_3=3; value_4=進貨; value_5=1,146,249; value_6=月結六十天; value_7=3.63 %
來源表=reports_csv_output/6488_環球晶圓/114Q2/6488_114Q2_母子公司間業務關係及重要交易往來情形.csv
  party=GWS | account=2
  amount_summary=value_2=MEMC LLC; value_3=3; value_4=銷貨; value_5=496,320; value_6=月結六十天; value_7=1.57 %
來源表=reports_csv_output/6488_環球晶圓/114Q2/6488_114Q2_母子公司間業務關係及重要交易往來情形.csv
  party=GWS | account=2
  amount_summary=value_2=MEMC SpA; value_3=3; value_4=進貨; value_5=1,797,102; value_6=月結六十天; value_7=5.69 %
來源表=reports_csv_output/6488_環球晶圓/114Q2/6488_114Q2_母子公司間業務關係及重要交易往來情形.csv
  party=GWS | account=2
  amount_summary=value_2=MEMC SpA; value_3=3; value_4=銷貨; value_5=4,281,690; value_6=月結六十天; value_7=13.55 %
（同公司同期符合此交易人之列數：12）
```

**請確認**：①「交易人＋交易對象＋科目」三元鍵在該公司該期是否唯一？②金額是否取自正確欄位（value_5）而非其他欄？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 05. `ho_arch_088`　[held-out]　related_party_transaction_graph

- **抽樣理由**：B1 圖譜題（三元主鍵唯一性）
- **題庫**：`questions/heldout/heldout_arch_100.json`
- **評測檔**：`results/heldout/eval_heldout_arch_100.json`

**題目**

> 根據關係人交易圖譜，【致茂電子】在【113Q1】，【本公司】與【Neworld Electronics Limited】之間的【應收帳款】交易金額是多少？

**金標（expected_answer）**：`312,357`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
312,357
```

**對應之財報原始欄位／表格**

```
來源表=reports_csv_output/2360_致茂電子/113Q1/2360_113Q1_母子公司間業務關係及重要交易往來情形.csv
  party=本公司 | account=0
  amount_summary=value_2=Neworld Electronics Limited; value_3=1; value_4=銷貨收入; value_5=535,984; value_6=註2; value_7=12.00 %
來源表=reports_csv_output/2360_致茂電子/113Q1/2360_113Q1_母子公司間業務關係及重要交易往來情形.csv
  party=本公司 | account=0
  amount_summary=value_2=Neworld Electronics Limited; value_3=1; value_4=應收帳款; value_5=312,357; value_6=一般交易條件; value_7=1.00 %
來源表=reports_csv_output/2360_致茂電子/113Q1/2360_113Q1_母子公司間業務關係及重要交易往來情形.csv
  party=本公司 | account=0
  amount_summary=value_2=中茂電子（上海）有限公司; value_3=1; value_4=銷貨收入; value_5=190,755; value_6=註2; value_7=4.00 %
來源表=reports_csv_output/2360_致茂電子/113Q1/2360_113Q1_母子公司間業務關係及重要交易往來情形.csv
  party=本公司 | account=0
  amount_summary=value_2=中茂電子（上海）有限公司; value_3=1; value_4=應收帳款; value_5=147,561; value_6=一般交易條件; value_7=0.00 %
（同公司同期符合此交易人之列數：16）
```

**請確認**：①「交易人＋交易對象＋科目」三元鍵在該公司該期是否唯一？②金額是否取自正確欄位（value_5）而非其他欄？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 06. `arch_test_090`　[dev]　related_party_transaction_graph

- **抽樣理由**：B1 圖譜題（三元主鍵唯一性）
- **題庫**：`questions/system_architecture_test_questions_100_v4.json`
- **評測檔**：`results/rerun/eval_arch100_v4_v3.json`

**題目**

> 根據關係人交易圖譜，【台灣光罩】在【113Q2】，【iPro Vision Inc.】與【昱嘉科技(股)公司】之間的【銷貨】交易金額是多少？

**金標（expected_answer）**：`2,414`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
2,414
```

**對應之財報原始欄位／表格**

```
來源表=reports_csv_output/2338_台灣光罩/113Q2/2338_113Q2_母子公司間業務關係及重要交易往來情形.csv
  party=iPro Vision Inc. | account=7
  amount_summary=value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %
（同公司同期符合此交易人之列數：1）
```

**請確認**：①「交易人＋交易對象＋科目」三元鍵在該公司該期是否唯一？②金額是否取自正確欄位（value_5）而非其他欄？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 07. `ho_graph_nat_030`　[held-out]　mainland_investment_graph

- **抽樣理由**：B1 圖譜題（大陸投資，題型曾被誤標）
- **題庫**：`questions/heldout/heldout_graph_nat_30.json`
- **評測檔**：`results/heldout/eval_heldout_graph_nat_30.json`

**題目**

> 旺矽科技在114Q3投資之大陸事業中，主要業務為研發、生產LED半導體照明芯片、計算機零部件、LED製程設備、新型電子元器件；電子材料、電子元器件、電子產品、LED製程設備、機械設備及零部件的採購、批發、佣金代理及進出口業務。的被投資公司是哪一家？其本期認列投資損益是多少？

**金標（expected_answer）**：`旺矽科技(蘇州)有限公司；本期認列投資損益：85,157`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
旺矽科技(蘇州)有限公司；本期認列投資損益：85,157
```

**對應之財報原始欄位／表格**

```
來源表=reports_csv_output/6223_旺矽科技/114Q3/6223_114Q3_母子公司間業務關係及重要交易往來情形.csv
  party=旺矽科技(蘇州)有限公司 | account=3
  amount_summary=value_2=旺矽科技(股)公司; value_3=2; value_4=銷貨收入; value_5=1,742; value_6=註4; value_7=0.00 %
來源表=reports_csv_output/6223_旺矽科技/114Q3/6223_114Q3_母子公司間業務關係及重要交易往來情形.csv
  party=旺矽科技(蘇州)有限公司 | account=3
  amount_summary=value_2=旺矽科技(股)公司; value_3=2; value_4=應收帳款; value_5=1,093; value_6=註6; value_7=0.00 %
來源表=reports_csv_output/6223_旺矽科技/114Q3/6223_114Q3_母子公司間業務關係及重要交易往來情形.csv
  party=旺矽科技(蘇州)有限公司 | account=3
  amount_summary=value_2=旺矽科技(股)公司; value_3=2; value_4=佣金收入; value_5=3,705; value_6=註5; value_7=0.00 %
來源表=reports_csv_output/6223_旺矽科技/114Q3/6223_114Q3_母子公司間業務關係及重要交易往來情形.csv
  party=旺矽科技(蘇州)有限公司 | account=3
  amount_summary=value_2=旺矽科技(股)公司; value_3=2; value_4=應收佣金; value_5=665; value_6=註6; value_7=0.00 %
（同公司同期符合此交易人之列數：6）
```

**請確認**：①該筆是否確實來自「轉投資大陸地區之事業相關資訊」表？②「本期認列投資損益」數值與括號負號是否正確？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 08. `arch_test_085`　[dev]　mainland_investment_graph

- **抽樣理由**：B1 圖譜題（大陸投資，題型曾被誤標）
- **題庫**：`questions/system_architecture_test_questions_100_v4.json`
- **評測檔**：`results/rerun/eval_arch100_v4_v3.json`

**題目**

> 根據大陸投資圖譜，【日月光投資控股】在【114Q2】投資之大陸事業中，主要業務為【從事半導體材料製造業務】的被投資公司是哪一家？其本期認列投資損益是多少？

**金標（expected_answer）**：`日月光半導體（上海）有限公司；本期認列投資損益：55,724`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
日月光半導體（上海）有限公司；本期認列投資損益：55,724
```

**對應之財報原始欄位／表格**

```
來源表=reports_csv_output/3711_日月光投資控股/114Q2/3711_114Q2_母子公司間業務關係及重要交易往來情形.csv
  party=日月光半導體（上海）有限公司 | account=2
  amount_summary=value_2=矽品科技（蘇州）有限公司; value_3=子公司對子公司; value_4=其他應收款; value_5=333,021; value_6=註1; value_7=0.00 %
來源表=reports_csv_output/3711_日月光投資控股/114Q2/3711_114Q2_母子公司間業務關係及重要交易往來情形.csv
  party=日月光半導體（上海）有限公司 | account=2
  amount_summary=value_2=日月光半導體（香港）有限公司; value_3=子公司對子公司; value_4=營業收入; value_5=323,501; value_6=註1; value_7=0.00 %
來源表=reports_csv_output/3711_日月光投資控股/114Q2/3711_114Q2_轉投資大陸地區之事業相關資訊.csv
  party=日月光半導體（上海）有限公司 | account=從事半導體材料製造業務
  amount_summary=本期期初自台灣匯出累積投資金額=1,497,683; 本期期末自台灣匯出累積投資金額=1,497,683; 被投資公司本期損益=46,939; 本期認列投資損益=55,724; 截至本期止已匯回台灣之投資收益=0
（同公司同期符合此交易人之列數：3）
```

**請確認**：①該筆是否確實來自「轉投資大陸地區之事業相關資訊」表？②「本期認列投資損益」數值與括號負號是否正確？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 09. `ho_graph_nat_022`　[held-out]　supply_chain_graph

- **抽樣理由**：B1 圖譜題（單一階段假設）
- **題庫**：`questions/heldout/heldout_graph_nat_30.json`
- **評測檔**：`results/heldout/eval_heldout_graph_nat_30.json`

**題目**

> 尼克森屬於哪個產業鏈階段與 segment？

**金標（expected_answer）**：`上游；IC設計`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
上游；IC設計
```

**對應之財報原始欄位／表格**

```
company_table.csv: 尼克森 → stage=上游 segment=IC設計 market=本國上櫃公司
（該公司在表中共 1 列；>1 列代表多階段）
```

**請確認**：①該公司是否確實只被分到單一階段（多階段者不應入題）？②stage／segment 的分號格式是否與系統輸出一致？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 10. `arch_test_094`　[dev]　supply_chain_graph

- **抽樣理由**：B1 圖譜題（單一階段假設）
- **題庫**：`questions/system_architecture_test_questions_100_v4.json`
- **評測檔**：`results/rerun/eval_arch100_v4_v3.json`

**題目**

> 根據半導體產業鏈圖譜，【巨有科技】屬於哪個產業鏈階段與 segment？

**金標（expected_answer）**：`上游；IP設計/IC設計代工服務`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
上游；IP設計/IC設計代工服務
```

**對應之財報原始欄位／表格**

```
company_table.csv: 巨有科技 → stage=上游 segment=IP設計/IC設計代工服務 market=本國上櫃公司
（該公司在表中共 1 列；>1 列代表多階段）
```

**請確認**：①該公司是否確實只被分到單一階段（多階段者不應入題）？②stage／segment 的分號格式是否與系統輸出一致？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 11. `ho_arch_097`　[held-out]　risk_event_graph

- **抽樣理由**：B1 圖譜題（風險標籤集合完整性）
- **題庫**：`questions/heldout/heldout_arch_100.json`
- **評測檔**：`results/heldout/eval_heldout_arch_100.json`

**題目**

> 根據風險事件圖譜，【群聯電子】在【114Q2】的財務科目【其他應付款增加（減少） Increase (decrease) in other payable】被標記為哪一類風險候選？

**金標（expected_answer）**：`營運資金壓力`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
營運資金壓力
```

**對應之財報原始欄位／表格**

```
風險標籤（金標）：營運資金壓力
對應科目於 facts 之列數：2；表別=['現金流量表']
→ 請至 risk_event_graph_output 確認該科目該期的全部風險標籤是否與金標集合相同
```

**請確認**：①該科目在該期對應的風險標籤是否**全部**列出（多標籤以 ; 分隔）？②標籤順序不影響評分，但集合須完全相同。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 12. `ho_arch_098`　[held-out]　risk_event_graph

- **抽樣理由**：B1 圖譜題（風險標籤集合完整性）
- **題庫**：`questions/heldout/heldout_arch_100.json`
- **評測檔**：`results/heldout/eval_heldout_arch_100.json`

**題目**

> 根據風險事件圖譜，【聯詠科技】在【114Q3】的財務科目【應收帳款淨額 Accounts receivable, net】被標記為哪一類風險候選？

**金標（expected_answer）**：`營運資金壓力`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
營運資金壓力
```

**對應之財報原始欄位／表格**

```
風險標籤（金標）：營運資金壓力
對應科目於 facts 之列數：3；表別=['資產負債表']
→ 請至 risk_event_graph_output 確認該科目該期的全部風險標籤是否與金標集合相同
```

**請確認**：①該科目在該期對應的風險標籤是否**全部**列出（多標籤以 ; 分隔）？②標籤順序不影響評分，但集合須完全相同。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 13. `arch_test_096`　[dev]　risk_event_graph

- **抽樣理由**：B1 圖譜題（風險標籤集合完整性）
- **題庫**：`questions/system_architecture_test_questions_100_v4.json`
- **評測檔**：`results/rerun/eval_arch100_v4_v3.json`

**題目**

> 根據風險事件圖譜，【旺矽科技】在【114Q4】的財務科目【其他應付款增加（減少） Increase (decrease) in other payable】被標記為哪一類風險候選？

**金標（expected_answer）**：`營運資金壓力`

**系統輸出（EM ✓ 相符｜路由 graph_rag_topology）**：

```
營運資金壓力
```

**對應之財報原始欄位／表格**

```
風險標籤（金標）：營運資金壓力
對應科目於 facts 之列數：2；表別=['現金流量表']
→ 請至 risk_event_graph_output 確認該科目該期的全部風險標籤是否與金標集合相同
```

**請確認**：①該科目在該期對應的風險標籤是否**全部**列出（多標籤以 ; 分隔）？②標籤順序不影響評分，但集合須完全相同。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 14. `ho_arch_033`　[held-out]　cross_company_compare

- **抽樣理由**：B2 語意：「較高」方向
- **題庫**：`questions/heldout/heldout_arch_100.json`
- **評測檔**：`results/heldout/eval_heldout_arch_100.json`

**題目**

> 請比較【創意電子】與【力成科技】在【114Q1】的【應付設備款 Payable on machinery and equipment】（2025年3月31日 2025/3/31）分別是多少？

**金標（expected_answer）**：`創意電子: 24,791 ｜ 力成科技: 2,286,381`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
創意電子: 24,791 ｜ 力成科技: 2,286,381
```

**對應之財報原始欄位／表格**

```
[創意電子 114Q1] 當期欄（2025 年）共 1 列：
    資產負債表 | 2025年3月31日 2025/3/31 | 24,791
    （非當期欄另有 2 列，例：2024年12月31日 2024/12/31 = 94,955）
[力成科技 114Q1] 當期欄（2025 年）共 1 列：
    資產負債表 | 2025年3月31日 2025/3/31 | 2,286,381
    （非當期欄另有 2 列，例：2024年12月31日 2024/12/31 = 3,049,495）
```

**請確認**：①兩家的數值是否都取自該期**當期欄**（非去年同期比較欄）？②（若有）「較高」判定方向是否正確——注意括號代表負數。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 15. `arch_test_031`　[dev]　cross_company_compare

- **抽樣理由**：B2 語意：「較高」方向
- **題庫**：`questions/system_architecture_test_questions_100_v4.json`
- **評測檔**：`results/rerun/eval_arch100_v4_v3.json`

**題目**

> 請比較【穩懋半導體】與【環球晶圓】在【113Q1】的【一年或一營業週期內到期或執行賣回權公司債 Bonds payable, current portion】（2023年12月31日 2023/12/31）分別是多少？

**金標（expected_answer）**：`穩懋半導體: 4,743,834 ｜ 環球晶圓: 13,745,450`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
穩懋半導體: 4,743,834 ｜ 環球晶圓: 13,745,450
```

**對應之財報原始欄位／表格**

```
[穩懋半導體 113Q1] 當期欄（2024 年）共 1 列：
    資產負債表 | 2024年3月31日 2024/3/31 | 0
    （非當期欄另有 2 列，例：2023年12月31日 2023/12/31 = 4,743,834）
[環球晶圓 113Q1] 當期欄（2024 年）共 1 列：
    資產負債表 | 2024年3月31日 2024/3/31 | 13,416,852
    （非當期欄另有 2 列，例：2023年12月31日 2023/12/31 = 13,745,450）
```

**請確認**：①兩家的數值是否都取自該期**當期欄**（非去年同期比較欄）？②（若有）「較高」判定方向是否正確——注意括號代表負數。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 16. `ho_arch_059`　[held-out]　cross_period_compare

- **抽樣理由**：B2 語意：「趨勢」方向與當期欄
- **題庫**：`questions/heldout/heldout_arch_100.json`
- **評測檔**：`results/heldout/eval_heldout_arch_100.json`

**題目**

> 請比較【聯華電子】在【113Q1】與【113Q3】的【其他應收款 Other receivables】各是多少（各期均取該期當期欄）？

**金標（expected_answer）**：`113Q1: 3,683,750 ｜ 113Q3: 1,942,631`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
113Q1: 3,683,750 ｜ 113Q3: 1,942,631
```

**對應之財報原始欄位／表格**

```
[聯華電子 113Q1] 當期欄（2024 年）共 1 列：
    資產負債表 | 2024年3月31日 2024/3/31 | 3,683,750
    （非當期欄另有 2 列，例：2023年12月31日 2023/12/31 = 2,707,400）
[聯華電子 113Q3] 當期欄（2024 年）共 1 列：
    資產負債表 | 2024年9月30日 2024/9/30 | 1,942,631
    （非當期欄另有 2 列，例：2023年12月31日 2023/12/31 = 2,707,400）
```

**請確認**：①兩期是否**各自**取自該期當期欄（同一欄不得套用於兩期）？②（若有）「趨勢」方向是否正確。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 17. `arch_test_055`　[dev]　cross_period_compare

- **抽樣理由**：B2 語意：「趨勢」方向與當期欄
- **題庫**：`questions/system_architecture_test_questions_100_v4.json`
- **評測檔**：`results/rerun/eval_arch100_v4_v3.json`

**題目**

> 請比較【聯華電子】在【113Q3】與【114Q3】的【不動產、廠房及設備 Property, plant and equipment】各是多少（各期均取該期當期欄）？

**金標（expected_answer）**：`113Q3: 276,444,716 ｜ 114Q3: 265,290,915`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
113Q3: 276,444,716 ｜ 114Q3: 265,290,915
```

**對應之財報原始欄位／表格**

```
[聯華電子 113Q3] 當期欄（2024 年）共 1 列：
    資產負債表 | 2024年9月30日 2024/9/30 | 276,444,716
    （非當期欄另有 2 列，例：2023年12月31日 2023/12/31 = 239,123,248）
[聯華電子 114Q3] 當期欄（2025 年）共 1 列：
    資產負債表 | 2025年9月30日 2025/9/30 | 265,290,915
    （非當期欄另有 2 列，例：2024年12月31日 2024/12/31 = 279,059,037）
```

**請確認**：①兩期是否**各自**取自該期當期欄（同一欄不得套用於兩期）？②（若有）「趨勢」方向是否正確。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 18. `ho_colloq_063`　[held-out]　colloquial_period_compare

- **抽樣理由**：B2 語意：口語跨期
- **題庫**：`questions/heldout/heldout_colloq_100.json`
- **評測檔**：`results/heldout/eval_heldout_colloq_100.json`

**題目**

> 聯華電子從113Q3到113Q4，營業活動之淨現金流入（流出）有變多嗎？（科目：【營業活動之淨現金流入（流出） Net cash flows from (used in) operating activities】）（各期均取該期當期欄）？

**金標（expected_answer）**：`113Q3: 60,894,868 ｜ 113Q4: 93,872,042 ｜ 趨勢: 上升`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
113Q3: 60,894,868 ｜ 113Q4: 93,872,042 ｜ 趨勢: 上升
```

**對應之財報原始欄位／表格**

```
[聯華電子 113Q3] 當期欄（2024 年）共 1 列：
    現金流量表 | 2024年1月1日至9月30日 2024/1/1To9/30 | 60,894,868
    （非當期欄另有 1 列，例：2023年1月1日至9月30日 2023/1/1To9/30 = 59,782,937）
[聯華電子 113Q4] 當期欄（2024 年）共 1 列：
    現金流量表 | 2024年1月1日至12月31日 2024/1/1To12/31 | 93,872,042
    （非當期欄另有 1 列，例：2023年1月1日至12月31日 2023/1/1To12/31 = 85,999,709）
```

**請確認**：①同上；②口語題幹是否足以唯一定位該科目。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 19. `ho_colloq_045`　[held-out]　colloquial_company_compare

- **抽樣理由**：B2 語意：口語跨公司
- **題庫**：`questions/heldout/heldout_colloq_100.json`
- **評測檔**：`results/heldout/eval_heldout_colloq_100.json`

**題目**

> 穩懋半導體跟智原科技在114Q4的數字差多少？先列出兩家的數字（科目：【母公司業主（淨利／損） Profit (loss), attributable to owners of parent】）（2025年1月1日至12月31日 2025/1/1To12/31）

**金標（expected_answer）**：`穩懋半導體: 1,693,801 ｜ 智原科技: 731,331 ｜ 較高: 穩懋半導體`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
穩懋半導體: 1,693,801 ｜ 智原科技: 731,331 ｜ 較高: 穩懋半導體
```

**對應之財報原始欄位／表格**

```
[穩懋半導體 114Q4] 當期欄（2025 年）共 1 列：
    綜合損益表 | 2025年1月1日至12月31日 2025/1/1To12/31 | 1,693,801
    （非當期欄另有 1 列，例：2024年1月1日至12月31日 2024/1/1To12/31 = 768,133）
[智原科技 114Q4] 當期欄（2025 年）共 1 列：
    綜合損益表 | 2025年1月1日至12月31日 2025/1/1To12/31 | 731,331
    （非當期欄另有 1 列，例：2024年1月1日至12月31日 2024/1/1To12/31 = 1,041,465）
```

**請確認**：①同跨公司題；②口語題幹是否足以唯一定位該科目。

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 20. `ho_colloq_nat_048`　[held-out]　colloquial_natural

- **抽樣理由**：B2 語意：口語詞 → 標準科目之映射
- **題庫**：`questions/heldout/heldout_colloq_nat_100.json`
- **評測檔**：`results/heldout/eval_heldout_colloq_nat_100.json`

**題目**

> 家登113Q3手上現金有多少？

**金標（expected_answer）**：`3,798,689`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
3,798,689
```

**對應之財報原始欄位／表格**

```
[家登精密工業 113Q3] 當期欄（2024 年）共 1 列：
    資產負債表 | 2024年9月30日 2024/9/30 | 3,798,689
    （非當期欄另有 2 列，例：2023年12月31日 2023/12/31 = 4,004,779）
```

**請確認**：①**口語詞與標準科目的映射是否合理**（如「欠了多少錢」→負債總計、「本業賺多少」→營業利益）？②金標是否為該期當期欄唯一值？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 21. `ho_colloq_nat_088`　[held-out]　colloquial_natural

- **抽樣理由**：B2 語意：口語詞 → 標準科目之映射
- **題庫**：`questions/heldout/heldout_colloq_nat_100.json`
- **評測檔**：`results/heldout/eval_heldout_colloq_nat_100.json`

**題目**

> 景碩114Q1營業活動現金流多少？

**金標（expected_answer）**：`1,916,310`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
1,916,310
```

**對應之財報原始欄位／表格**

```
[景碩科技 114Q1] 當期欄（2025 年）共 1 列：
    現金流量表 | 2025年1月1日至3月31日 2025/1/1To3/31 | 1,916,310
    （非當期欄另有 1 列，例：2024年1月1日至3月31日 2024/1/1To3/31 = 1,393,011）
```

**請確認**：①**口語詞與標準科目的映射是否合理**（如「欠了多少錢」→負債總計、「本業賺多少」→營業利益）？②金標是否為該期當期欄唯一值？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 22. `colloq_nat_051`　[dev]　colloquial_natural

- **抽樣理由**：B2 語意：口語詞 → 標準科目之映射
- **題庫**：`questions/customer_colloquial_natural_100.json`
- **評測檔**：`results/rerun/eval_colloq_nat100_fix16.json`

**題目**

> 群聯113Q3現金部位多大？

**金標（expected_answer）**：`14,918,538`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
14,918,538
```

**對應之財報原始欄位／表格**

```
[群聯電子 113Q3] 當期欄（2024 年）共 1 列：
    資產負債表 | 2024年9月30日 2024/9/30 | 14,918,538
    （非當期欄另有 2 列，例：2023年12月31日 2023/12/31 = 14,220,367）
```

**請確認**：①**口語詞與標準科目的映射是否合理**（如「欠了多少錢」→負債總計、「本業賺多少」→營業利益）？②金標是否為該期當期欄唯一值？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 23. `ho_arch_020`　[held-out]　direct_numeric_lookup

- **抽樣理由**：B3 對照：結構化直查（風險最低，作為基準）
- **題庫**：`questions/heldout/heldout_arch_100.json`
- **評測檔**：`results/heldout/eval_heldout_arch_100.json`

**題目**

> 請查詢【瑞昱半導體】在【114Q4】的【利息費用】（2025年1月1日至12月31日）是多少？

**金標（expected_answer）**：`118,423`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
118,423
```

**對應之財報原始欄位／表格**

```
[瑞昱半導體 114Q4] 當期欄（2025 年）共 1 列：
    財務成本 | 2025年1月1日至12月31日 | 118,423
    （非當期欄另有 1 列，例：2024年1月1日至12月31日 = 288,398）
```

**請確認**：①題幹明寫的欄位標頭與金標是否一致？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---

## 24. `ho_colloq_021`　[held-out]　colloquial_single_metric

- **抽樣理由**：B3 對照：口語直查
- **題庫**：`questions/heldout/heldout_colloq_100.json`
- **評測檔**：`results/heldout/eval_heldout_colloq_100.json`

**題目**

> 幫我看一下智原科技113Q4現金水位是多少（科目：【期初現金及約當現金餘額 Cash and cash equivalents at beginning of period】）（表：【現金流量表】）（2024年1月1日至12月31日 2024/1/1To12/31）

**金標（expected_answer）**：`5,714,806`

**系統輸出（EM ✓ 相符｜路由 direct_lookup）**：

```
5,714,806
```

**對應之財報原始欄位／表格**

```
[智原科技 113Q4] 當期欄（2024 年）共 1 列：
    現金流量表 | 2024年1月1日至12月31日 2024/1/1To12/31 | 5,714,806
    （非當期欄另有 1 列，例：2023年1月1日至12月31日 2023/1/1To12/31 = 4,872,818）
```

**請確認**：①題幹括號內的科目／表／欄位與金標是否一致？

| 判定 | 備註 |
|---|---|
| ☐ 正確　☐ 錯誤　☐ 存疑 |  |

---
