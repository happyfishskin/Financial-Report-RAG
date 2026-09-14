# 資料集金標稽核報告

稽核對象：原始資料集

語料：`__all_company_all_period_numeric_facts.csv`（211,263 筆事實）

## 各資料集缺陷數

| 資料集 | 題數 | 缺陷題數 |
|---|---:|---:|
| `customer_colloquial_test_questions_100.json` | 100 | 55 |
| `customer_colloquial_test_questions_100_v2.json` | 100 | 30 |
| `customer_colloquial_natural_100.json` | 100 | 0 |
| `system_architecture_test_questions_100.json` | 100 | 29 |
| `system_architecture_test_questions_100_v2.json` | 100 | 29 |
| `system_architecture_test_questions_10_selected.json` | 10 | 1 |
| `system_architecture_test_questions_10_selected_alt.json` | 10 | 1 |
| `system_architecture_wrong_questions_dataset.json` | 24 | 16 |
| `system_architecture_wrong_questions_dataset_v2.json` | 24 | 16 |
| `ratio_questions_50.json` | 50 | 0 |
| `ratio_cross_company_50.json` | 50 | 0 |
| `system_architecture_test_questions_100_v4.json` | 100 | 0 |
| `graph_capability_explicit.json` | 30 | 0 |
| `graph_routing_natural.json` | 30 | 0 |

**合計缺陷 177 題**（另有 0 題題目文字已明寫欄位標頭，判定為非缺陷）

## 缺陷類型分佈

| 代碼 | 題數 | 說明 |
|---|---:|---|
| `D4_same_value_two_period` | 52 | 跨期比較題兩期金標同值，實際兩期不同 |
| `D3_corrupt_gold` | 44 | 金標為附註代號／整列傾印，非可評分答案 |
| `D11_row_index_in_question` | 32 | 題幹使用無語意的原表列序號作為識別鍵 |
| `D2_wrong_column_period` | 18 | 金標取自去年同期比較欄（題目未指定欄位） |
| `D7_prior_period_source` | 14 | 金標取自「去年同期」報表，非所問期間之當期值 |
| `D5_ambiguous_row` | 7 | 同科目同欄位對到多列相異值 |
| `D10_question_type_mismatch` | 6 | question_type 與來源表不符（如大陸投資題標成關係人交易） |
| `D6_item_name_mismatch` | 4 | 科目名中英文指向不同科目（語料表頭誤併） |

## D10_question_type_mismatch（6 題）

**[arch_test_084]** 根據關係人交易圖譜，【群聯電子】在【113Q2】的【電子產品軟硬件的研發、生產、銷售、技術服務等相關業務及一般投資業】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`合肥芯鵬技術有限公司；本期期初自台灣匯出累積投資金額=0; 本期期末自台灣匯出累積投資金額=0; 被投資公司本期損益=( 38,763 ); 本期認列投資損益=( 9,393 ); 截至本期止已匯回台灣之投資收益=0`
- 定位：8299 / 113Q2 / 轉投資大陸地區之事業相關資訊 /  / 
- 診斷：來源表為「轉投資大陸地區之事業相關資訊」，question_type 應為 mainland_investment_graph，實為 related_party_transaction_graph

**[arch_test_085]** 根據關係人交易圖譜，【日月光投資控股】在【114Q2】的【從事半導體材料製造業務】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`日月光半導體（上海）有限公司；本期期初自台灣匯出累積投資金額=1,497,683; 本期期末自台灣匯出累積投資金額=1,497,683; 被投資公司本期損益=46,939; 本期認列投資損益=55,724; 截至本期止已匯回台灣之投資收益=0`
- 定位：3711 / 114Q2 / 轉投資大陸地區之事業相關資訊 /  / 
- 診斷：來源表為「轉投資大陸地區之事業相關資訊」，question_type 應為 mainland_investment_graph，實為 related_party_transaction_graph

**[arch_test_084]** 根據關係人交易圖譜，【群聯電子】在【113Q2】的【電子產品軟硬件的研發、生產、銷售、技術服務等相關業務及一般投資業】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`合肥芯鵬技術有限公司；本期期初自台灣匯出累積投資金額=0; 本期期末自台灣匯出累積投資金額=0; 被投資公司本期損益=( 38,763 ); 本期認列投資損益=( 9,393 ); 截至本期止已匯回台灣之投資收益=0`
- 定位：8299 / 113Q2 / 轉投資大陸地區之事業相關資訊 /  / 
- 診斷：來源表為「轉投資大陸地區之事業相關資訊」，question_type 應為 mainland_investment_graph，實為 related_party_transaction_graph

**[arch_test_085]** 根據關係人交易圖譜，【日月光投資控股】在【114Q2】的【從事半導體材料製造業務】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`日月光半導體（上海）有限公司；本期期初自台灣匯出累積投資金額=1,497,683; 本期期末自台灣匯出累積投資金額=1,497,683; 被投資公司本期損益=46,939; 本期認列投資損益=55,724; 截至本期止已匯回台灣之投資收益=0`
- 定位：3711 / 114Q2 / 轉投資大陸地區之事業相關資訊 /  / 
- 診斷：來源表為「轉投資大陸地區之事業相關資訊」，question_type 應為 mainland_investment_graph，實為 related_party_transaction_graph

**[arch_selected_08]** 根據關係人交易圖譜，【群聯電子】在【113Q2】的【電子產品軟硬件的研發、生產、銷售、技術服務等相關業務及一般投資業】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_10_selected.json`　題型：related_party_transaction_graph
- 現行金標：`合肥芯鵬技術有限公司；本期期初自台灣匯出累積投資金額=0; 本期期末自台灣匯出累積投資金額=0; 被投資公司本期損益=( 38,763 ); 本期認列投資損益=( 9,393 ); 截至本期止已匯回台灣之投資收益=0`
- 定位：8299 / 113Q2 / 轉投資大陸地區之事業相關資訊 /  / 
- 診斷：來源表為「轉投資大陸地區之事業相關資訊」，question_type 應為 mainland_investment_graph，實為 related_party_transaction_graph

**[arch_selected_alt_08]** 根據關係人交易圖譜，【日月光投資控股】在【114Q2】的【從事半導體材料製造業務】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_10_selected_alt.json`　題型：related_party_transaction_graph
- 現行金標：`日月光半導體（上海）有限公司；本期期初自台灣匯出累積投資金額=1,497,683; 本期期末自台灣匯出累積投資金額=1,497,683; 被投資公司本期損益=46,939; 本期認列投資損益=55,724; 截至本期止已匯回台灣之投資收益=0`
- 定位：3711 / 114Q2 / 轉投資大陸地區之事業相關資訊 /  / 
- 診斷：來源表為「轉投資大陸地區之事業相關資訊」，question_type 應為 mainland_investment_graph，實為 related_party_transaction_graph


## D11_row_index_in_question（32 題）

