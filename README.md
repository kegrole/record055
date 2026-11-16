# resample

把不规则时间序列重采样成固定频率的纯标准库工具（无第三方依赖，Python 3.11+）。

## 用法

```bash
python -m resample.cli --input demo/series.csv --freq 1m --out out/report.json
```

命令结束后在 stdout 打印一行摘要（原始点数、桶数、空值桶数、填补点数），
并把完整报告写入 `--out` 指定的 JSON 文件。

### 参数

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--input` | （必填） | 输入 CSV，列为 `timestamp,value` |
| `--freq` | （必填） | 目标频率：`1m`、`5m`、`1h`、`1d` |
| `--out` | 无 | 报告输出路径（JSON） |
| `--agg` | `mean` | 聚合函数：`sum`、`mean`、`min`、`max`、`count`、`last` |
| `--closed` | `left` | 窗口边界语义：`left`、`right`、`both`、`neither` |
| `--label` | `left` | 桶标签取窗口的 `left`（左缘）或 `right`（右缘） |
| `--tz` | 无（UTC） | IANA 时区名，如 `Europe/Berlin`；按本地墙钟时间切桶 |
| `--max-gap` | `3` | 线性插值允许的最大缺口（空桶数），`0` 表示不填补 |

## 窗口边界语义

- `closed=left`：窗口为 `[start, end)`，正好落在边界上的点归入以该时刻起始的桶。
- `closed=right`：窗口为 `(start, end]`，边界点归入前一个桶。
- `closed=both`：窗口为 `[start, end]`，边界点同时归入相邻两个桶。
- `closed=neither`：窗口为 `(start, end)`，边界点不落入任何桶。
- `label` 决定输出中 `bucket_start` 显示窗口的左缘还是右缘，不影响分桶。

输出桶范围从最早数据点向下对齐到频率边界开始，到最晚数据点所在的
上一级自然周期结束为止（`1m`/`5m` 覆盖整点小时，`1h`/`1d` 覆盖整天），
因此序列末尾之后可能出现空桶。

## 空桶与填补

- 空窗口的 `value` 输出 `null`（JSON）/ `None`，任何聚合函数都不会填 0。
- 线性插值只填补**内部缺口**（两端都有真实值的连续空桶段），且缺口长度
  不超过 `--max-gap` 个桶；序列首尾的空桶段永不填补（禁止外推）。
- 被填补的桶 `filled` 为 `true`，填补完全由 `--max-gap` 配置驱动。

## 时区处理

- 输入时间戳可带任意 ISO-8601 偏移（或 `Z`），内部统一归一到 UTC。
- 指定 `--tz` 后，分桶在本地墙钟时间上进行：`1d` 按本地午夜切，`1h`
  按本地整点标签切。夏令时回拨日（如 Europe/Berlin 2026-10-25，真实 25
  小时）重采样到 `1h` 仍得到 24 个桶，两次出现的 02:00 归入同一个桶，
  该桶只出现一次；同一天按 `1d` 切正好 1 个桶。
- 输出 `bucket_start` 始终带时区偏移。

## 输出格式

```json
{
  "summary": {"raw_points": 12, "buckets": 60, "empty_buckets": 48, "filled_points": 0},
  "buckets": [
    {"bucket_start": "2026-03-10T00:00:00+00:00", "value": 10.0, "filled": false}
  ]
}
```

每个桶固定包含三个字段：`bucket_start`（带时区）、`value`（可为 `null`）、
`filled`（是否由插值填补）。

## 测试

```bash
cd tests && python -m unittest test_resample -v
```
