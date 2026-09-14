# 候選歧義分層評測（第二份 held-out）

金標語意 **A：全部列出才算對**（集合相等、順序無關）。評分規則於量測前隨
`heldout2_prereg_manifest.json` 一併凍結；受測系統未修改。

| 子分層 | 題數 | 集合 EM | 集合 EM(凍結原規則) | 字串 EM | 覆蓋率 | 平均候選數 |
|---|---:|---:|---:|---:|---:|---:|
| investment_ambiguous | 30 | 0.0% | 0.0% | 0.0% | 27.1% | 5.77 |
| supply_chain_ambiguous | 30 | 100.0% | 100.0% | 13.3% | 100.0% | 2.3 |
| **合計** | 60 | **50.0%** | 50.0% | 6.7% | 63.5% | 4.03 |

## 逐題

| id | 子分層 | 候選數 | 集合EM | 覆蓋率 | 系統答案 |
|---|---|---:|:--:|---:|---|
| ho2_ambig_001 | investment_ambiguous | 11 | ✗ | 9% | 環球晶資本 |
| ho2_ambig_002 | investment_ambiguous | 4 | ✗ | 25% | 竹荷投資股份有限公司 |
| ho2_ambig_003 | investment_ambiguous | 14 | ✗ | 7% | Amobile Intelligent Corp. Limited |
| ho2_ambig_004 | investment_ambiguous | 2 | ✗ | 50% | 聯發科香港投資有限公司 |
| ho2_ambig_005 | investment_ambiguous | 3 | ✗ | 33% | 鑫鵬瑜有限公司 |
| ho2_ambig_006 | investment_ambiguous | 4 | ✗ | 25% | 測冠投資股份有限公司 |
| ho2_ambig_007 | investment_ambiguous | 2 | ✗ | 50% | SPIL (Cayman) Holding Limited |
| ho2_ambig_008 | investment_ambiguous | 5 | ✗ | 20% | 漢磊科技股份有限公司 |
| ho2_ambig_009 | investment_ambiguous | 6 | ✗ | 17% | 新寶紘公司 |
| ho2_ambig_010 | investment_ambiguous | 3 | ✗ | 33% | iPro Vision Inc. |
| ho2_ambig_011 | investment_ambiguous | 4 | ✗ | 25% | 測冠投資股份有限公司 |
| ho2_ambig_012 | investment_ambiguous | 2 | ✗ | 50% | 舶美股份有限公司 |
| ho2_ambig_013 | investment_ambiguous | 5 | ✗ | 20% | 昱鐳公司 |
| ho2_ambig_014 | investment_ambiguous | 5 | ✗ | 20% | Quantel Global Company Limited |
| ho2_ambig_015 | investment_ambiguous | 11 | ✗ | 9% | 環球晶資本 |
| ho2_ambig_016 | investment_ambiguous | 5 | ✗ | 20% | 矽實科技(股)公司 |
| ho2_ambig_017 | investment_ambiguous | 13 | ✗ | 8% | 牧德科技公司 |
| ho2_ambig_018 | investment_ambiguous | 3 | ✗ | 33% | FaradayTek Solutions India Private Limited |
| ho2_ambig_019 | investment_ambiguous | 5 | ✗ | 20% | 寰美電子股份有限公司 |
| ho2_ambig_020 | investment_ambiguous | 2 | ✗ | 50% | Chainwin Biotech and Agrotech (Cayman Islands) Co., Ltd. |
| ho2_ambig_021 | investment_ambiguous | 3 | ✗ | 33% | Hsu Chia (Samoa) Investment Ltd. |
| ho2_ambig_022 | investment_ambiguous | 9 | ✗ | 11% | UNIVERSAL SCIENTIFIC INDUSTRIAL VIETNAM COMPANY LIMITED |
| ho2_ambig_023 | investment_ambiguous | 25 | ✗ | 4% | 致禾順開發股份有限公司 |
| ho2_ambig_024 | investment_ambiguous | 2 | ✗ | 50% | Amiti IV Quantum L.P. |
| ho2_ambig_025 | investment_ambiguous | 4 | ✗ | 25% | MediaTek Bangalore Private Limited |
| ho2_ambig_026 | investment_ambiguous | 2 | ✗ | 50% | Powertech Technology Akita Inc. |
| ho2_ambig_027 | investment_ambiguous | 5 | ✗ | 20% | 日月光整合服務公司 |
| ho2_ambig_028 | investment_ambiguous | 3 | ✗ | 33% | 竹荷投資股份有限公司 |
| ho2_ambig_029 | investment_ambiguous | 9 | ✗ | 11% | 光環科技(股)公司 |
| ho2_ambig_030 | investment_ambiguous | 2 | ✗ | 50% | WPG Americas Inc. |
| ho2_ambig_031 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_032 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 中游；化學品 |
| ho2_ambig_033 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_034 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_035 | supply_chain_ambiguous | 3 | ✓ | 100% | 下游；基板 ｜ 下游；IC封裝測試 ｜ 下游；IC模組 |
| ho2_ambig_036 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_037 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_038 | supply_chain_ambiguous | 2 | ✓ | 100% | 上游；IC設計 ｜ 中游；IC/晶圓製造 |
| ho2_ambig_039 | supply_chain_ambiguous | 2 | ✓ | 100% | 下游；IC封裝測試 ｜ 下游；IC模組 |
| ho2_ambig_040 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_041 | supply_chain_ambiguous | 3 | ✓ | 100% | 上游；IC設計 ｜ 中游；IC/晶圓製造 ｜ 下游；IC封裝測試 |
| ho2_ambig_042 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_043 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_044 | supply_chain_ambiguous | 3 | ✓ | 100% | 下游；生產製程及檢測設備 ｜ 下游；基板 ｜ 下游；導線架 |
| ho2_ambig_045 | supply_chain_ambiguous | 5 | ✓ | 100% | 下游；基板 ｜ 下游；導線架 ｜ 下游；IC封裝測試 ｜ 下游；IC模組 ｜ 下游；IC通路 |
| ho2_ambig_046 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_047 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_048 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_049 | supply_chain_ambiguous | 2 | ✓ | 100% | 下游；IC模組 ｜ 下游；IC通路 |
| ho2_ambig_050 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_051 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_052 | supply_chain_ambiguous | 2 | ✓ | 100% | 上游；IC設計 ｜ 下游；IC通路 |
| ho2_ambig_053 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_054 | supply_chain_ambiguous | 4 | ✓ | 100% | 上游；IP設計/IC設計代工服務 ｜ 上游；IC設計 ｜ 下游；IC模組 ｜ 下游；IC通路 |
| ho2_ambig_055 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；IC封裝測試 |
| ho2_ambig_056 | supply_chain_ambiguous | 3 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；基板 ｜ 下游；IC封裝測試 |
| ho2_ambig_057 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_058 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_059 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
| ho2_ambig_060 | supply_chain_ambiguous | 2 | ✓ | 100% | 中游；生產製程及檢測設備 ｜ 下游；生產製程及檢測設備 |