**[arch_test_081]** 根據關係人交易圖譜，【大聯大控股】在【114Q1】的【3】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`World Peace International (South Asia) Pte Ltd.；value_2=WPG South Asia Pte. Ltd.; value_3=3; value_4=其他應收款; value_5=348,056; value_6=註6; value_7=0.08 %`
- 定位：3702 / 114Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【3】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_082]** 根據關係人交易圖譜，【穩懋半導體】在【114Q2】的【2】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`江蘇全穩康源農業發展有限公司；value_2=江蘇全穩農牧科技有限公司; value_3=3; value_4=其他應付款-關係人; value_5=110,510; value_6=與一般交易同; value_7=0.18 %`
- 定位：3105 / 114Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【2】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_083]** 根據關係人交易圖譜，【家登精密工業】在【113Q1】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`家登精密工業股份有限公司；value_2=上海家登貿易有限公司; value_3=1; value_4=服務費用; value_5=28,658; value_7=2.00 %`
- 定位：3680 / 113Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_086]** 根據關係人交易圖譜，【華邦電子】在【114Q4】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`華邦公司；value_2=WECA公司; value_3=母公司對子公司; value_4=其他應付款; value_5=229,127; value_6=0; value_7=0.00 %`
- 定位：2344 / 114Q4 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_087]** 根據關係人交易圖譜，【智原科技】在【113Q2】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`智原科技(股)公司；value_2=智原科技(上海)有限公司; value_3=1; value_4=合約資產; value_5=8,602; value_6=依合約而定; value_7=0.05 %`
- 定位：3035 / 113Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_088]** 根據關係人交易圖譜，【京鼎精密科技】在【114Q4】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`京鼎精密科技股份有限公司；value_2=SUCCESSPRAISECORPORATION; value_3=(1); value_4=進貨; value_5=7,877,323; value_6=發票日起45天; value_7=38.00 %`
- 定位：3413 / 114Q4 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_089]** 根據關係人交易圖譜，【台灣光罩】在【114Q1】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`台灣光罩(股)公司；value_2=友縳投資(股)公司; value_3=3; value_4=利息收入; value_5=1,997; value_6=約定時間收付款; value_7=0.12 %`
- 定位：2338 / 114Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_090]** 根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`iPro Vision Inc.；value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %`
- 定位：2338 / 113Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【7】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_081]** 根據關係人交易圖譜，【大聯大控股】在【114Q1】的【3】中，與【WPG South Asia Pte. Ltd.】之間的【其他應收款】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`World Peace International (South Asia) Pte Ltd.；value_2=WPG South Asia Pte. Ltd.; value_3=3; value_4=其他應收款; value_5=348,056; value_6=註6; value_7=0.08 %`
- 定位：3702 / 114Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【3】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_082]** 根據關係人交易圖譜，【穩懋半導體】在【114Q2】的【2】中，與【江蘇全穩農牧科技有限公司】之間的【其他應付款-關係人】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`江蘇全穩康源農業發展有限公司；value_2=江蘇全穩農牧科技有限公司; value_3=3; value_4=其他應付款-關係人; value_5=110,510; value_6=與一般交易同; value_7=0.18 %`
- 定位：3105 / 114Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【2】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_083]** 根據關係人交易圖譜，【家登精密工業】在【113Q1】的【0】中，與【上海家登貿易有限公司】之間的【服務費用】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`家登精密工業股份有限公司；value_2=上海家登貿易有限公司; value_3=1; value_4=服務費用; value_5=28,658; value_7=2.00 %`
- 定位：3680 / 113Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_086]** 根據關係人交易圖譜，【華邦電子】在【114Q4】的【0】中，與【WECA公司】之間的【其他應付款】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`華邦公司；value_2=WECA公司; value_3=母公司對子公司; value_4=其他應付款; value_5=229,127; value_6=0; value_7=0.00 %`
- 定位：2344 / 114Q4 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_087]** 根據關係人交易圖譜，【智原科技】在【113Q2】的【0】中，與【智原科技(上海)有限公司】之間的【合約資產】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`智原科技(股)公司；value_2=智原科技(上海)有限公司; value_3=1; value_4=合約資產; value_5=8,602; value_6=依合約而定; value_7=0.05 %`
- 定位：3035 / 113Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_088]** 根據關係人交易圖譜，【京鼎精密科技】在【114Q4】的【0】中，與【SUCCESSPRAISECORPORATION】之間的【進貨】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`京鼎精密科技股份有限公司；value_2=SUCCESSPRAISECORPORATION; value_3=(1); value_4=進貨; value_5=7,877,323; value_6=發票日起45天; value_7=38.00 %`
- 定位：3413 / 114Q4 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_089]** 根據關係人交易圖譜，【台灣光罩】在【114Q1】的【0】中，與【友縳投資(股)公司】之間的【利息收入】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`台灣光罩(股)公司；value_2=友縳投資(股)公司; value_3=3; value_4=利息收入; value_5=1,997; value_6=約定時間收付款; value_7=0.12 %`
- 定位：2338 / 114Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_test_090]** 根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`iPro Vision Inc.；value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %`
- 定位：2338 / 113Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【7】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_017]** 根據關係人交易圖譜，【大聯大控股】在【114Q1】的【3】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`World Peace International (South Asia) Pte Ltd.；value_2=WPG South Asia Pte. Ltd.; value_3=3; value_4=其他應收款; value_5=348,056; value_6=註6; value_7=0.08 %`
- 定位：3702 / 114Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【3】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_018]** 根據關係人交易圖譜，【穩懋半導體】在【114Q2】的【2】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`江蘇全穩康源農業發展有限公司；value_2=江蘇全穩農牧科技有限公司; value_3=3; value_4=其他應付款-關係人; value_5=110,510; value_6=與一般交易同; value_7=0.18 %`
- 定位：3105 / 114Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【2】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_019]** 根據關係人交易圖譜，【家登精密工業】在【113Q1】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`家登精密工業股份有限公司；value_2=上海家登貿易有限公司; value_3=1; value_4=服務費用; value_5=28,658; value_7=2.00 %`
- 定位：3680 / 113Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_020]** 根據關係人交易圖譜，【華邦電子】在【114Q4】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`華邦公司；value_2=WECA公司; value_3=母公司對子公司; value_4=其他應付款; value_5=229,127; value_6=0; value_7=0.00 %`
- 定位：2344 / 114Q4 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_021]** 根據關係人交易圖譜，【智原科技】在【113Q2】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`智原科技(股)公司；value_2=智原科技(上海)有限公司; value_3=1; value_4=合約資產; value_5=8,602; value_6=依合約而定; value_7=0.05 %`
- 定位：3035 / 113Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_022]** 根據關係人交易圖譜，【京鼎精密科技】在【114Q4】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`京鼎精密科技股份有限公司；value_2=SUCCESSPRAISECORPORATION; value_3=(1); value_4=進貨; value_5=7,877,323; value_6=發票日起45天; value_7=38.00 %`
- 定位：3413 / 114Q4 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_023]** 根據關係人交易圖譜，【台灣光罩】在【114Q1】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`台灣光罩(股)公司；value_2=友縳投資(股)公司; value_3=3; value_4=利息收入; value_5=1,997; value_6=約定時間收付款; value_7=0.12 %`
- 定位：2338 / 114Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【0】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_024]** 根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`iPro Vision Inc.；value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %`
- 定位：2338 / 113Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【7】涉及」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_017]** 根據關係人交易圖譜，【大聯大控股】在【114Q1】的【3】中，與【WPG South Asia Pte. Ltd.】之間的【其他應收款】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`World Peace International (South Asia) Pte Ltd.；value_2=WPG South Asia Pte. Ltd.; value_3=3; value_4=其他應收款; value_5=348,056; value_6=註6; value_7=0.08 %`
- 定位：3702 / 114Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【3】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_018]** 根據關係人交易圖譜，【穩懋半導體】在【114Q2】的【2】中，與【江蘇全穩農牧科技有限公司】之間的【其他應付款-關係人】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`江蘇全穩康源農業發展有限公司；value_2=江蘇全穩農牧科技有限公司; value_3=3; value_4=其他應付款-關係人; value_5=110,510; value_6=與一般交易同; value_7=0.18 %`
- 定位：3105 / 114Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【2】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_019]** 根據關係人交易圖譜，【家登精密工業】在【113Q1】的【0】中，與【上海家登貿易有限公司】之間的【服務費用】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`家登精密工業股份有限公司；value_2=上海家登貿易有限公司; value_3=1; value_4=服務費用; value_5=28,658; value_7=2.00 %`
- 定位：3680 / 113Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_020]** 根據關係人交易圖譜，【華邦電子】在【114Q4】的【0】中，與【WECA公司】之間的【其他應付款】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`華邦公司；value_2=WECA公司; value_3=母公司對子公司; value_4=其他應付款; value_5=229,127; value_6=0; value_7=0.00 %`
- 定位：2344 / 114Q4 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_021]** 根據關係人交易圖譜，【智原科技】在【113Q2】的【0】中，與【智原科技(上海)有限公司】之間的【合約資產】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`智原科技(股)公司；value_2=智原科技(上海)有限公司; value_3=1; value_4=合約資產; value_5=8,602; value_6=依合約而定; value_7=0.05 %`
- 定位：3035 / 113Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_022]** 根據關係人交易圖譜，【京鼎精密科技】在【114Q4】的【0】中，與【SUCCESSPRAISECORPORATION】之間的【進貨】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`京鼎精密科技股份有限公司；value_2=SUCCESSPRAISECORPORATION; value_3=(1); value_4=進貨; value_5=7,877,323; value_6=發票日起45天; value_7=38.00 %`
- 定位：3413 / 114Q4 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_023]** 根據關係人交易圖譜，【台灣光罩】在【114Q1】的【0】中，與【友縳投資(股)公司】之間的【利息收入】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`台灣光罩(股)公司；value_2=友縳投資(股)公司; value_3=3; value_4=利息收入; value_5=1,997; value_6=約定時間收付款; value_7=0.12 %`
- 定位：2338 / 114Q1 /  /  / 
- 診斷：題幹含無語意列序號「的【0】中」，應改用語意主鍵（交易人／交易對象／科目）

**[arch_wrong_024]** 根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】中，與【昱嘉科技(股)公司】之間的【銷貨】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`iPro Vision Inc.；value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %`
- 定位：2338 / 113Q2 /  /  / 
- 診斷：題幹含無語意列序號「的【7】中」，應改用語意主鍵（交易人／交易對象／科目）


## D2_wrong_column_period（18 題）

**[customer_colloquial_002]** 幫我看一下京鼎精密科技114Q4現金水位是多少

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`7,526,593`
- 定位：3413 / 114Q4 / 現金流量表 / 資產負債表帳列之現金及約當現金 Cash and cash equivalents reported in the statement of financial position / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：金標「7,526,593」出現在比較欄 ['2024年1月1日至12月31日 2024/1/1To12/31']；本期（2025）欄之正解為 ['6,625,513']

**[customer_colloquial_005]** 京鼎精密科技113Q2手上現金有多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`5,756,299`
- 定位：3413 / 113Q2 / 現金流量表 / 資產負債表帳列之現金及約當現金 Cash and cash equivalents reported in the statement of financial position / 2023年1月1日至6月30日 2023/1/1To6/30
- 診斷：金標「5,756,299」出現在比較欄 ['2023年1月1日至6月30日 2023/1/1To6/30']；本期（2024）欄之正解為 ['7,571,315']

**[customer_colloquial_009]** 景碩科技114Q4手上現金有多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`15,365,653`
- 定位：3189 / 114Q4 / 現金流量表 / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：金標「15,365,653」出現在比較欄 ['2024年1月1日至12月31日 2024/1/1To12/31']；本期（2025）欄之正解為 ['12,281,237']

