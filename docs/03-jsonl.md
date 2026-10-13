# 用行号找出 JSONL / NDJSON 中的坏记录

日志和数据集常把一条记录放在一行中。检查整个文件时，最有用的结果是：哪一行有问题，后面的记录是否也检查过，输入是否完整读到了末尾。

从其他程序接收记录，见[实际运行的 Bash / PowerShell 管道教程](04-jsonl-pipelines.md)，包含两端退出码、UTF-8 和生成器中途失败的例子。

## 可复现例子

附带的 `examples/invalid-records.jsonl` 有四条记录：第 1 行有效，第 2 行重复使用 `id` 键，第 3 行含非标准的 `NaN`，第 4 行是有效的 `null`。

```bash
python -m offline_devkit jsonl examples/invalid-records.jsonl
```

标准输出：

```text
Lines checked: 4; valid: 2; invalid: 2
```

标准错误：

```text
line 2: duplicate object key: 'id'
line 3: non-standard JSON number: NaN
```

命令返回 2。这说明检查完成，但记录中存在错误。修复后可以重跑；工具不会修改原始数据。

用 `--json` 得到机器可读报告：

```bash
python -m offline_devkit jsonl examples/invalid-records.jsonl --json --max-errors 1
```

这次仍检查全部四行，`invalid_lines` 仍为 2，但 `errors` 只保留第一个错误，`errors_omitted` 为 1。`complete=true` 表示读到了输入末尾，不表示所有记录有效。脚本需要同时检查退出码、`invalid_lines` 和 `complete`。

## 为什么逐行读取还需要大小限制

直接遍历文本文件虽然没有一次读取整个文件，但单行仍可能非常大。这里使用带长度上限的 `readline`；超长记录先记为一个错误，再以最多 64 KiB 的块排空到该行末尾，继续检查下一行。

默认每条记录最多 1 MiB，不包含 LF 或 CRLF。限制按 UTF-8 **字节数**计算，中文字数与字节数不同。默认仅保留前 20 个错误，内存不会随全部错误的数量累积。内存仍随配置的单行上限、解码后的数据结构和错误样本上限增长，不承诺固定的常数内存。

## JSON Lines 的格式与本工具的额外规则

[JSON Lines 格式说明](https://jsonlines.org/)要求 UTF-8、每行一个有效 JSON 值，并禁止 BOM。空白行无效，`null` 这样的标量有效。CRLF 可用，最后一行可以没有换行。空输入按零条记录处理。

本工具另有严格策略：拒绝重复对象键以及 `NaN` / `Infinity`。重复键判断发生在转义解码后，所以 `"a"` 与 `"\u0061"` 是同一个键。数字解析使用原文令牌，检查 `1E-400` 或超大整数时不会先转成浮点数或有长度限制的整数。

`jsonl` 不格式化记录，也不进行 schema、数据字段或任何 AI 平台的专用数据格式验证。只接受未压缩输入；压缩流支持是后续方向。

## 读到一半失败怎么办

如果底层读取报错，报告保留已经检查的计数，设为 `complete=false`，并在 `read_error` 中说明原因，退出码为 2。超长行排空过程中失败，也保留已经确定的该行错误。如果输入文件无法打开，命令直接向标准错误写入说明，不生成 JSON 报告。

嵌套深度仍取决于 Python 的 JSON 解码器能力；超出能力会给出受控记录错误。检查运行时的输入不是文件系统快照。

实现见 [jsonl_tools.py](../offline_devkit/jsonl_tools.py)，回归测试见 [test_jsonl_tools.py](../tests/test_jsonl_tools.py)。
