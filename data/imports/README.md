# 外部 CSV 导入目录

把券商、东方财富、Wind、Choice 或其他来源导出的 CSV 放在这里。

示例：

```powershell
powershell.exe -ExecutionPolicy Bypass -File F:\chatgptssd\project2\scripts\map_external_fields.ps1 -InputPath F:\chatgptssd\project2\data\imports\your_export.csv -Output data\raw\imported_mapped.csv
```

转换后请先检查 `data\raw\imported_mapped.csv` 的字段和数值，再参与每周筛选。
