# 候選歧義分層評測（第二份 held-out）

金標語意 **A：全部列出才算對**（集合相等、順序無關）。評分規則於量測前隨
`heldout2_prereg_manifest.json` 一併凍結；受測系統未修改。

| 子分層 | 題數 | 集合 EM | 集合 EM(凍結原規則) | 字串 EM | 覆蓋率 | 平均候選數 |
|---|---:|---:|---:|---:|---:|---:|
| investment_ambiguous | 30 | 100.0% | 100.0% | 10.0% | 100.0% | 5.77 |
| supply_chain_ambiguous | 30 | 100.0% | 100.0% | 13.3% | 100.0% | 2.3 |
| **合計** | 60 | **100.0%** | 100.0% | 11.7% | 100.0% | 4.03 |

## 逐題

| id | 子分層 | 候選數 | 集合EM | 覆蓋率 | 系統答案 |
|---|---|---:|:--:|---:|---|
| ho2_ambig_001 | investment_ambiguous | 11 | ✓ | 100% | GSI ｜ GWJ ｜ GWS ｜ GW GmbH ｜ GWBV ｜ 弘望投資股份有限公司 ｜ 旭愛能源 ｜ 旭信電力 ｜ 寰球鑫 ｜ 兆遠科技 ｜ 環球晶資本 |
| ho2_ambig_002 | investment_ambiguous | 4 | ✓ | 100% | PEGAVISION JAPAN INC. ｜ 美韻投資股份有限公司 ｜ PEGAVISION VIETNAM COMPANY LIMITED ｜ 竹荷投資股份 |
| ho2_ambig_003 | investment_ambiguous | 14 | ✓ | 100% | 聯發科中國有限公司 ｜ ZENA TECHNOLOGY INTERNATIONAL, INC. ｜ Smarthead Limited ｜ Sigmastar  |
| ho2_ambig_004 | investment_ambiguous | 2 | ✓ | 100% | MaiSys Design Technology SG Pte. Ltd. ｜ 聯發科香港投資有限公司 |
| ho2_ambig_005 | investment_ambiguous | 3 | ✓ | 100% | 捷元股份有限公司 ｜ 鑫聯大(香港)有限公司 ｜ 鑫鵬瑜有限公司 |
| ho2_ambig_006 | investment_ambiguous | 4 | ✓ | 100% | Chunghwa Precision Test Tech. International, Ltd. ｜ Chunghwa Precision Test Tech |
| ho2_ambig_007 | investment_ambiguous | 2 | ✓ | 100% | Siliconware USA, Inc. ｜ SPIL (Cayman) Holding Limited |
| ho2_ambig_008 | investment_ambiguous | 5 | ✓ | 100% | VIS Associates Inc. ｜ Vanguard International Semiconductor Singapore Pte. Ltd. ｜ |
| ho2_ambig_009 | investment_ambiguous | 6 | ✓ | 100% | AEMC USA ｜ 新應材日本 ｜ 思微公司 ｜ 歐利得公司 ｜ 昱鐳公司 ｜ 新寶紘公司 |
| ho2_ambig_010 | investment_ambiguous | 3 | ✓ | 100% | 英諾華科技(股)公司 ｜ Innova Vision (B.V.I) Inc. ｜ iPro Vision Inc. |
| ho2_ambig_011 | investment_ambiguous | 4 | ✓ | 100% | Chunghwa Precision Test Tech. International, Ltd. ｜ Chunghwa Precision Test Tech |
| ho2_ambig_012 | investment_ambiguous | 2 | ✓ | 100% | Beautytech Platform (Singapore) Pte. Ltd. ｜ 舶美股份有限公司 |
| ho2_ambig_013 | investment_ambiguous | 5 | ✓ | 100% | AEMC USA ｜ 新應材日本 ｜ 思微公司 ｜ 歐利得公司 ｜ 昱鐳公司 |
| ho2_ambig_014 | investment_ambiguous | 5 | ✓ | 100% | Quantel Technologies India Private Ltd. ｜ Quantel Global Vietnam Co.,Ltd. ｜ Quan |
| ho2_ambig_015 | investment_ambiguous | 11 | ✓ | 100% | GSI ｜ GWJ ｜ GWS ｜ GW GmbH ｜ GWBV ｜ 弘望投資股份有限公司 ｜ 旭愛能源 ｜ 旭信電力 ｜ 寰球鑫 ｜ 兆遠科技 ｜ 環球晶資本 |
| ho2_ambig_016 | investment_ambiguous | 5 | ✓ | 100% | 常憶科技(股)公司 ｜ 聯發創新基地(股)公司 ｜ 聚星電子(股)公司 ｜ Intelligo Technology Inc. ｜ 矽實科技(股)公司 |
| ho2_ambig_017 | investment_ambiguous | 13 | ✓ | 100% | A.S.E. Holding Limited ｜ J ＆ R Holding Limited ｜ ASE Marketing ＆ Service Japan C |
| ho2_ambig_018 | investment_ambiguous | 3 | ✓ | 100% | 昇邁科技股份有限公司 ｜ 寅通科技股份有限公司 ｜ FaradayTek Solutions India Private Limited |
| ho2_ambig_019 | investment_ambiguous | 5 | ✓ | 100% | 金匯科技股份有限公司 ｜ 愛思分析儀器股份有限公司 ｜ 恆陽綠能股份有限公司 ｜ 垚鋐系統科技股份有限公司 ｜ 寰美電子股份有限公司 |
| ho2_ambig_020 | investment_ambiguous | 2 | ✓ | 100% | Rainbow Star Group Limited ｜ Chainwin Biotech and Agrotech (Cayman Islands) Co., |
| ho2_ambig_021 | investment_ambiguous | 3 | ✓ | 100% | Hsu Kang (Samoa) Investment Ltd. ｜ Hsu Fa (Samoa) Investment Ltd. ｜ Hsu Chia (Sa |
| ho2_ambig_022 | investment_ambiguous | 9 | ✓ | 100% | 環旭科技公司 ｜ M-Universe Investments Pte. Ltd. ｜ 環鴻科技公司 ｜ USI Japan Co., Ltd. ｜ Unive |
| ho2_ambig_023 | investment_ambiguous | 25 | ✓ | 100% | Neworld Electronics Limited ｜ 威光自動化科技股份有限公司 ｜ Chroma ATE Inc. ｜ Chroma Systems S |
| ho2_ambig_024 | investment_ambiguous | 2 | ✓ | 100% | 聯發利寶(香港)有限公司 ｜ Amiti IV Quantum L.P. |
| ho2_ambig_025 | investment_ambiguous | 4 | ✓ | 100% | 鈺太科技(股)公司 ｜ 達發科技(股)公司 ｜ 翔發投資(股)公司 ｜ MediaTek Bangalore Private Limited |
| ho2_ambig_026 | investment_ambiguous | 2 | ✓ | 100% | Tera Probe, Inc. ｜ Powertech Technology Akita Inc. |
| ho2_ambig_027 | investment_ambiguous | 5 | ✓ | 100% | 日 月 光 ｜ 矽 品 ｜ 環電公司 ｜ 日月光社會企業公司 ｜ 日月光整合服務公司 |
| ho2_ambig_028 | investment_ambiguous | 3 | ✓ | 100% | 晶碩光學股份有限公司 ｜ 復揚科技股份有限公司 ｜ 竹荷投資股份有限公司 |
| ho2_ambig_029 | investment_ambiguous | 9 | ✓ | 100% | SunnyLake Park International Holdings, Inc. ｜ 友縳投資(股)公司 ｜ 昱厚生技(股)公司 ｜ 美祿科技(股)公司  |
| ho2_ambig_030 | investment_ambiguous | 2 | ✓ | 100% | WPG C＆C Limited ｜ WPG Americas Inc. |
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
