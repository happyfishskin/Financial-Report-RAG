# ── 測試問題庫 ────────────────────────────────────────────────────────────────
#
# result_type:
#   "graph"  → Cypher RETURN 節點 + 關係，前端用 vis.js 渲染
#   "table"  → Cypher RETURN 純屬性，前端用 HTML 表格渲染
#
QUESTIONS = {
    # ── Investment 圖 ──────────────────────────────────────────────────────────
    "Q1": {
        "title": "台積電投資哪些海外子公司？持股比例各是多少？",
        "category": "Investment", "difficulty": "★★", "result_type": "table",
        "cypher": """
            MATCH (c:Company {stock_code: '2330'})-[r:INVESTS_IN]->(sub:Company)
                  -[:LOCATED_IN]->(loc:Location)
            WHERE loc.name <> '台灣'
            RETURN sub.name AS 子公司, loc.name AS 所在地區,
                   r.ownership_percent AS 持股比例,
                   r.book_value AS 帳面價值,
                   r.investment_income_loss AS 本期損益
            ORDER BY toFloat(r.ownership_percent) DESC
        """,
    },
    "Q2": {
        "title": "哪些被投資公司本期投資損益為負（虧損）？",
        "category": "Investment", "difficulty": "★★", "result_type": "table",
        "cypher": """
            MATCH (c:Company)-[r:INVESTS_IN]->(sub:Company)
            WHERE r.investment_income_loss IS NOT NULL
              AND toFloat(r.investment_income_loss) < 0
            RETURN c.name AS 母公司, sub.name AS 被投資公司,
                   r.investment_income_loss AS 本期損益,
                   r.ownership_percent AS 持股比例
            ORDER BY toFloat(r.investment_income_loss) ASC
        """,
    },
    "Q3": {
        "title": "台積電的被投資公司網路圖（含地區）",
        "category": "Investment", "difficulty": "★★★", "result_type": "graph",
        "cypher": """
            MATCH (c:Company {stock_code: '2330'})-[r:INVESTS_IN]->(sub:Company)
            OPTIONAL MATCH (sub)-[r2:LOCATED_IN]->(loc:Location)
            RETURN c, r, sub, r2, loc
        """,
    },
    "Q4": {
        "title": "在美國從事晶圓製造業務的被投資公司有哪些？",
        "category": "Investment", "difficulty": "★★★", "result_type": "table",
        "cypher": """
            MATCH (parent:Company)-[:INVESTS_IN]->(sub:Company)
                  -[:LOCATED_IN]->(loc:Location {name: '美國'})
            MATCH (sub)-[:HAS_BUSINESS]->(biz:Business {name: '晶圓製造'})
            RETURN parent.name AS 母公司, sub.name AS 子公司,
                   loc.name AS 所在地區, biz.name AS 業務類型
        """,
    },

    # ── RelatedParty 圖 ────────────────────────────────────────────────────────
    "Q5": {
        "title": "台積電 114Q2 有哪些主要管理階層關係人？",
        "category": "RelatedParty", "difficulty": "★", "result_type": "table",
        "cypher": """
            MATCH (c:Company {stock_code: '2330'})-[r:HAS_RELATED_PARTY]->(rp:RelatedParty)
            WHERE r.relation_category = '主要管理階層'
            RETURN rp.name AS 關係人, r.relationship_desc AS 關係描述,
                   r.report_period AS 申報期間
        """,
    },
    "Q6": {
        "title": "哪些關係人同時出現在多家公司的申報表中？",
        "category": "RelatedParty", "difficulty": "★★★", "result_type": "table",
        "cypher": """
            MATCH (c:Company)-[r:HAS_RELATED_PARTY]->(rp:RelatedParty)
            WITH rp, collect(DISTINCT c.name) AS companies, count(DISTINCT c) AS cnt
            WHERE cnt > 1
            RETURN rp.name AS 關係人, companies AS 出現公司, cnt AS 公司數
            ORDER BY cnt DESC
        """,
    },
    "Q7": {
        "title": "各關係類型涵蓋幾個關係人？（統計分布）",
        "category": "RelatedParty", "difficulty": "★★", "result_type": "table",
        "cypher": """
            MATCH (c:Company)-[r:HAS_RELATED_PARTY]->(rp:RelatedParty)
            RETURN r.relation_category AS 關係類型,
                   count(DISTINCT rp) AS 關係人數,
                   count(DISTINCT c)  AS 涉及公司數
            ORDER BY 關係人數 DESC
        """,
    },
    "Q8": {
        "title": "公司與關係人的完整關係網路圖",
        "category": "RelatedParty", "difficulty": "★★", "result_type": "graph",
        "cypher": """
            MATCH (c:Company)-[r:HAS_RELATED_PARTY]->(rp:RelatedParty)
            RETURN c, r, rp
        """,
    },

    # ── SupplyChain 圖 ─────────────────────────────────────────────────────────
    "Q9": {
        "title": "台灣半導體上游有哪些細分領域與公司？",
        "category": "SupplyChain", "difficulty": "★★", "result_type": "table",
        "cypher": """
            MATCH (ic:IndustryChain)-[:HAS_STAGE]->(st:Stage {name: '上游'})
                  -[:HAS_SEGMENT]->(seg:Segment)
                  -[:HAS_COMPANY]->(c:Company)
            RETURN st.name AS 階段, seg.name AS 細分領域,
                   c.name AS 公司, c.stock_code AS 股票代號
            ORDER BY seg.name, c.stock_code
        """,
    },
    "Q10": {
        "title": "台積電在供應鏈中屬於哪個階段和細分領域？",
        "category": "SupplyChain", "difficulty": "★", "result_type": "table",
        "cypher": """
            MATCH (seg:Segment)-[:HAS_COMPANY]->(c:Company {stock_code: '2330'})
            MATCH (st:Stage)-[:HAS_SEGMENT]->(seg)
            RETURN c.name AS 公司, st.name AS 產業階段,
                   seg.name AS 細分領域, c.market AS 市場別
        """,
    },
    "Q11": {
        "title": "整條半導體產業鏈各階段公司數量分布",
        "category": "SupplyChain", "difficulty": "★★", "result_type": "table",
        "cypher": """
            MATCH (st:Stage)-[:HAS_SEGMENT]->(seg:Segment)-[:HAS_COMPANY]->(c:Company)
            RETURN st.name AS 產業階段, seg.name AS 細分領域,
                   count(DISTINCT c) AS 公司數
            ORDER BY st.name, 公司數 DESC
        """,
    },
    "Q12": {
        "title": "供應鏈全圖（IndustryChain → Stage → Segment → Company）",
        "category": "SupplyChain", "difficulty": "★★★", "result_type": "graph",
        "cypher": """
            MATCH (ic:IndustryChain)-[r1:HAS_STAGE]->(st:Stage)
                  -[r2:HAS_SEGMENT]->(seg:Segment)
                  -[r3:HAS_COMPANY]->(c:Company)
            RETURN ic, r1, st, r2, seg, r3, c
        """,
    },

    # ── RiskEvent 圖 ───────────────────────────────────────────────────────────
    "Q13": {
        "title": "台積電在 114Q2 揭露了哪些風險事件？",
        "category": "RiskEvent", "difficulty": "★", "result_type": "table",
        "cypher": """
            MATCH (c:Company {stock_code: '2330'})-[:HAS_RISK_EVENT]->(re:RiskEvent)
            WHERE re.report_period = '114Q2'
            RETURN re.name AS 風險名稱, re.category AS 風險類別,
                   re.description AS 說明
            ORDER BY re.category
        """,
    },
    "Q14": {
        "title": "哪個風險類別在多家公司中同時出現？（跨公司風險共振）",
        "category": "RiskEvent", "difficulty": "★★★", "result_type": "table",
        "cypher": """
            MATCH (c:Company)-[:HAS_RISK_EVENT]->(re:RiskEvent)
            WITH re.category AS category,
                 collect(DISTINCT c.name) AS companies,
                 count(DISTINCT c) AS cnt
            WHERE cnt > 1
            RETURN category AS 風險類別, companies AS 揭露公司, cnt AS 公司數
            ORDER BY cnt DESC
        """,
    },

    # ── 跨圖複合查詢 ───────────────────────────────────────────────────────────
    "Q15": {
        "title": "台積電被投資子公司中，有沒有也在供應鏈中游的公司？",
        "category": "跨圖", "difficulty": "★★★★", "result_type": "table",
        "cypher": """
            MATCH (tsmc:Company {stock_code: '2330'})-[:INVESTS_IN]->(sub:Company)
            MATCH (seg:Segment)-[:HAS_COMPANY]->(sub)
            MATCH (st:Stage)-[:HAS_SEGMENT]->(seg)
            WHERE st.name = '中游'
            RETURN tsmc.name AS 母公司, sub.name AS 子公司,
                   seg.name AS 供應鏈細分, st.name AS 產業階段
        """,
    },
    "Q16": {
        "title": "有揭露市場類風險的公司，各自投資了哪些地區？",
        "category": "跨圖", "difficulty": "★★★★", "result_type": "table",
        "cypher": """
            MATCH (c:Company)-[:HAS_RISK_EVENT]->(re:RiskEvent {category: '市場'})
            MATCH (c)-[:INVESTS_IN]->(sub:Company)-[:LOCATED_IN]->(loc:Location)
            RETURN c.name AS 公司, re.name AS 風險事件,
                   collect(DISTINCT loc.name) AS 投資地區
        """,
    },
    "Q17": {
        "title": "每家公司的完整風險畫像（風險數、子公司數、關係人數匯總）",
        "category": "跨圖", "difficulty": "★★★★★", "result_type": "table",
        "cypher": """
            MATCH (c:Company)
            WHERE c.stock_code IN ['2330','2303','3711']
            OPTIONAL MATCH (c)-[:HAS_RISK_EVENT]->(re:RiskEvent)
            OPTIONAL MATCH (c)-[:INVESTS_IN]->(sub:Company)
            OPTIONAL MATCH (c)-[:HAS_RELATED_PARTY]->(rp:RelatedParty)
            RETURN c.name AS 公司, c.stock_code AS 股票代號,
                   count(DISTINCT re)  AS 風險事件數,
                   count(DISTINCT sub) AS 被投資公司數,
                   count(DISTINCT rp)  AS 關係人數
            ORDER BY 風險事件數 DESC
        """,
    },
}
