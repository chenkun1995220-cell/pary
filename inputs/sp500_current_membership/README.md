# S&P 500 当前成分官方 CSV 投递入口

将从 S&P Global 官方页面导出的当前成分股 CSV 放在本目录，并命名为：

```text
official_constituents.csv
```

每周收口脚本会自动检查该文件。如果存在，会先执行 dry-run 校验，通过后才正式导入当前成分来源包。

要求：

- CSV 至少包含 `Symbol` 或 `Ticker` 列。
- ticker 数量至少应达到 400 个。
- 文件应来自 S&P Global 官方成分导出，不要使用人工核对模板或其他二手来源。
- 本目录下的 CSV 已被 `.gitignore` 忽略，不应提交到仓库。
