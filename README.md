# 建筑标准公开检索门户（standard-portal）

公开的"国家标准名录查询 + 治理数据展示 + 演示检索"单页应用。

## 功能

1. **名录查询**：3 万本标准题录检索（标准号 / 名称 / 状态 / 分类 / 日期 / 引用数），前端本地过滤，毫秒级响应。
2. **治理统计**：29 本治理规范、chunk / 强条 / QC 等聚合指标展示（由私有管线导出）。
3. **演示检索**：小样本条文检索，返回"条文号 + 自写摘要 + 官方源链接"，不含条文原文。

## 数据分层与合规边界

| 层 | 内容 | 公开 |
|---|---|---|
| 名录层 | 标准号 / 名称 / 状态 / 日期 / 分类（事实信息） | ✅ |
| 方法论层 | 导出校验脚本、schema、README | ✅ |
| 证据层 | 29 本聚合统计、评测指标 | ✅ |
| 演示层 | 条文号 + 自写摘要 + 官方链接（小样本） | ✅ |
| 全文层 | 清洗后 chunk 全文、真题集 | ❌ 仅私有 |

数据来源：国家标准全文公开系统（openstd.samr.gov.cn）等官方公开题录。
名录由私有 pipeline 定期抓取、清洗、导出，公开仓库只接收校验后的脱敏产物。

## 目录结构

```text
standard-portal/
├── index.html              # 单页入口（无构建、无外部依赖）
├── assets/
│   ├── app.js              # 前端检索逻辑
│   └── style.css
├── data/public/
│   ├── catalog.json        # 名录（公开）
│   ├── stats.json          # 聚合统计（公开）
│   └── demo.json           # 演示检索子集（公开）
├── scripts/
│   └── export_public.py    # 私有产物 → 公开产物：白名单 + 泄漏校验 + 导出
├── .github/workflows/
│   └── deploy.yml          # 校验 → 部署 GitHub Pages
└── README.md
```

## 本地运行

直接用浏览器打开 `index.html` 会因 `fetch` 的 file:// 限制而无法加载数据，请起一个本地静态服务：

```bash
python -m http.server 8000 --directory .
```

然后访问 http://localhost:8000 。

## 更新公开数据（私有侧执行）

```bash
python scripts/export_public.py \
  --registry <私有 registry.json> \
  --demo <私有 enrich.json> \
  --demo-id ZJXFZN-2020 \
  --demo-title "浙江省消防难点问题操作技术指南（2020版）" \
  --demo-source-url https://openstd.samr.gov.cn/bzgk/std/ \
  --outdir data/public
```

导出器会做字段白名单、内部域名/正文泄漏探测、规模与体积断言，全部通过才写文件。
产物提交后，GitHub Actions 部署前会再跑一次 `--check` 校验。

## 版权声明（README 里建议保留）

- 题录信息（标准号、名称、状态、日期、分类）为事实信息，来源标注官方平台。
- 本站不发布标准条文全文；检索结果仅提供条文号、自写摘要与官方源链接。
- 完整治理数据（清洗后 chunk、评测集等）属于私有资产，不在本仓库发布。
