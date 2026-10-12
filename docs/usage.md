# 命令手册

在仓库根目录运行 `python -m offline_devkit --help`。安装到虚拟环境后，可以将前缀换成 `offline-devkit`。所有命令都只读取输入，结果写到标准输出，错误写到标准错误。

命令输出统一为 UTF-8、LF 换行，Windows 重定向时也保持相同字节格式。格式化后的 JSON 以一个 LF 结尾。

## JSON

```bash
python -m offline_devkit json [FILE] [--check] [--sort-keys] [--compact] [--indent 2|4]
```

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `FILE` | `-` | UTF-8 文件；`-` 读取标准输入 |
| `--check` | 关闭 | 只校验，成功不输出内容 |
| `--sort-keys` | 关闭 | 对所有层级的对象键排序 |
| `--compact` | 关闭 | 删除可省略的空白；此时忽略缩进设置 |
| `--indent` | `2` | 美化缩进，可选 2 或 4 个空格 |

支持顶层字符串、数字、布尔值、`null`、数组、对象。拒绝尾随逗号、注释、多份拼接文档、重复键与非标准数字。允许文件或输入开头有一个 UTF-8 BOM。

数字在解析时存储为私有的字符串子类，序列化时写回原始字符序列。它不适合直接做算术。字符串会经过解码和重新编码，所以转义的写法可能改变；对象键顺序默认保留。

输入最大 16 MiB。嵌套深度由 Python 解码器和递归限制决定，因此 `--check` 可能接受格式化无法处理的深度；解码或渲染触及限制时会报告受控错误。程序没有大型流式 JSON 或 JSON Lines 支持。

不指定文件时，可以直接管道传入：

```bash
python -m offline_devkit json examples/config.json --compact | python -m offline_devkit json --check
```

不要使用 `... json config.json > config.json`：shell 会先清空输入文件。请写到新的文件。

## 目录命令共同参数

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `DIRECTORY` | `.` | 根目录，必须是真实存在的目录 |
| `--exclude GLOB` | 无 | 匹配相对路径或 basename，可重复使用 |
| `--include-ignored` | 关闭 | 包含默认跳过的依赖、缓存目录 |
| `--json` | 关闭 | 输出机器可读的 JSON 报告 |

默认跳过的目录：`.git`、`.venv`、`venv`、`node_modules`、`__pycache__`、`.pytest_cache`。任意层级的同名目录都跳过；同名普通文件不会因此被跳过。`.gitignore` 不会被读取。

Glob 匹配区分大小写，规则为 Python `fnmatch.fnmatchcase`。相对路径统一使用 `/`。`*` 可以匹配 `/`，与 shell 的路径 glob 不完全相同。匹配目录时整个子树都跳过。`excluded_entries` 统计被跳过的入口数，不是子树的文件总数。

符号链接、Windows 重解析点始终跳过；普通文件才进入统计，设备与管道等特殊文件忽略。根目录本身不能是链接。传入路径的祖先目录仍由操作系统正常解析。

目录扫描一次收集文件元数据，内存用量随文件数量增长。哈希内容按 1 MiB 分块读取，不把大文件整体放进内存。并发扫描 / 修改不提供一致性快照。

目录加入待扫描队列时记录设备与 inode；进入该目录前、列出条目后重新读取 `lstat`，检查它仍为非链接目录且身份未变。发现替换时不处理该目录的条目，将 `directory changed during scan; rerun when directories are stable` 写入 `errors`，`dupes` 和 `sizes` 均返回 2。目录消失或不可访问时也记录相应读取错误。

检查仍通过路径完成，检查与后续操作之间存在竞态，祖先目录替换也未被完全防护；文件系统不提供有效设备 / inode 时，普通目录替换可能无法识别。请等待修改结束后重跑，不要将部分报告视为完整结果。

## 重复文件

```bash
python -m offline_devkit dupes [DIRECTORY] [--min-size BYTES] [--fail-if-found] [共同参数]
```

默认 `--min-size 1` 不纳入空文件。`--min-size 0` 包含空文件；字节数必须是非负整数。只有存在相同大小的候选文件才计算哈希。

同一设备与 inode 的硬链接路径只保留字典序最前的一条参与哈希；如果文件系统不提供有效 inode，则无法可靠去重硬链接。报告输出不表示保留 / 删除建议。工具没有文件删除接口。

分组按冗余逻辑字节从大到小排序，同值时按第一条相对路径排序。

| JSON 字段 | 含义 |
| --- | --- |
| `root` | 绝对扫描路径 |
| `files_scanned` | 纳入扫描的普通文件路径数 |
| `files_hashed` | 成功计算 SHA-256 的候选文件数 |
| `hardlinks_skipped` | 跳过的硬链接别名数 |
| `min_size_bytes` | 本次最小文件长度 |
| `groups` | 相同长度、相同 SHA-256 的分组 |
| `groups[].sha256` | 内容摘要 |
| `groups[].size_bytes` | 每个文件的逻辑长度 |
| `groups[].paths` | 按字典序排序的相对路径 |
| `groups[].redundant_bytes` | `size_bytes × (paths 数量 − 1)` |
| `redundant_bytes` | 分组的冗余字节总和，非真实可释放空间 |
| `symlinks_skipped` | 跳过的符号链接 / 重解析点入口数 |
| `excluded_entries` | 默认目录或自定义 glob 排除的入口数 |
| `errors` | 未完成读取、文件变化、权限等错误 |

哈希前后检查设备、inode、长度、纳秒修改时间和读取字节数。文件消失、被替换或检测到修改时加入 `errors`，不会悄悄当作成功。检查无法检测所有并发变化；SHA-256 分组也不提供逐字节复核。

## 目录大小

```bash
python -m offline_devkit sizes [DIRECTORY] [--top N] [共同参数]
```

`--top` 默认为 10，必须是正整数，只限制最大文件列表长度，不影响目录汇总。

| JSON 字段 | 含义 |
| --- | --- |
| `total_bytes` | 所有纳入普通文件路径的逻辑长度总和 |
| `directories` | 一级目录汇总；`./` 代表根目录直接存放的文件 |
| `directories[].path` | 一级目录名称或 `./` |
| `directories[].files` | 子树内纳入的普通文件路径数 |
| `directories[].size_bytes` | 子树内逻辑字节总和 |
| `largest_files` | 按长度倒序、相对路径正序的前 N 个文件 |
| `largest_files[].path` | 相对路径 |
| `largest_files[].size_bytes` | 逻辑文件长度 |

另外包含 `root`、`files_scanned`、`symlinks_skipped`、`excluded_entries`、`errors`，含义与重复文件报告相同。硬链接各路径单独累计；稀疏文件、压缩、写时复制不会修正为磁盘块占用。

## 自动化与退出码

`--json` 的标准输出始终是报告，处理错误包含在 `errors` 数组中。只要 `errors` 非空，退出码为 2，即使其他文件已经成功处理。人类可读格式还会把错误写到标准错误。

| 状态 | 退出码 |
| --- | --- |
| 完整处理 | 0 |
| `dupes --fail-if-found` 检出重复 | 1 |
| 参数错误、输入错误、处理不完整 | 2 |
| 中断 | 130 |

可以把报告写到扫描目录以外的位置：

```bash
python -m offline_devkit dupes examples/files --json > duplicate-report.json
```

本例扫描 `examples/files`，报告写到仓库根目录，所以不会被纳入扫描。