**[customer_colloquial_016]** 幫我查日月光投資控股113Q2賣了多少錢

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`136,275,352`
- 定位：3711 / 113Q2 / 綜合損益表 / 營業收入合計 Total operating revenue / 2023年4月1日至6月30日 2023/4/1To6/30
- 診斷：金標「136,275,352」出現在比較欄 ['2023年4月1日至6月30日 2023/4/1To6/30']；本期（2024）欄之正解為 ['140,238,063', '273,040,918']

**[customer_colloquial_018]** 日月光投資控股113Q1營業額是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`2,396,888`
- 定位：3711 / 113Q1 / 母子公司間業務關係及重要交易往來情形 / 營業收入 / 金額
- 診斷：金標「2,396,888」出現在比較欄 ['金額']；本期（2024）欄之正解為 （查無）

**[customer_colloquial_024]** 幫我查達興材料113Q3賣了多少錢

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`6,319`
- 定位：5234 / 113Q3 / 營業收入 / 營業收入 / 本期
- 診斷：金標「6,319」出現在比較欄 ['本期']；本期（2024）欄之正解為 （查無）

**[customer_colloquial_025]** 京元電子114Q4獲利是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`5,971,547`
- 定位：2449 / 114Q4 / 現金流量表 / 繼續營業單位稅前淨利（淨損） Profit (loss) from continuing operations before tax / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：金標「5,971,547」出現在比較欄 ['2024年1月1日至12月31日 2024/1/1To12/31']；本期（2025）欄之正解為 ['10,628,756']

**[customer_colloquial_027]** 環球晶圓114Q4獲利是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`( 7,290 )`
- 定位：6488 / 114Q4 / 綜合損益表 / 非控制權益（淨利／損） Profit (loss), attributable to non-controlling interests / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：金標「( 7,290 )」出現在比較欄 ['2024年1月1日至12月31日 2024/1/1To12/31']；本期（2025）欄之正解為 ['( 367 )']

**[customer_colloquial_028]** 幫我看致茂電子114Q3淨利多少

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`1,426,036`
- 定位：2360 / 114Q3 / 綜合損益表 / 母公司業主（淨利／損） Profit (loss), attributable to owners of parent / 2024年7月1日至9月30日 2024/7/1To9/30
- 診斷：金標「1,426,036」出現在比較欄 ['2024年7月1日至9月30日 2024/7/1To9/30']；本期（2025）欄之正解為 ['5,066,329', '9,142,112']

**[customer_colloquial_035]** 華邦電子114Q1賺多少錢？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`( 426,564 )`
- 定位：2344 / 114Q1 / 現金流量表 / 本期稅前淨利（淨損） Profit (loss) before tax / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：金標「( 426,564 )」出現在比較欄 ['2024年1月1日至3月31日 2024/1/1To3/31']；本期（2025）欄之正解為 ['( 1,145,815 )']

**[customer_colloquial_036]** 穩懋半導體113Q2賺多少錢？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`( 96,923 )`
- 定位：3105 / 113Q2 / 綜合損益表 / 母公司業主（淨利／損） Profit (loss), attributable to owners of parent / 2023年4月1日至6月30日 2023/4/1To6/30
- 診斷：金標「( 96,923 )」出現在比較欄 ['2023年4月1日至6月30日 2023/4/1To6/30']；本期（2024）欄之正解為 ['485,291', '892,017']

**[customer_colloquial_037]** 景碩科技113Q2總資產多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`78,067,039`
- 定位：3189 / 113Q2 / 資產負債表 / 資產總計 Total assets / 2023年12月31日 2023/12/31
- 診斷：金標「78,067,039」出現在比較欄 ['2023年12月31日 2023/12/31']；本期（2024）欄之正解為 ['80,178,407']

**[customer_colloquial_039]** 查一下大聯大控股114Q4資產總額

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`405,992,805`
- 定位：3702 / 114Q4 / 資產負債表 / 資產總計 Total assets / 2024年12月31日 2024/12/31
- 診斷：金標「405,992,805」出現在比較欄 ['2024年12月31日 2024/12/31']；本期（2025）欄之正解為 ['410,972,064']

**[customer_colloquial_041]** 創意電子跟力晶積成電子製造在113Q1的數字差多少？先列出兩家的數字。

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`創意電子: 238 ｜ 力晶積成電子製造: ( 196 ) ｜ 較高: 創意電子`
- 定位：3443/6770 / 113Q1 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2023年1月1日至3月31日 2023/1/1To3/31
- 診斷：創意電子 金標「238」取自比較欄，本期（2024）正解 ['17,448']；力晶積成電子製造 金標「( 196 )」取自比較欄，本期（2024）正解 ['( 279 )']；metadata.column_header「2023年1月1日至3月31日 2023/1/1To3/31」非 113Q1（2024）之本期欄

**[customer_colloquial_043]** 113Q1時，致茂電子和力旺電子誰的期初現金及約當現金餘額比較高？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`致茂電子: 5,941,512 ｜ 力旺電子: 3,066,268 ｜ 較高: 致茂電子`
- 定位：2360/3529 / 113Q1 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2023年1月1日至3月31日 2023/1/1To3/31
- 診斷：致茂電子 金標「5,941,512」取自比較欄，本期（2024）正解 ['4,132,261']；力旺電子 金標「3,066,268」取自比較欄，本期（2024）正解 ['2,731,524']；metadata.column_header「2023年1月1日至3月31日 2023/1/1To3/31」非 113Q1（2024）之本期欄

**[customer_colloquial_045]** 幫我比一下家登精密工業和京鼎精密科技，113Q1的期末現金及約當現金餘額各是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`家登精密工業: 2,428,230 ｜ 京鼎精密科技: 7,900,544 ｜ 較高: 京鼎精密科技`
- 定位：3680/3413 / 113Q1 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2023年1月1日至3月31日 2023/1/1To3/31
- 診斷：家登精密工業 金標「2,428,230」取自比較欄，本期（2024）正解 ['2,915,840']；京鼎精密科技 金標「7,900,544」取自比較欄，本期（2024）正解 ['6,736,655']；metadata.column_header「2023年1月1日至3月31日 2023/1/1To3/31」非 113Q1（2024）之本期欄

**[customer_colloquial_047]** 113Q1時，聯華電子和環球晶圓誰的本期淨利（淨損）比較高？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`聯華電子: 16,384,547 ｜ 環球晶圓: 5,000,228 ｜ 較高: 聯華電子`
- 定位：2303/6488 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 2023年1月1日至3月31日 2023/1/1To3/31
- 診斷：聯華電子 金標「16,384,547」取自比較欄，本期（2024）正解 ['10,429,595']；環球晶圓 金標「5,000,228」取自比較欄，本期（2024）正解 ['3,533,081']；metadata.column_header「2023年1月1日至3月31日 2023/1/1To3/31」非 113Q1（2024）之本期欄

**[customer_colloquial_049]** 113Q1時，旺矽科技和日月光投資控股誰的本期淨利（淨損）比較高？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`旺矽科技: 393,799 ｜ 日月光投資控股: 5,681,509 ｜ 較高: 日月光投資控股`
- 定位：6223/3711 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 保留盈餘合計 Total retained earnings
- 診斷：旺矽科技 金標「393,799」取自比較欄，本期（2024）正解 ['392,927']；日月光投資控股 金標「5,681,509」取自比較欄，本期（2024）正解 ['5,955,331']


## D3_corrupt_gold（44 題）

**[customer_colloquial_029]** 幫我看創意電子114Q3淨利多少

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`D1`
- 定位：3443 / 114Q3 / 去年同期權益變動表 / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity
- 診斷：金標「D1」非數值（附註代號或整列傾印）

**[customer_colloquial_081]** 大聯大控股113Q3的10是跟哪個關係人有關？金額大概多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_related_party_question
- 現行金標：`振遠科技股份有限公司；value_2=大聯大電子(香港)有限公司; value_3=3; value_4=應收帳款; value_5=416,120; value_6=註4; value_7=0.10 %`
- 定位：3702 / 113Q3 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_084]** 台灣光罩113Q1的0是跟哪個關係人有關？金額大概多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_related_party_question
- 現行金標：`台灣光罩(股)公司；value_2=美祿科技(股)公司; value_3=1; value_4=背書保證; value_5=128,000; value_6=與一般客戶交易條件相當; value_7=0.57 %`
- 定位：2338 / 113Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_088]** 幫我看日月光投資控股113Q4關係人交易裡，28對象是誰？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_related_party_question
- 現行金標：`FINANCIERE AFG；value_2=ASTEELFLASH PLZEN S.R.O.; value_3=子公司對子公司; value_4=其他資產; value_5=238,422; value_6=註1; value_7=0.00 %`
- 定位：3711 / 113Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_089]** 幫我看大聯大控股113Q1關係人交易裡，2對象是誰？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_related_party_question
- 現行金標：`WPI International (South Asia) Pte. Ltd.；value_2=世平興業股份有限公司; value_3=3; value_4=應收帳款; value_5=229,699; value_6=註5; value_7=0.07 %`
- 定位：3702 / 113Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_090]** 幫我看日月光投資控股113Q3關係人交易裡，19對象是誰？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_related_party_question
- 現行金標：`環旭科技有限公司；value_2=環鴻電子（昆山）有限公司; value_3=子公司對子公司; value_4=其他應付款; value_5=3,039,731; value_6=註1; value_7=0.00 %`
- 定位：3711 / 113Q3 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_029]** 幫我看創意電子114Q3淨利多少（科目：【本期淨利（淨損） Profit (loss)】）（表：【去年同期權益變動表】）（去年同期權益變動表 Last year's Statements of Change in Equity）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_single_metric
- 現行金標：`D1`
- 定位：3443 / 114Q3 / 去年同期權益變動表 / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity
- 診斷：金標「D1」非數值（附註代號或整列傾印）

