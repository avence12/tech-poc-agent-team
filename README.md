# Technical Survey / PoC Agent Team

讓沒有工程師下屬的 IC Technical Manager，在 Claude Code 中執行技術 survey 與 PoC。
適用於 Web Application 與 CCTV 邊緣 AI；每次處理一個可決策的技術問題。

- A（Opus）：架構、impact、方案分析與主管決策報告。
- B（Opus）：最小 PoC／實驗與可重現證據。
- C（Sonnet）：獨立 checklist、證據審查與修正要求。
- Human：核定問題與門檻、裁決爭議、final review。

執行器自動交接報告，最多三次實驗；否證也能成功收斂。各角色保留獨立
context，scope／criteria 變更與報告核可需要人的明確授權。

## 開始使用

需要 macOS／Linux、Python 3.10+ 與已登入的 Claude Code CLI。
在此 repository 根目錄開啟 Claude Code，輸入：

```text
/tech-poc <你的技術問題>
```

完整流程、手動 CLI、權限、四指標與跨專案安裝方式，見
[操作說明](agent-team/README.md)。

[Claude skill](.claude/skills/tech-poc/SKILL.md) 與
[設計規格](agent-team/DESIGN.md) 一併包含在 repository 中。

## 驗證

```bash
python3 -m unittest discover -s agent-team/tests -v
```

測試使用 fake Claude executable，不會呼叫 LLM。真實登入、模型回應與專案
工具權限，需在第一個實際研究題目驗證。
