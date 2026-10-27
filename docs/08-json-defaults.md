# 解析成功之后，还要检查什么？

导入 JSONL 前，你可能需要确认：同一个字段有没有写两次，数据里有没有非标准数字；格式化 JSON 时，还可能需要保留数字原文。这个演练把实际输入、Python 默认处理结果和本工具输出放在一起，帮助你选择需要的规则。

## 一条命令复现

从最新源码目录运行，需要 Python 3.10+，不需要 pip 或个人数据：

```bash
python scripts/compare_json_checks.py
```

[脚本](../scripts/compare_json_checks.py)打印实际 Python 和工具版本。基线是默认 `json.loads(text)` 后执行默认 `json.dumps(value)`；本工具通过真实 CLI 子进程读取同一份临时合成文件。它核对完整报告、数字输出、输入哈希与清理情况，失败返回 2。最后的 `Comparison passed` 与脚本退出 0 表示预期差异已验证，包括两个坏样本被检查器以 2 拒绝。

脚本调用当前检出的源码；版本字符串不能证明执行的是下载的 Release 附件。脚本在 v0.4.1 源码包中提供，不在 pyz 内；本页比较的 CLI 行为从 v0.4.0 起已有。

## 三个具体差异

以下默认输出实际来自 CPython 3.12.14；脚本会打印你自己的结果，不把浮点数的具体末尾数字写死在断言里。

| 输入（一条记录） | Python 默认读入再写出 | 本工具的结果 |
| --- | --- | --- |
| `{"id":1,"\u0069d":2}` | `{"id": 2}`，只剩后一个值 | `jsonl --json` 返回 2，第 1 行 `duplicate object key: 'id'` |
| `{"score":NaN}` | `{"score": NaN}`，没有抛出解析错误 | `jsonl --json` 返回 2，第 1 行 `non-standard JSON number: NaN` |
| `{"ratio":0.123456789012345678901,"tiny":1E-400,"zero":-0}` | `{"ratio": 0.12345678901234568, "tiny": 0.0, "zero": 0}` | `json --compact` 返回 0，保留三个数字的原始写法 |

前两份检查报告都是 `lines_checked=1`、`invalid_lines=1`、`complete=true`：输入已经读完，问题在记录中。脚本打印完整 JSON 报告；gzip 读取不完整的另一种失败状态见 [gzip 演练](05-gzip-jsonl.md)。

**重复键。** `\u0069` 解码后就是 `i`，所以示例中的两个键都叫 `id`。重复键会让不同系统得到不同结果；拒绝它是本项目明确采用的严格策略，不应把它概括为所有 JSON 解析器都必须拒绝的语法错误。

**非标准数字。** `NaN` 表示“不是一个数”，不是标准 JSON 数字。Python 默认接受它，不代表接收数据的服务也接受它。`json.loads(strict=True)` 仍会接受本例中的重复键和 `NaN`；这里的 `strict` 参数针对字符串中的控制字符。

**数字原文。** 默认浮点转换和重新序列化可以改变长小数与极小数；整数转换也会把 `-0` 写成 `0`。`json` 格式化命令保留已经通过解析的数字字符，不进行十进制计算。`jsonl` 命令只检查记录并输出报告，不生成改写后的数据集。

## 什么时候用哪种方案

已有 Python 程序、需要自己的业务规则时，可以继续使用标准库：用 `object_pairs_hook` 检查重复键，`parse_constant` 拒绝非标准数字，`parse_float` / `parse_int` 控制数字转换。本项目本身也使用这些接口，见 [parse_json 与格式化器](../offline_devkit/json_tools.py)。需要十进制计算时，应另外选择 `decimal.Decimal` 和适合的序列化规则。

数字回调保留原文后，还需要相应的输出器；仅用 `parse_float=str` 再直接 `json.dumps` 会把结果写成带引号的字符串。本项目的 `format_json` 负责把已验证的数字 token 写回数字。

需要现成的 JSONL 行号、有限错误样本、读取完整性与明确退出码时，可以使用本 CLI。它不代替业务 schema、必填字段或某个数据平台的导入校验。本页只比较 Python 标准库的默认设置，不是速度排名，也不对其他工具或自定义 Python 解析器作结论。