**[customer_colloquial_081]** 大聯大控股113Q3的10是跟哪個關係人有關？金額大概多少？（與【大聯大電子(香港)有限公司】之間的【應收帳款】交易）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_related_party_question
- 現行金標：`振遠科技股份有限公司；value_2=大聯大電子(香港)有限公司; value_3=3; value_4=應收帳款; value_5=416,120; value_6=註4; value_7=0.10 %`
- 定位：3702 / 113Q3 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_084]** 台灣光罩113Q1的0是跟哪個關係人有關？金額大概多少？（與【美祿科技(股)公司】之間的【背書保證】交易）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_related_party_question
- 現行金標：`台灣光罩(股)公司；value_2=美祿科技(股)公司; value_3=1; value_4=背書保證; value_5=128,000; value_6=與一般客戶交易條件相當; value_7=0.57 %`
- 定位：2338 / 113Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_088]** 幫我看日月光投資控股113Q4關係人交易裡，28對象是誰？（與【ASTEELFLASH PLZEN S.R.O.】之間的【其他資產】交易）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_related_party_question
- 現行金標：`FINANCIERE AFG；value_2=ASTEELFLASH PLZEN S.R.O.; value_3=子公司對子公司; value_4=其他資產; value_5=238,422; value_6=註1; value_7=0.00 %`
- 定位：3711 / 113Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_089]** 幫我看大聯大控股113Q1關係人交易裡，2對象是誰？（與【世平興業股份有限公司】之間的【應收帳款】交易）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_related_party_question
- 現行金標：`WPI International (South Asia) Pte. Ltd.；value_2=世平興業股份有限公司; value_3=3; value_4=應收帳款; value_5=229,699; value_6=註5; value_7=0.07 %`
- 定位：3702 / 113Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[customer_colloquial_090]** 幫我看日月光投資控股113Q3關係人交易裡，19對象是誰？（與【環鴻電子（昆山）有限公司】之間的【其他應付款】交易）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_related_party_question
- 現行金標：`環旭科技有限公司；value_2=環鴻電子（昆山）有限公司; value_3=子公司對子公司; value_4=其他應付款; value_5=3,039,731; value_6=註1; value_7=0.00 %`
- 定位：3711 / 113Q3 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_081]** 根據關係人交易圖譜，【大聯大控股】在【114Q1】的【3】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`World Peace International (South Asia) Pte Ltd.；value_2=WPG South Asia Pte. Ltd.; value_3=3; value_4=其他應收款; value_5=348,056; value_6=註6; value_7=0.08 %`
- 定位：3702 / 114Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_082]** 根據關係人交易圖譜，【穩懋半導體】在【114Q2】的【2】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`江蘇全穩康源農業發展有限公司；value_2=江蘇全穩農牧科技有限公司; value_3=3; value_4=其他應付款-關係人; value_5=110,510; value_6=與一般交易同; value_7=0.18 %`
- 定位：3105 / 114Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_083]** 根據關係人交易圖譜，【家登精密工業】在【113Q1】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`家登精密工業股份有限公司；value_2=上海家登貿易有限公司; value_3=1; value_4=服務費用; value_5=28,658; value_7=2.00 %`
- 定位：3680 / 113Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_086]** 根據關係人交易圖譜，【華邦電子】在【114Q4】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`華邦公司；value_2=WECA公司; value_3=母公司對子公司; value_4=其他應付款; value_5=229,127; value_6=0; value_7=0.00 %`
- 定位：2344 / 114Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_087]** 根據關係人交易圖譜，【智原科技】在【113Q2】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`智原科技(股)公司；value_2=智原科技(上海)有限公司; value_3=1; value_4=合約資產; value_5=8,602; value_6=依合約而定; value_7=0.05 %`
- 定位：3035 / 113Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_088]** 根據關係人交易圖譜，【京鼎精密科技】在【114Q4】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`京鼎精密科技股份有限公司；value_2=SUCCESSPRAISECORPORATION; value_3=(1); value_4=進貨; value_5=7,877,323; value_6=發票日起45天; value_7=38.00 %`
- 定位：3413 / 114Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_089]** 根據關係人交易圖譜，【台灣光罩】在【114Q1】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`台灣光罩(股)公司；value_2=友縳投資(股)公司; value_3=3; value_4=利息收入; value_5=1,997; value_6=約定時間收付款; value_7=0.12 %`
- 定位：2338 / 114Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_090]** 根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：related_party_transaction_graph
- 現行金標：`iPro Vision Inc.；value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %`
- 定位：2338 / 113Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_081]** 根據關係人交易圖譜，【大聯大控股】在【114Q1】的【3】中，與【WPG South Asia Pte. Ltd.】之間的【其他應收款】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`World Peace International (South Asia) Pte Ltd.；value_2=WPG South Asia Pte. Ltd.; value_3=3; value_4=其他應收款; value_5=348,056; value_6=註6; value_7=0.08 %`
- 定位：3702 / 114Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_082]** 根據關係人交易圖譜，【穩懋半導體】在【114Q2】的【2】中，與【江蘇全穩農牧科技有限公司】之間的【其他應付款-關係人】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`江蘇全穩康源農業發展有限公司；value_2=江蘇全穩農牧科技有限公司; value_3=3; value_4=其他應付款-關係人; value_5=110,510; value_6=與一般交易同; value_7=0.18 %`
- 定位：3105 / 114Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_083]** 根據關係人交易圖譜，【家登精密工業】在【113Q1】的【0】中，與【上海家登貿易有限公司】之間的【服務費用】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`家登精密工業股份有限公司；value_2=上海家登貿易有限公司; value_3=1; value_4=服務費用; value_5=28,658; value_7=2.00 %`
- 定位：3680 / 113Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_086]** 根據關係人交易圖譜，【華邦電子】在【114Q4】的【0】中，與【WECA公司】之間的【其他應付款】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`華邦公司；value_2=WECA公司; value_3=母公司對子公司; value_4=其他應付款; value_5=229,127; value_6=0; value_7=0.00 %`
- 定位：2344 / 114Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_087]** 根據關係人交易圖譜，【智原科技】在【113Q2】的【0】中，與【智原科技(上海)有限公司】之間的【合約資產】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`智原科技(股)公司；value_2=智原科技(上海)有限公司; value_3=1; value_4=合約資產; value_5=8,602; value_6=依合約而定; value_7=0.05 %`
- 定位：3035 / 113Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_088]** 根據關係人交易圖譜，【京鼎精密科技】在【114Q4】的【0】中，與【SUCCESSPRAISECORPORATION】之間的【進貨】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`京鼎精密科技股份有限公司；value_2=SUCCESSPRAISECORPORATION; value_3=(1); value_4=進貨; value_5=7,877,323; value_6=發票日起45天; value_7=38.00 %`
- 定位：3413 / 114Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_089]** 根據關係人交易圖譜，【台灣光罩】在【114Q1】的【0】中，與【友縳投資(股)公司】之間的【利息收入】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`台灣光罩(股)公司；value_2=友縳投資(股)公司; value_3=3; value_4=利息收入; value_5=1,997; value_6=約定時間收付款; value_7=0.12 %`
- 定位：2338 / 114Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_test_090]** 根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：related_party_transaction_graph
- 現行金標：`iPro Vision Inc.；value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %`
- 定位：2338 / 113Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_017]** 根據關係人交易圖譜，【大聯大控股】在【114Q1】的【3】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`World Peace International (South Asia) Pte Ltd.；value_2=WPG South Asia Pte. Ltd.; value_3=3; value_4=其他應收款; value_5=348,056; value_6=註6; value_7=0.08 %`
- 定位：3702 / 114Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_018]** 根據關係人交易圖譜，【穩懋半導體】在【114Q2】的【2】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`江蘇全穩康源農業發展有限公司；value_2=江蘇全穩農牧科技有限公司; value_3=3; value_4=其他應付款-關係人; value_5=110,510; value_6=與一般交易同; value_7=0.18 %`
- 定位：3105 / 114Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_019]** 根據關係人交易圖譜，【家登精密工業】在【113Q1】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`家登精密工業股份有限公司；value_2=上海家登貿易有限公司; value_3=1; value_4=服務費用; value_5=28,658; value_7=2.00 %`
- 定位：3680 / 113Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_020]** 根據關係人交易圖譜，【華邦電子】在【114Q4】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`華邦公司；value_2=WECA公司; value_3=母公司對子公司; value_4=其他應付款; value_5=229,127; value_6=0; value_7=0.00 %`
- 定位：2344 / 114Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_021]** 根據關係人交易圖譜，【智原科技】在【113Q2】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`智原科技(股)公司；value_2=智原科技(上海)有限公司; value_3=1; value_4=合約資產; value_5=8,602; value_6=依合約而定; value_7=0.05 %`
- 定位：3035 / 113Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_022]** 根據關係人交易圖譜，【京鼎精密科技】在【114Q4】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`京鼎精密科技股份有限公司；value_2=SUCCESSPRAISECORPORATION; value_3=(1); value_4=進貨; value_5=7,877,323; value_6=發票日起45天; value_7=38.00 %`
- 定位：3413 / 114Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_023]** 根據關係人交易圖譜，【台灣光罩】在【114Q1】的【0】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`台灣光罩(股)公司；value_2=友縳投資(股)公司; value_3=3; value_4=利息收入; value_5=1,997; value_6=約定時間收付款; value_7=0.12 %`
- 定位：2338 / 114Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_024]** 根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset.json`　題型：related_party_transaction_graph
- 現行金標：`iPro Vision Inc.；value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %`
- 定位：2338 / 113Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_017]** 根據關係人交易圖譜，【大聯大控股】在【114Q1】的【3】中，與【WPG South Asia Pte. Ltd.】之間的【其他應收款】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`World Peace International (South Asia) Pte Ltd.；value_2=WPG South Asia Pte. Ltd.; value_3=3; value_4=其他應收款; value_5=348,056; value_6=註6; value_7=0.08 %`
- 定位：3702 / 114Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_018]** 根據關係人交易圖譜，【穩懋半導體】在【114Q2】的【2】中，與【江蘇全穩農牧科技有限公司】之間的【其他應付款-關係人】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`江蘇全穩康源農業發展有限公司；value_2=江蘇全穩農牧科技有限公司; value_3=3; value_4=其他應付款-關係人; value_5=110,510; value_6=與一般交易同; value_7=0.18 %`
- 定位：3105 / 114Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_019]** 根據關係人交易圖譜，【家登精密工業】在【113Q1】的【0】中，與【上海家登貿易有限公司】之間的【服務費用】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`家登精密工業股份有限公司；value_2=上海家登貿易有限公司; value_3=1; value_4=服務費用; value_5=28,658; value_7=2.00 %`
- 定位：3680 / 113Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_020]** 根據關係人交易圖譜，【華邦電子】在【114Q4】的【0】中，與【WECA公司】之間的【其他應付款】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`華邦公司；value_2=WECA公司; value_3=母公司對子公司; value_4=其他應付款; value_5=229,127; value_6=0; value_7=0.00 %`
- 定位：2344 / 114Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_021]** 根據關係人交易圖譜，【智原科技】在【113Q2】的【0】中，與【智原科技(上海)有限公司】之間的【合約資產】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`智原科技(股)公司；value_2=智原科技(上海)有限公司; value_3=1; value_4=合約資產; value_5=8,602; value_6=依合約而定; value_7=0.05 %`
- 定位：3035 / 113Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_022]** 根據關係人交易圖譜，【京鼎精密科技】在【114Q4】的【0】中，與【SUCCESSPRAISECORPORATION】之間的【進貨】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`京鼎精密科技股份有限公司；value_2=SUCCESSPRAISECORPORATION; value_3=(1); value_4=進貨; value_5=7,877,323; value_6=發票日起45天; value_7=38.00 %`
- 定位：3413 / 114Q4 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_023]** 根據關係人交易圖譜，【台灣光罩】在【114Q1】的【0】中，與【友縳投資(股)公司】之間的【利息收入】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`台灣光罩(股)公司；value_2=友縳投資(股)公司; value_3=3; value_4=利息收入; value_5=1,997; value_6=約定時間收付款; value_7=0.12 %`
- 定位：2338 / 114Q1 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分

**[arch_wrong_024]** 根據關係人交易圖譜，【台灣光罩】在【113Q2】的【7】中，與【昱嘉科技(股)公司】之間的【銷貨】交易涉及哪個關係人或類別？金額摘要是多少？

- 資料集：`system_architecture_wrong_questions_dataset_v2.json`　題型：related_party_transaction_graph
- 現行金標：`iPro Vision Inc.；value_2=昱嘉科技(股)公司; value_3=3; value_4=銷貨; value_5=2,414; value_6=約定時間收付款; value_7=0.06 %`
- 定位：2338 / 113Q2 /  /  / 
- 診斷：圖譜題金標為附註代號或整列傾印，無法評分


## D4_same_value_two_period（52 題）

**[customer_colloquial_056]** 幫我看聯華電子113Q2跟114Q2的分類至待出售（非流動）資產（或處分群組）之現金及約當現金差異。

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q2: 430,570 ｜ 114Q2: 430,570 ｜ 趨勢: 持平`
- 定位：2303 / 113Q2/114Q2 / None / 分類至待出售（非流動）資產（或處分群組）之現金及約當現金 (Non-current) assets (or disposal groups) classified as held for sale, net / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_057]** 聯華電子這兩季(113Q4、114Q4)的匯率變動對現金及約當現金之影響各是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q4: 3,715,419 ｜ 114Q4: 3,715,419 ｜ 趨勢: 持平`
- 定位：2303 / 113Q4/114Q4 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_058]** 聯華電子這兩季(113Q1、114Q1)的匯率變動對現金及約當現金之影響各是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q1: 2,411,317 ｜ 114Q1: 2,411,317 ｜ 趨勢: 持平`
- 定位：2303 / 113Q1/114Q1 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_059]** 聯華電子從113Q2到114Q2，匯率變動對現金及約當現金之影響有變多嗎？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q2: 2,753,669 ｜ 114Q2: 2,753,669 ｜ 趨勢: 持平`
- 定位：2303 / 113Q2/114Q2 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_060]** 聯華電子這兩季(113Q3、114Q3)的匯率變動對現金及約當現金之影響各是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q3: 3,826,647 ｜ 114Q3: 3,826,647 ｜ 趨勢: 持平`
- 定位：2303 / 113Q3/114Q3 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2024年1月1日至9月30日 2024/1/1To9/30
- 診斷：欄位標頭「2024年1月1日至9月30日 2024/1/1To9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_061]** 幫我看聯華電子113Q4跟114Q4的期初現金及約當現金餘額差異。

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q4: 132,553,615 ｜ 114Q4: 132,553,615 ｜ 趨勢: 持平`
- 定位：2303 / 113Q4/114Q4 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_062]** 聯華電子從113Q1到114Q1，期初現金及約當現金餘額有變多嗎？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q1: 132,553,615 ｜ 114Q1: 132,553,615 ｜ 趨勢: 持平`
- 定位：2303 / 113Q1/114Q1 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_063]** 幫我看聯華電子113Q2跟114Q2的期初現金及約當現金餘額差異。

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q2: 132,553,615 ｜ 114Q2: 132,553,615 ｜ 趨勢: 持平`
- 定位：2303 / 113Q2/114Q2 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_064]** 聯華電子這兩季(113Q3、114Q3)的期初現金及約當現金餘額各是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q3: 132,553,615 ｜ 114Q3: 132,553,615 ｜ 趨勢: 持平`
- 定位：2303 / 113Q3/114Q3 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2024年1月1日至9月30日 2024/1/1To9/30
- 診斷：欄位標頭「2024年1月1日至9月30日 2024/1/1To9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_065]** 聯華電子從113Q4到114Q4，期末現金及約當現金餘額有變多嗎？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q4: 105,000,226 ｜ 114Q4: 105,000,226 ｜ 趨勢: 持平`
- 定位：2303 / 113Q4/114Q4 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_066]** 聯華電子這兩季(113Q1、114Q1)的期末現金及約當現金餘額各是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q1: 119,431,260 ｜ 114Q1: 119,431,260 ｜ 趨勢: 持平`
- 定位：2303 / 113Q1/114Q1 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_067]** 聯華電子從113Q2到114Q2，期末現金及約當現金餘額有變多嗎？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q2: 121,664,395 ｜ 114Q2: 121,664,395 ｜ 趨勢: 持平`
- 定位：2303 / 113Q2/114Q2 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_068]** 聯華電子從113Q3到114Q3，期末現金及約當現金餘額有變多嗎？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q3: 103,407,426 ｜ 114Q3: 103,407,426 ｜ 趨勢: 持平`
- 定位：2303 / 113Q3/114Q3 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至9月30日 2024/1/1To9/30
- 診斷：欄位標頭「2024年1月1日至9月30日 2024/1/1To9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_069]** 聯華電子從113Q4到114Q4，本期淨利（淨損）有變多嗎？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q4: 47,106,256 ｜ 114Q4: 47,106,256 ｜ 趨勢: 持平`
- 定位：2303 / 113Q4/114Q4 / None / 本期淨利（淨損） Profit (loss) / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_070]** 幫我看聯華電子113Q1跟114Q1的本期淨利（淨損）差異。

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_period_compare
- 現行金標：`113Q1: 10,429,595 ｜ 114Q1: 10,429,595 ｜ 趨勢: 持平`
- 定位：2303 / 113Q1/114Q1 / None / 本期淨利（淨損） Profit (loss) / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_056]** 幫我看聯華電子113Q2跟114Q2的分類至待出售（非流動）資產（或處分群組）之現金及約當現金差異（科目：【分類至待出售（非流動）資產（或處分群組）之現金及約當現金 (Non-current) assets (or disposal groups) classified as held for sale, net】）（2024年1月1日至6月30日 2024/1/1To6/30）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q2: 430,570 ｜ 114Q2: 430,570 ｜ 趨勢: 持平`
- 定位：2303 / 113Q2/114Q2 / None / 分類至待出售（非流動）資產（或處分群組）之現金及約當現金 (Non-current) assets (or disposal groups) classified as held for sale, net / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_057]** 聯華電子這兩季(113Q4、114Q4)的匯率變動對現金及約當現金之影響各是多少？（科目：【匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents】）（2024年1月1日至12月31日 2024/1/1To12/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q4: 3,715,419 ｜ 114Q4: 3,715,419 ｜ 趨勢: 持平`
- 定位：2303 / 113Q4/114Q4 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_058]** 聯華電子這兩季(113Q1、114Q1)的匯率變動對現金及約當現金之影響各是多少？（科目：【匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents】）（2024年1月1日至3月31日 2024/1/1To3/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q1: 2,411,317 ｜ 114Q1: 2,411,317 ｜ 趨勢: 持平`
- 定位：2303 / 113Q1/114Q1 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_059]** 聯華電子從113Q2到114Q2，匯率變動對現金及約當現金之影響有變多嗎？（科目：【匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents】）（2024年1月1日至6月30日 2024/1/1To6/30）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q2: 2,753,669 ｜ 114Q2: 2,753,669 ｜ 趨勢: 持平`
- 定位：2303 / 113Q2/114Q2 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_060]** 聯華電子這兩季(113Q3、114Q3)的匯率變動對現金及約當現金之影響各是多少？（科目：【匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents】）（2024年1月1日至9月30日 2024/1/1To9/30）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q3: 3,826,647 ｜ 114Q3: 3,826,647 ｜ 趨勢: 持平`
- 定位：2303 / 113Q3/114Q3 / None / 匯率變動對現金及約當現金之影響 Effect of exchange rate changes on cash and cash equivalents / 2024年1月1日至9月30日 2024/1/1To9/30
- 診斷：欄位標頭「2024年1月1日至9月30日 2024/1/1To9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_061]** 幫我看聯華電子113Q4跟114Q4的期初現金及約當現金餘額差異（科目：【期初現金及約當現金餘額 Cash and cash equivalents at beginning of period】）（2024年1月1日至12月31日 2024/1/1To12/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q4: 132,553,615 ｜ 114Q4: 132,553,615 ｜ 趨勢: 持平`
- 定位：2303 / 113Q4/114Q4 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_062]** 聯華電子從113Q1到114Q1，期初現金及約當現金餘額有變多嗎？（科目：【期初現金及約當現金餘額 Cash and cash equivalents at beginning of period】）（2024年1月1日至3月31日 2024/1/1To3/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q1: 132,553,615 ｜ 114Q1: 132,553,615 ｜ 趨勢: 持平`
- 定位：2303 / 113Q1/114Q1 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_063]** 幫我看聯華電子113Q2跟114Q2的期初現金及約當現金餘額差異（科目：【期初現金及約當現金餘額 Cash and cash equivalents at beginning of period】）（2024年1月1日至6月30日 2024/1/1To6/30）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q2: 132,553,615 ｜ 114Q2: 132,553,615 ｜ 趨勢: 持平`
- 定位：2303 / 113Q2/114Q2 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_064]** 聯華電子這兩季(113Q3、114Q3)的期初現金及約當現金餘額各是多少？（科目：【期初現金及約當現金餘額 Cash and cash equivalents at beginning of period】）（2024年1月1日至9月30日 2024/1/1To9/30）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q3: 132,553,615 ｜ 114Q3: 132,553,615 ｜ 趨勢: 持平`
- 定位：2303 / 113Q3/114Q3 / None / 期初現金及約當現金餘額 Cash and cash equivalents at beginning of period / 2024年1月1日至9月30日 2024/1/1To9/30
- 診斷：欄位標頭「2024年1月1日至9月30日 2024/1/1To9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_065]** 聯華電子從113Q4到114Q4，期末現金及約當現金餘額有變多嗎？（科目：【期末現金及約當現金餘額 Cash and cash equivalents at end of period】）（2024年1月1日至12月31日 2024/1/1To12/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q4: 105,000,226 ｜ 114Q4: 105,000,226 ｜ 趨勢: 持平`
- 定位：2303 / 113Q4/114Q4 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_066]** 聯華電子這兩季(113Q1、114Q1)的期末現金及約當現金餘額各是多少？（科目：【期末現金及約當現金餘額 Cash and cash equivalents at end of period】）（2024年1月1日至3月31日 2024/1/1To3/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q1: 119,431,260 ｜ 114Q1: 119,431,260 ｜ 趨勢: 持平`
- 定位：2303 / 113Q1/114Q1 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_067]** 聯華電子從113Q2到114Q2，期末現金及約當現金餘額有變多嗎？（科目：【期末現金及約當現金餘額 Cash and cash equivalents at end of period】）（2024年1月1日至6月30日 2024/1/1To6/30）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q2: 121,664,395 ｜ 114Q2: 121,664,395 ｜ 趨勢: 持平`
- 定位：2303 / 113Q2/114Q2 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_068]** 聯華電子從113Q3到114Q3，期末現金及約當現金餘額有變多嗎？（科目：【期末現金及約當現金餘額 Cash and cash equivalents at end of period】）（2024年1月1日至9月30日 2024/1/1To9/30）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q3: 103,407,426 ｜ 114Q3: 103,407,426 ｜ 趨勢: 持平`
- 定位：2303 / 113Q3/114Q3 / None / 期末現金及約當現金餘額 Cash and cash equivalents at end of period / 2024年1月1日至9月30日 2024/1/1To9/30
- 診斷：欄位標頭「2024年1月1日至9月30日 2024/1/1To9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_069]** 聯華電子從113Q4到114Q4，本期淨利（淨損）有變多嗎？（科目：【本期淨利（淨損） Profit (loss)】）（2024年1月1日至12月31日 2024/1/1To12/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q4: 47,106,256 ｜ 114Q4: 47,106,256 ｜ 趨勢: 持平`
- 定位：2303 / 113Q4/114Q4 / None / 本期淨利（淨損） Profit (loss) / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[customer_colloquial_070]** 幫我看聯華電子113Q1跟114Q1的本期淨利（淨損）差異（科目：【本期淨利（淨損） Profit (loss)】）（2024年1月1日至3月31日 2024/1/1To3/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_period_compare
- 現行金標：`113Q1: 10,429,595 ｜ 114Q1: 10,429,595 ｜ 趨勢: 持平`
- 定位：2303 / 113Q1/114Q1 / None / 本期淨利（淨損） Profit (loss) / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_048]** 請比較【聯華電子】在【113Q1】與【114Q1】的【一年或一營業週期內到期長期負債 Long-term liabilities, current portion】（2024年3月31日 2024/3/31）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q1: 14,466,461 ｜ 114Q1: 14,466,461`
- 定位：2303 / 113Q1/114Q1 / None / 一年或一營業週期內到期長期負債 Long-term liabilities, current portion / 2024年3月31日 2024/3/31
- 診斷：欄位標頭「2024年3月31日 2024/3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_049]** 請比較【聯華電子】在【113Q2】與【114Q2】的【一年或一營業週期內到期長期負債 Long-term liabilities, current portion】（2024年6月30日 2024/6/30）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q2: 13,090,901 ｜ 114Q2: 13,090,901`
- 定位：2303 / 113Q2/114Q2 / None / 一年或一營業週期內到期長期負債 Long-term liabilities, current portion / 2024年6月30日 2024/6/30
- 診斷：欄位標頭「2024年6月30日 2024/6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_050]** 請比較【聯華電子】在【113Q3】與【114Q3】的【一年或一營業週期內到期長期負債 Long-term liabilities, current portion】（2024年9月30日 2024/9/30）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q3: 13,786,620 ｜ 114Q3: 13,786,620`
- 定位：2303 / 113Q3/114Q3 / None / 一年或一營業週期內到期長期負債 Long-term liabilities, current portion / 2024年9月30日 2024/9/30
- 診斷：欄位標頭「2024年9月30日 2024/9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_053]** 請比較【聯華電子】在【113Q1】與【114Q1】的【不動產、廠房及設備 Property, plant and equipment】（2024年3月31日 2024/3/31）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q1: 254,135,871 ｜ 114Q1: 254,135,871`
- 定位：2303 / 113Q1/114Q1 / None / 不動產、廠房及設備 Property, plant and equipment / 2024年3月31日 2024/3/31
- 診斷：欄位標頭「2024年3月31日 2024/3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_054]** 請比較【聯華電子】在【113Q2】與【114Q2】的【不動產、廠房及設備 Property, plant and equipment】（2024年6月30日 2024/6/30）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q2: 274,030,951 ｜ 114Q2: 274,030,951`
- 定位：2303 / 113Q2/114Q2 / None / 不動產、廠房及設備 Property, plant and equipment / 2024年6月30日 2024/6/30
- 診斷：欄位標頭「2024年6月30日 2024/6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_055]** 請比較【聯華電子】在【113Q3】與【114Q3】的【不動產、廠房及設備 Property, plant and equipment】（2024年9月30日 2024/9/30）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q3: 276,444,716 ｜ 114Q3: 276,444,716`
- 定位：2303 / 113Q3/114Q3 / None / 不動產、廠房及設備 Property, plant and equipment / 2024年9月30日 2024/9/30
- 診斷：欄位標頭「2024年9月30日 2024/9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_056]** 請比較【聯華電子】在【113Q4】與【114Q4】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年1月1日至12月31日 2024/1/1To12/31）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q4: ( 1,042,322 ) ｜ 114Q4: ( 1,042,322 )`
- 定位：2303 / 113Q4/114Q4 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_057]** 請比較【聯華電子】在【113Q1】與【114Q1】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年1月1日至3月31日 2024/1/1To3/31）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q1: 2,494,401 ｜ 114Q1: 2,494,401`
- 定位：2303 / 113Q1/114Q1 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_058]** 請比較【聯華電子】在【113Q2】與【114Q2】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年1月1日至6月30日 2024/1/1To6/30）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q2: 2,688,302 ｜ 114Q2: 2,688,302`
- 定位：2303 / 113Q2/114Q2 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_059]** 請比較【聯華電子】在【113Q3】與【114Q3】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年1月1日至9月30日 2024/1/1To9/30）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q3: 336,249 ｜ 114Q3: 336,249`
- 定位：2303 / 113Q3/114Q3 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年1月1日至9月30日 2024/1/1To9/30
- 診斷：欄位標頭「2024年1月1日至9月30日 2024/1/1To9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_060]** 請比較【聯華電子】在【113Q2】與【114Q2】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年4月1日至6月30日 2024/4/1To6/30）各是多少？

- 資料集：`system_architecture_test_questions_100.json`　題型：cross_period_compare
- 現行金標：`113Q2: 193,901 ｜ 114Q2: 193,901`
- 定位：2303 / 113Q2/114Q2 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年4月1日至6月30日 2024/4/1To6/30
- 診斷：欄位標頭「2024年4月1日至6月30日 2024/4/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_048]** 請比較【聯華電子】在【113Q1】與【114Q1】的【一年或一營業週期內到期長期負債 Long-term liabilities, current portion】（2024年3月31日 2024/3/31）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q1: 14,466,461 ｜ 114Q1: 14,466,461`
- 定位：2303 / 113Q1/114Q1 / None / 一年或一營業週期內到期長期負債 Long-term liabilities, current portion / 2024年3月31日 2024/3/31
- 診斷：欄位標頭「2024年3月31日 2024/3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_049]** 請比較【聯華電子】在【113Q2】與【114Q2】的【一年或一營業週期內到期長期負債 Long-term liabilities, current portion】（2024年6月30日 2024/6/30）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q2: 13,090,901 ｜ 114Q2: 13,090,901`
- 定位：2303 / 113Q2/114Q2 / None / 一年或一營業週期內到期長期負債 Long-term liabilities, current portion / 2024年6月30日 2024/6/30
- 診斷：欄位標頭「2024年6月30日 2024/6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_050]** 請比較【聯華電子】在【113Q3】與【114Q3】的【一年或一營業週期內到期長期負債 Long-term liabilities, current portion】（2024年9月30日 2024/9/30）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q3: 13,786,620 ｜ 114Q3: 13,786,620`
- 定位：2303 / 113Q3/114Q3 / None / 一年或一營業週期內到期長期負債 Long-term liabilities, current portion / 2024年9月30日 2024/9/30
- 診斷：欄位標頭「2024年9月30日 2024/9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_053]** 請比較【聯華電子】在【113Q1】與【114Q1】的【不動產、廠房及設備 Property, plant and equipment】（2024年3月31日 2024/3/31）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q1: 254,135,871 ｜ 114Q1: 254,135,871`
- 定位：2303 / 113Q1/114Q1 / None / 不動產、廠房及設備 Property, plant and equipment / 2024年3月31日 2024/3/31
- 診斷：欄位標頭「2024年3月31日 2024/3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_054]** 請比較【聯華電子】在【113Q2】與【114Q2】的【不動產、廠房及設備 Property, plant and equipment】（2024年6月30日 2024/6/30）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q2: 274,030,951 ｜ 114Q2: 274,030,951`
- 定位：2303 / 113Q2/114Q2 / None / 不動產、廠房及設備 Property, plant and equipment / 2024年6月30日 2024/6/30
- 診斷：欄位標頭「2024年6月30日 2024/6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_055]** 請比較【聯華電子】在【113Q3】與【114Q3】的【不動產、廠房及設備 Property, plant and equipment】（2024年9月30日 2024/9/30）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q3: 276,444,716 ｜ 114Q3: 276,444,716`
- 定位：2303 / 113Q3/114Q3 / None / 不動產、廠房及設備 Property, plant and equipment / 2024年9月30日 2024/9/30
- 診斷：欄位標頭「2024年9月30日 2024/9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_056]** 請比較【聯華電子】在【113Q4】與【114Q4】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年1月1日至12月31日 2024/1/1To12/31）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q4: ( 1,042,322 ) ｜ 114Q4: ( 1,042,322 )`
- 定位：2303 / 113Q4/114Q4 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年1月1日至12月31日 2024/1/1To12/31
- 診斷：欄位標頭「2024年1月1日至12月31日 2024/1/1To12/31」僅屬 113Q4 之當期欄，卻同時用於 113Q4/114Q4 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_057]** 請比較【聯華電子】在【113Q1】與【114Q1】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年1月1日至3月31日 2024/1/1To3/31）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q1: 2,494,401 ｜ 114Q1: 2,494,401`
- 定位：2303 / 113Q1/114Q1 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年1月1日至3月31日 2024/1/1To3/31
- 診斷：欄位標頭「2024年1月1日至3月31日 2024/1/1To3/31」僅屬 113Q1 之當期欄，卻同時用於 113Q1/114Q1 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_058]** 請比較【聯華電子】在【113Q2】與【114Q2】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年1月1日至6月30日 2024/1/1To6/30）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q2: 2,688,302 ｜ 114Q2: 2,688,302`
- 定位：2303 / 113Q2/114Q2 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：欄位標頭「2024年1月1日至6月30日 2024/1/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_059]** 請比較【聯華電子】在【113Q3】與【114Q3】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年1月1日至9月30日 2024/1/1To9/30）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q3: 336,249 ｜ 114Q3: 336,249`
- 定位：2303 / 113Q3/114Q3 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年1月1日至9月30日 2024/1/1To9/30
- 診斷：欄位標頭「2024年1月1日至9月30日 2024/1/1To9/30」僅屬 113Q3 之當期欄，卻同時用於 113Q3/114Q3 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」

**[arch_test_060]** 請比較【聯華電子】在【113Q2】與【114Q2】的【不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss】（2024年4月1日至6月30日 2024/4/1To6/30）各是多少？

- 資料集：`system_architecture_test_questions_100_v2.json`　題型：cross_period_compare
- 現行金標：`113Q2: 193,901 ｜ 114Q2: 193,901`
- 定位：2303 / 113Q2/114Q2 / None / 不重分類至損益之項目總額 Components of other comprehensive income that will not be reclassified to profit or loss / 2024年4月1日至6月30日 2024/4/1To6/30
- 診斷：欄位標頭「2024年4月1日至6月30日 2024/4/1To6/30」僅屬 113Q2 之當期欄，卻同時用於 113Q2/114Q2 兩期；另一期實為其去年同期比較欄，趨勢結論因此恆為「持平」


## D5_ambiguous_row（7 題）

**[customer_colloquial_013]** 幫我查家登精密工業114Q2賣了多少錢

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`3,418,805`
- 定位：3680 / 114Q2 / 綜合損益表 / 營業收入合計 Total operating revenue / 2025年1月1日至6月30日 2025/1/1To6/30
- 診斷：本期欄 ['2025年1月1日至6月30日 2025/1/1To6/30', '2025年4月1日至6月30日 2025/4/1To6/30'] 對到 2 列、2 個相異值：1,710,009、3,418,805

**[customer_colloquial_015]** 幫我查力晶積成電子製造114Q2賣了多少錢

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`22,394,444`
- 定位：6770 / 114Q2 / 綜合損益表 / 營業收入合計 Total operating revenue / 2025年1月1日至6月30日 2025/1/1To6/30
- 診斷：本期欄 ['2025年1月1日至6月30日 2025/1/1To6/30', '2025年4月1日至6月30日 2025/4/1To6/30'] 對到 2 列、2 個相異值：11,277,968、22,394,444

**[customer_colloquial_016]** 幫我查日月光投資控股113Q2賣了多少錢

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`136,275,352`
- 定位：3711 / 113Q2 / 綜合損益表 / 營業收入合計 Total operating revenue / 2023年4月1日至6月30日 2023/4/1To6/30
- 診斷：本期欄 ['2024年1月1日至6月30日 2024/1/1To6/30', '2024年4月1日至6月30日 2024/4/1To6/30'] 對到 2 列、2 個相異值：140,238,063、273,040,918

**[customer_colloquial_020]** 幫我查穩懋半導體113Q3賣了多少錢

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`4,347,821`
- 定位：3105 / 113Q3 / 綜合損益表 / 營業收入合計 Total operating revenue / 2024年7月1日至9月30日 2024/7/1To9/30
- 診斷：本期欄 ['2024年1月1日至9月30日 2024/1/1To9/30', '2024年7月1日至9月30日 2024/7/1To9/30'] 對到 2 列、2 個相異值：13,751,648、4,347,821

**[customer_colloquial_026]** 華邦電子114Q2獲利是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`( 1,630,984 )`
- 定位：2344 / 114Q2 / 綜合損益表 / 繼續營業單位本期淨利（淨損） Profit (loss) from continuing operations / 2025年4月1日至6月30日 2025/4/1To6/30
- 診斷：本期欄 ['2025年1月1日至6月30日 2025/1/1To6/30', '2025年4月1日至6月30日 2025/4/1To6/30'] 對到 2 列、2 個相異值：( 1,630,984 )、( 2,617,901 )

**[customer_colloquial_028]** 幫我看致茂電子114Q3淨利多少

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`1,426,036`
- 定位：2360 / 114Q3 / 綜合損益表 / 母公司業主（淨利／損） Profit (loss), attributable to owners of parent / 2024年7月1日至9月30日 2024/7/1To9/30
- 診斷：本期欄 ['2025年1月1日至9月30日 2025/1/1To9/30', '2025年7月1日至9月30日 2025/7/1To9/30'] 對到 2 列、2 個相異值：5,066,329、9,142,112

**[customer_colloquial_036]** 穩懋半導體113Q2賺多少錢？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`( 96,923 )`
- 定位：3105 / 113Q2 / 綜合損益表 / 母公司業主（淨利／損） Profit (loss), attributable to owners of parent / 2023年4月1日至6月30日 2023/4/1To6/30
- 診斷：本期欄 ['2024年1月1日至6月30日 2024/1/1To6/30', '2024年4月1日至6月30日 2024/4/1To6/30'] 對到 2 列、2 個相異值：485,291、892,017


## D6_item_name_mismatch（4 題）

**[customer_colloquial_031]** 大聯大控股114Q4賺多少錢？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`5.59`
- 定位：3702 / 114Q4 / 綜合損益表 / 繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations / 2025年1月1日至12月31日 2025/1/1To12/31
- 診斷：科目名「繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations」之中英文分別指向不同科目（語料表頭誤併），金標「5.59」實為每股盈餘而非淨利

**[customer_colloquial_032]** 辛耘企業114Q2賺多少錢？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`5.41`
- 定位：3583 / 114Q2 / 綜合損益表 / 繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：科目名「繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations」之中英文分別指向不同科目（語料表頭誤併），金標「5.41」實為每股盈餘而非淨利

**[customer_colloquial_031]** 大聯大控股114Q4賺多少錢？（科目：【繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations】）（表：【綜合損益表】）（2025年1月1日至12月31日 2025/1/1To12/31）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_single_metric
- 現行金標：`5.59`
- 定位：3702 / 114Q4 / 綜合損益表 / 繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations / 2025年1月1日至12月31日 2025/1/1To12/31
- 診斷：科目名「繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations」之中英文分別指向不同科目（語料表頭誤併），金標「5.59」實為每股盈餘而非淨利

**[customer_colloquial_032]** 辛耘企業114Q2賺多少錢？（科目：【繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations】）（表：【綜合損益表】）（2024年1月1日至6月30日 2024/1/1To6/30）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_single_metric
- 現行金標：`5.41`
- 定位：3583 / 114Q2 / 綜合損益表 / 繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations / 2024年1月1日至6月30日 2024/1/1To6/30
- 診斷：科目名「繼續營業單位淨利（淨損） Diluted earnings (loss) per share from continuing operations」之中英文分別指向不同科目（語料表頭誤併），金標「5.41」實為每股盈餘而非淨利


## D7_prior_period_source（14 題）

**[customer_colloquial_014]** 京元電子114Q3營業額是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_single_metric
- 現行金標：`640,887`
- 定位：2449 / 114Q3 / 營業收入 / 營業收入 / 去年同期累計
- 診斷：金標取自「營業收入」（上一年度報表），非 114Q3（2025）當期；主要報表當期值為 （查無）

**[customer_colloquial_050]** 幫我比一下創意電子和力晶積成電子製造，113Q1的本期淨利（淨損）各是多少？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`創意電子: D1 ｜ 力晶積成電子製造: D1 ｜ 較高: 創意電子`
- 定位：3443/6770 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity」（上一年度報表），非所問期間之當期值

**[customer_colloquial_051]** 113Q1時，創意電子和中華精測科技誰的本期淨利（淨損）比較高？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`創意電子: 934,171 ｜ 中華精測科技: ( 30,789 ) ｜ 較高: 創意電子`
- 定位：3443/6510 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_12
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_12」（上一年度報表），非所問期間之當期值

**[customer_colloquial_052]** 113Q1時，辛耘企業和力晶積成電子製造誰的本期淨利（淨損）比較高？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`辛耘企業: 145,486 ｜ 力晶積成電子製造: 186,779 ｜ 較高: 力晶積成電子製造`
- 定位：3583/6770 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_14
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_14」（上一年度報表），非所問期間之當期值

**[customer_colloquial_053]** 113Q1時，辛耘企業和景碩科技誰的本期淨利（淨損）比較高？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`辛耘企業: 145,486 ｜ 景碩科技: 216,904 ｜ 較高: 景碩科技`
- 定位：3583/3189 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_15
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_15」（上一年度報表），非所問期間之當期值

**[customer_colloquial_054]** 辛耘企業跟景碩科技在113Q1的數字差多少？先列出兩家的數字。

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`辛耘企業: 145,486 ｜ 景碩科技: 8,014 ｜ 較高: 辛耘企業`
- 定位：3583/3189 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_8
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_8」（上一年度報表），非所問期間之當期值

**[customer_colloquial_055]** 113Q1時，辛耘企業和中華精測科技誰的本期淨利（淨損）比較高？

- 資料集：`customer_colloquial_test_questions_100.json`　題型：colloquial_company_compare
- 現行金標：`辛耘企業: 145,486 ｜ 中華精測科技: ( 30,789 ) ｜ 較高: 辛耘企業`
- 定位：3583/6510 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_9
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_9」（上一年度報表），非所問期間之當期值

**[customer_colloquial_014]** 京元電子114Q3營業額是多少？（科目：【營業收入】）（表：【營業收入】）（去年同期累計）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_single_metric
- 現行金標：`640,887`
- 定位：2449 / 114Q3 / 營業收入 / 營業收入 / 去年同期累計
- 診斷：金標取自「營業收入」（上一年度報表），非 114Q3（2025）當期；主要報表當期值為 （查無）

**[customer_colloquial_050]** 幫我比一下創意電子和力晶積成電子製造，113Q1的本期淨利（淨損）各是多少？（科目：【本期淨利（淨損） Profit (loss)】）（去年同期權益變動表 Last year's Statements of Change in Equity）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_company_compare
- 現行金標：`創意電子: D1 ｜ 力晶積成電子製造: D1 ｜ 較高: 創意電子`
- 定位：3443/6770 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity」（上一年度報表），非所問期間之當期值

**[customer_colloquial_051]** 113Q1時，創意電子和中華精測科技誰的本期淨利（淨損）比較高？（科目：【本期淨利（淨損） Profit (loss)】）（去年同期權益變動表 Last year's Statements of Change in Equity_12）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_company_compare
- 現行金標：`創意電子: 934,171 ｜ 中華精測科技: ( 30,789 ) ｜ 較高: 創意電子`
- 定位：3443/6510 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_12
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_12」（上一年度報表），非所問期間之當期值

**[customer_colloquial_052]** 113Q1時，辛耘企業和力晶積成電子製造誰的本期淨利（淨損）比較高？（科目：【本期淨利（淨損） Profit (loss)】）（去年同期權益變動表 Last year's Statements of Change in Equity_14）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_company_compare
- 現行金標：`辛耘企業: 145,486 ｜ 力晶積成電子製造: 186,779 ｜ 較高: 力晶積成電子製造`
- 定位：3583/6770 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_14
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_14」（上一年度報表），非所問期間之當期值

**[customer_colloquial_053]** 113Q1時，辛耘企業和景碩科技誰的本期淨利（淨損）比較高？（科目：【本期淨利（淨損） Profit (loss)】）（去年同期權益變動表 Last year's Statements of Change in Equity_15）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_company_compare
- 現行金標：`辛耘企業: 145,486 ｜ 景碩科技: 216,904 ｜ 較高: 景碩科技`
- 定位：3583/3189 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_15
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_15」（上一年度報表），非所問期間之當期值

**[customer_colloquial_054]** 辛耘企業跟景碩科技在113Q1的數字差多少？先列出兩家的數字（科目：【本期淨利（淨損） Profit (loss)】）（去年同期權益變動表 Last year's Statements of Change in Equity_8）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_company_compare
- 現行金標：`辛耘企業: 145,486 ｜ 景碩科技: 8,014 ｜ 較高: 辛耘企業`
- 定位：3583/3189 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_8
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_8」（上一年度報表），非所問期間之當期值

**[customer_colloquial_055]** 113Q1時，辛耘企業和中華精測科技誰的本期淨利（淨損）比較高？（科目：【本期淨利（淨損） Profit (loss)】）（去年同期權益變動表 Last year's Statements of Change in Equity_9）

- 資料集：`customer_colloquial_test_questions_100_v2.json`　題型：colloquial_company_compare
- 現行金標：`辛耘企業: 145,486 ｜ 中華精測科技: ( 30,789 ) ｜ 較高: 辛耘企業`
- 定位：3583/6510 / 113Q1 / None / 本期淨利（淨損） Profit (loss) / 去年同期權益變動表 Last year's Statements of Change in Equity_9
- 診斷：金標取自「去年同期權益變動表 Last year's Statements of Change in Equity_9」（上一年度報表），非所問期間之當期值
