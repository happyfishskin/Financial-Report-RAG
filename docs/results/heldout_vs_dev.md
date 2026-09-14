# Held-out 孿生集 vs 開發集（dev）對照

預註冊凍結時間（UTC）：2026-07-25T14:33:30+00:00

| 資料集 | n | dev EM | held-out EM | Δ | Wilson 95% | 預測 | 落在預測區間 |
|---|---:|---:|---:|---:|---|---:|---|
| 架構測試 100 題 | 100 | 97.0% | **100.0%** | +3.0 pp | 96.3–100.0% | 88.0% | ✗ |
| 口語化 100 題（v2 鑑別版） | 100 | 91.0% | **92.0%** | +1.0 pp | 85.0–95.9% | 80.0% | ✗ |
| 純口語自然 100 題 | 100 | 100.0% | **100.0%** | +0.0 pp | 96.3–100.0% | 92.0% | ✗ |
| 圖譜能力題 30 題（固定路由） | 30 | 100.0% | **100.0%** | +0.0 pp | 88.6–100.0% | 90.0% | ✗ |
| 圖譜自然路由題 30 題 | 30 | 100.0% | **100.0%** | +0.0 pp | 88.6–100.0% | 83.0% | ✗ |

**平均落差**：-0.8 pp　**判定**：平均落差 -0.8 pp < 5 pp → 既有修復具跨實例泛化能力

## 逐題型分層（held-out）

### 架構測試 100 題

| question_type | dev | held-out |
|---|---:|---:|
| cross_company_compare | 15/15 | 15/15 |
| cross_period_compare | 12/15 | 15/15 |
| direct_numeric_lookup | 30/30 | 30/30 |
| investment_graph | 10/10 | 10/10 |
| mainland_investment_graph | 2/2 | 2/2 |
| related_party_transaction_graph | 8/8 | 8/8 |
| risk_event_graph | 5/5 | 5/5 |
| supply_chain_graph | 5/5 | 5/5 |
| vector_table_retrieval | 10/10 | 10/10 |

### 口語化 100 題（v2 鑑別版）

| question_type | dev | held-out |
|---|---:|---:|
| colloquial_company_compare | 13/15 | 11/15 |
| colloquial_investment_question | 10/10 | 10/10 |
| colloquial_period_compare | 10/15 | 11/15 |
| colloquial_related_party_question | 10/10 | 10/10 |
| colloquial_risk_question | 5/5 | 5/5 |
| colloquial_single_metric | 38/40 | 40/40 |
| colloquial_supply_chain_question | 5/5 | 5/5 |

### 純口語自然 100 題

| question_type | dev | held-out |
|---|---:|---:|
| colloquial_natural | 100/100 | 100/100 |

### 圖譜能力題 30 題（固定路由）

| question_type | dev | held-out |
|---|---:|---:|
| investment_graph | 10/10 | 10/10 |
| mainland_investment_graph | 2/2 | 2/2 |
| related_party_transaction_graph | 8/8 | 8/8 |
| risk_event_graph | 5/5 | 5/5 |
| supply_chain_graph | 5/5 | 5/5 |

### 圖譜自然路由題 30 題

| question_type | dev | held-out |
|---|---:|---:|
| investment_graph | 10/10 | 10/10 |
| mainland_investment_graph | 2/2 | 2/2 |
| related_party_transaction_graph | 8/8 | 8/8 |
| risk_event_graph | 5/5 | 5/5 |
| supply_chain_graph | 5/5 | 5/5 |