## 5–10 分钟练习

1. 运行演练，找到默认输出里消失的 `id:1` 和变成 `0.0` 的极小数，再看对应检查器退出码。
2. 打开 Python 交互环境，运行下面四行。只改变第二个键，观察第一个对象只有一个键，第二个对象有两个键：

   ```python
   import json
   print(json.loads(r'{"id":1,"\u0069d":2}'))
   print(json.loads(r'{"id":1,"other":2}'))
   print(json.loads('{"score":NaN}', strict=True))
   ```

3. 阅读源码里的 `_object`、`_constant` 和 `parse_json`，把 `object_pairs_hook`、`parse_constant` 与 `parse_int` / `parse_float` 分别对应到“重复键”“非标准数字”“数字原文”。能解释这些对应关系后，再尝试向别人说明为什么“默认解析成功”和“符合导入前检查规则”是两件事。

默认行为与配置接口依据：[Python 3.10 json 文档](https://docs.python.org/3.10/library/json.html#standard-compliance-and-interoperability)、[Python 3.12 解码器与回调文档](https://docs.python.org/3.12/library/json.html#json.JSONDecoder)。更细的数字实现见 [技术笔记 01](01-json-numbers.md)。

## English

### Reproduce the settings comparison

Run `python scripts/compare_json_checks.py` from the latest checkout with Python 3.10+. No pip or personal data is needed. The script prints actual Python/tool versions, inputs, baseline outputs and complete CLI reports. Its baseline is default `json.loads(text)` followed by default `json.dumps(value)`. The CLI reads the same disposable synthetic files. Input hashes, report contents, number output and cleanup are checked; a mismatch returns 2. `Comparison passed` and script exit 0 mean both rejected inputs were correctly rejected with validator exit 2.

This runs the current checkout; a source version string is not proof that a downloaded release was executed. The script is included in the v0.4.1 source distribution, not the pyz; the compared CLI behaviors already exist in v0.4.0.

| Input | Default output on CPython 3.12.14 | CLI outcome |
| --- | --- | --- |
| `{"id":1,"\u0069d":2}` | `{"id": 2}` | `jsonl --json`: exit 2, duplicate `id` on line 1 |
| `{"score":NaN}` | `{"score": NaN}` | `jsonl --json`: exit 2, non-standard number on line 1 |
| `{"ratio":0.123456789012345678901,"tiny":1E-400,"zero":-0}` | `{"ratio": 0.12345678901234568, "tiny": 0.0, "zero": 0}` | `json --compact`: exit 0, all three original number spellings retained |

The script prints your runtime's actual results without asserting a specific float tail. Both rejected records have `complete=true`: reading finished, but the record violates the selected rules. Compare [gzip read failures](05-gzip-jsonl.md#english), where counters may be partial.

Duplicate names are an interoperability risk; rejecting them is this project's explicit policy. Escapes are decoded before comparing names. `NaN` is outside standard JSON numbers. Python's `strict=True` controls string control characters and does not reject these duplicate-key or NaN examples. Preserving number spelling during `json` formatting is not decimal arithmetic; `jsonl` only validates and reports, without rewriting the dataset.

Python can implement these policies through `object_pairs_hook`, `parse_constant`, `parse_float` and `parse_int`; this project uses those interfaces too. Retaining numeric text also requires a matching renderer: `parse_float=str` followed directly by `json.dumps` produces quoted strings. This project's `format_json` writes validated numeric tokens as numbers. Keep using the standard library when you want custom application logic. Use this CLI when you want ready-made line numbers, bounded error samples, read-completeness reports and exit codes. Neither this comparison nor syntax checking validates application schemas or a particular import service. This is not a speed ranking or a claim about other tools or configured Python decoders. The Python documentation linked above describes the defaults and hooks.

For a 5–10 minute exercise, run the script, then try the four-line interactive example above. Observe the overwritten first value, two distinct keys after changing the second name, and NaN still accepted with `strict=True`. Read `_object`, `_constant` and `parse_json` in [json_tools.py](../offline_devkit/json_tools.py) and match each hook to the policy it implements.
