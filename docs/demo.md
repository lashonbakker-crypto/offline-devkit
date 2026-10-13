# Reproduce the README demo / 复现首页演示

The animation renders actual stdout and stderr captured from the included fixtures. It demonstrates behavior, not performance. The local absolute scan root is omitted from the duplicate-report excerpt; other displayed output is unchanged. Stdout and stderr are grouped for readability.

动图来自下列命令的实际输出，不是速度测评。重复文件片段省略了本机绝对根路径；标准输出和标准错误分组显示，便于阅读。

Run from the repository directory / 在仓库根目录运行：

```bash
python -m offline_devkit json examples/precision.json --compact
```

```json
{"id":9007199254740993123456789,"ratio":1E-400,"negative_zero":-0}
```

The number spellings remain intact / 数字原文保持不变。

```bash
python -m offline_devkit jsonl examples/invalid-records.jsonl
```

```text
Lines checked: 4; valid: 2; invalid: 2
line 2: duplicate object key: 'id'
line 3: non-standard JSON number: NaN
```

This command intentionally returns 2: the fixture includes two bad records / 本命令有意返回 2，因为示例包含两条坏记录。

```bash
python -m offline_devkit dupes examples/files
```

There is one duplicate group: `copies/note-copy.txt` and `note.txt`. `unique.txt` is different. Files are unchanged by the command / 应发现一个重复组，且所有文件保持原样。

Try a completely valid JSONL fixture / 试用全部有效的 JSONL 文件：

```bash
python -m offline_devkit jsonl examples/records.jsonl
```

```text
Lines checked: 3; valid: 3; invalid: 0
```

Portable archive users can replace `python -m offline_devkit` with `python offline-devkit.pyz`; fixtures are available in the source download / 使用单文件包时可以更换命令前缀；示例文件包含在源码下载中。
