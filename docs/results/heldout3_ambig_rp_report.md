# 候選歧義分層評測（第二份 held-out）

金標語意 **A：全部列出才算對**（集合相等、順序無關）。評分規則於量測前隨
`heldout2_prereg_manifest.json` 一併凍結；受測系統未修改。

| 子分層 | 題數 | 集合 EM | 集合 EM(凍結原規則) | 字串 EM | 覆蓋率 | 平均候選數 |
|---|---:|---:|---:|---:|---:|---:|
| rp_account_ambiguous | 20 | 100.0% | 100.0% | 45.0% | 100.0% | 2.3 |
| rp_counterparty_ambiguous | 20 | 100.0% | 100.0% | 20.0% | 100.0% | 4.3 |
| **合計** | 40 | **100.0%** | 100.0% | 32.5% | 100.0% | 3.3 |

## 逐題

| id | 子分層 | 候選數 | 集合EM | 覆蓋率 | 系統答案 |
|---|---|---:|:--:|---:|---|
| ho3_rp_001 | rp_counterparty_ambiguous | 5 | ✓ | 100% | 芯唐香港公司 ｜ NTSG公司 ｜ NTCJ公司 ｜ NTIL公司 ｜ NTCA公司 |
| ho3_rp_002 | rp_counterparty_ambiguous | 6 | ✓ | 100% | 華邦香港公司 ｜ WECA公司 ｜ WECJ公司 ｜ WTL公司 ｜ 華邦蘇州公司 ｜ 新唐科技公司 |
| ho3_rp_003 | rp_counterparty_ambiguous | 2 | ✓ | 100% | UMC GROUP (USA) ｜ 聯暻半導體(山東)有限公司(註六) |
| ho3_rp_004 | rp_counterparty_ambiguous | 4 | ✓ | 100% | UMC GROUP (USA) ｜ 聯芯集成電路製造(廈門)有限公司(註五) ｜ 聯芯集成電路製造(廈門)有限公司 ｜ 聯暻半導體(山東)有限公司(註六) |
| ho3_rp_005 | rp_counterparty_ambiguous | 2 | ✓ | 100% | 聯發芯軟件設計(成都)有限公司 ｜ 聯發科軟件(武漢)有限公司 |
| ho3_rp_006 | rp_counterparty_ambiguous | 2 | ✓ | 100% | 大聯大商貿有限公司 ｜ Yosun Hong Kong Corp. Ltd. |
| ho3_rp_007 | rp_counterparty_ambiguous | 2 | ✓ | 100% | Chainwin Biotech and Agrotech (Cayman Islands) Co., Ltd. ｜ 江蘇全穩康源農業發展有限公司 |
| ho3_rp_008 | rp_counterparty_ambiguous | 9 | ✓ | 100% | 世平興業股份有限公司 ｜ WPI Technology Pte. Ltd. ｜ World Peace International (India) Pvt.,  |
| ho3_rp_009 | rp_counterparty_ambiguous | 5 | ✓ | 100% | 芯唐香港公司 ｜ NTCA公司 ｜ NTSG公司 ｜ NTCJ公司 ｜ NTIL公司 |
| ho3_rp_010 | rp_counterparty_ambiguous | 6 | ✓ | 100% | 長洛國際(股)公司 ｜ 琉明光電(常州)有限公司 ｜ MPI AMERICA INC. ｜ 旺矽科技(蘇州)有限公司 ｜ MEGTAS CO.,LTD. ｜ C |
| ho3_rp_011 | rp_counterparty_ambiguous | 3 | ✓ | 100% | 環旭電子公司 ｜ Real Tech Holdings Limited ｜ 環電公司 |
| ho3_rp_012 | rp_counterparty_ambiguous | 2 | ✓ | 100% | 美祿科技(股)公司 ｜ 四川美闊電子科技有限公司 |
| ho3_rp_013 | rp_counterparty_ambiguous | 4 | ✓ | 100% | 世平興業股份有限公司 ｜ 世平國際(香港)有限公司 ｜ 鑫鵬瑜有限公司 ｜ 大聯大電子(香港)有限公司 |
| ho3_rp_014 | rp_counterparty_ambiguous | 3 | ✓ | 100% | 世平興業股份有限公司 ｜ 世平國際(香港)有限公司 ｜ 鑫鵬瑜有限公司 |
| ho3_rp_015 | rp_counterparty_ambiguous | 10 | ✓ | 100% | 瑞晟微電子(蘇州)有限公司 ｜ 瑞昱半導體(深圳)有限公司 ｜ Cortina Access, Inc. ｜ 科締納網絡系統(上海)有限公司 ｜ 科締納科技股份 |
| ho3_rp_016 | rp_counterparty_ambiguous | 7 | ✓ | 100% | 曜成科技股份有限公司 ｜ 群佳科技製造股份有限公司 ｜ Phison Technology Inc. ｜ Nextorage Corporation ｜ Phi |
| ho3_rp_017 | rp_counterparty_ambiguous | 2 | ✓ | 100% | 品佳股份有限公司 ｜ 鑫鵬瑜有限公司 |
| ho3_rp_018 | rp_counterparty_ambiguous | 4 | ✓ | 100% | 承鼎精密股份有限公司 ｜ SUCCESS PRAISE CORPORATION ｜ 富士邁半導體精密工業(上海)有限公司 ｜ 富曜半導體(昆山)有限公司 |
| ho3_rp_019 | rp_counterparty_ambiguous | 2 | ✓ | 100% | PUFsecurity ｜ 熵積公司 |
| ho3_rp_020 | rp_counterparty_ambiguous | 6 | ✓ | 100% | 大聯大商貿(深圳)有限公司 ｜ 大聯大商貿有限公司 ｜ Yosun Hong Kong Corp. Ltd. ｜ 富威科技股份有限公司 ｜ 建智股份有限公司 ｜ |
| ho3_rp_021 | rp_account_ambiguous | 3 | ✓ | 100% | 營業收入 ｜ 應收帳款 ｜ 其他應收款 |
| ho3_rp_022 | rp_account_ambiguous | 3 | ✓ | 100% | 銷貨 ｜ 應收帳款 ｜ 其他應收款 |
| ho3_rp_023 | rp_account_ambiguous | 2 | ✓ | 100% | 進貨 ｜ 銷貨 |
| ho3_rp_024 | rp_account_ambiguous | 2 | ✓ | 100% | 應付帳款 ｜ 營業成本 |
| ho3_rp_025 | rp_account_ambiguous | 2 | ✓ | 100% | 營業費用 ｜ 其他應付款－關係人 |
| ho3_rp_026 | rp_account_ambiguous | 2 | ✓ | 100% | 研究設計費 ｜ 其他應付款 |
| ho3_rp_027 | rp_account_ambiguous | 2 | ✓ | 100% | 其他應付款 ｜ 營業費用 |
| ho3_rp_028 | rp_account_ambiguous | 2 | ✓ | 100% | 其他應收款(資金貸與) ｜ 利息收入 |
| ho3_rp_029 | rp_account_ambiguous | 2 | ✓ | 100% | 其他應收款 ｜ 其他資產 |
| ho3_rp_030 | rp_account_ambiguous | 2 | ✓ | 100% | 進貨 ｜ 銷貨 |
| ho3_rp_031 | rp_account_ambiguous | 3 | ✓ | 100% | 銷貨 ｜ 應收帳款 ｜ 其他應收款 |
| ho3_rp_032 | rp_account_ambiguous | 2 | ✓ | 100% | 銷貨 ｜ 其他應收款 |
| ho3_rp_033 | rp_account_ambiguous | 2 | ✓ | 100% | 銷貨 ｜ 應收帳款 |
| ho3_rp_034 | rp_account_ambiguous | 3 | ✓ | 100% | 銷貨 ｜ 應收帳款 ｜ 其他應收款 |
| ho3_rp_035 | rp_account_ambiguous | 2 | ✓ | 100% | 銷貨 ｜ 應收帳款 |
| ho3_rp_036 | rp_account_ambiguous | 2 | ✓ | 100% | 佣金支出 ｜ 應付費用 |
| ho3_rp_037 | rp_account_ambiguous | 4 | ✓ | 100% | 營業收入 ｜ 研究設計費 ｜ 合約資產 ｜ 其他應付款 |
| ho3_rp_038 | rp_account_ambiguous | 2 | ✓ | 100% | 進貨 ｜ 銷貨 |
| ho3_rp_039 | rp_account_ambiguous | 2 | ✓ | 100% | 營業費用 ｜ 應付費用及其他流動負債 |
| ho3_rp_040 | rp_account_ambiguous | 2 | ✓ | 100% | 其他應付款 ｜ 利息費用 |
