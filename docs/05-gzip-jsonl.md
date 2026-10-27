# 直接检查 gzip 压缩日志

从 v0.4.0 起，`jsonl --gzip` 可以直接读取压缩文件，或者读取上游程序输出的 gzip 二进制字节。它不生成解压文件，检查仍在本机完成。

## 无需准备数据的首次体验

在最新源码目录运行，脚本只在临时目录生成合成样本，自动清理，使用真实 CLI 核对完整 gzip、重复键和截断 gzip 三种结果：

```bash
python scripts/try_jsonl.py
```

应依次看到检查器退出码 `0 / 2 / 2`；重复键位于第 2 行，截断 gzip 的 `complete=false`。脚本本身返回 0 表示三种预期都得到验证，不表示坏输入有效。截断时部分计数不保证跨 Python 版本相同。

从 Releases 下载并按[发布文档](publishing.md)完成来源 / SHA-256 检查后，也可以让相同脚本验证已有下载包（路径替换为你自己的文件）：

```bash
python scripts/try_jsonl.py --archive ../release-download/offline-devkit.pyz
```

归档在源码目录外以隔离导入模式运行，不会借用当前源码。脚本只用 Python 标准库，输入哈希和未生成解压文件也会核对。演练脚本从 v0.4.1 源码包起提供；单文件下载包本身只包含 CLI 与许可证，不包含这个脚本。

## 手动构造样本

在源码目录里，用附带的三条有效记录生成一个新的压缩样本；这些命令适用于已安装 Python 的 Bash 和 PowerShell：

```bash
python -c "import gzip; from pathlib import Path; Path('records-demo.jsonl.gz').write_bytes(gzip.compress(Path('examples/records.jsonl').read_bytes(), mtime=0))"
python -m offline_devkit jsonl records-demo.jsonl.gz --gzip --json
python -c "from pathlib import Path; p=Path('records-demo.jsonl.gz'); Path('records-truncated.jsonl.gz').write_bytes(p.read_bytes()[:-4])"
python -m offline_devkit jsonl records-truncated.jsonl.gz --gzip --json
```

第二条检查返回 0，报告为三条有效记录、`complete=true`。最后一条返回 2，报告包含 `complete=false` 和 `read_error`。它可能已经交付部分有效记录，但压缩流没有完整通过检查，不能只看 `invalid_lines` 是否为零。

单文件下载包使用相同参数：

```bash
python offline-devkit.pyz jsonl records-demo.jsonl.gz --gzip --json
```

文件扩展名不触发自动解压。只有 `--gzip` 切换输入模式；普通文本使用原来的 `jsonl FILE`。

## 二进制标准输入

下面的 Python 调用显式传递字节，跨平台使用时不经过 shell 的文本解码与重新编码：

```python
from pathlib import Path
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "offline_devkit", "jsonl", "-", "--gzip", "--json"],
    input=Path("records-demo.jsonl.gz").read_bytes(),
    capture_output=True,
)
print(result.stdout.decode("utf-8"), end="")
raise SystemExit(result.returncode)
```

这是小样本的可复现示例，会将压缩文件读进调用方内存。处理大文件时直接传文件路径，或把已经打开的二进制文件对象作为 `stdin=`，无需自己读完整文件。不要用 PowerShell `Get-Content` 的文本管道传递 gzip 字节；有关普通 UTF-8 JSONL 管道的两端退出码，见[管道教程](04-jsonl-pipelines.md)。

## 报告与限制

| 情况 | `complete` | 退出码 |
| --- | --- | --- |
| 压缩流完整，全部记录有效 | `true` | 0 |
| 压缩流完整，有重复键、NaN、超长行等记录错误 | `true` | 2 |
| 压缩格式、CRC、解压长度、DEFLATE 错误或截断 | `false` | 2 |
| 文件无法打开 | 无 JSON 报告，标准错误说明 | 2 |

行号按**解压后的物理行**计算。`--max-line-bytes` 仍默认 1 MiB，不含 LF / CRLF，按解压后 UTF-8 字节计算。超长行仍分块排空，`--max-errors` 仍只保留有限样本。多个 gzip member 依次连接成一个字节流，段边界不会自动插入换行，行号也不重置。

检查器会持续读取到压缩流末尾，包括各段的 CRC 和长度字段。错误可能在缓冲读取时出现；部分计数只说明已经交给记录检查器的内容，不能证明前缀完整性，也不是原文件的总记录数。底层读取异常同样设为不完整。与 Python 标准库一致，空字节流和空的 gzip 内容都得到零条记录。gzip CRC 用来检测格式损坏，不能证明作者身份或防止恶意篡改。

行大小限制和错误样本限制并不提供总解压量、总运行时间或 CPU 上限。读取的是正在打开的输入，并非文件系统快照。工具不验证业务 schema，不上传数据，也不改写输入文件。

实现依据：[Python gzip 文档](https://docs.python.org/3.12/library/gzip.html)，其中说明非法压缩流可能抛出 `BadGzipFile`、`EOFError` 或 `zlib.error`；这些错误都转换为报告中的不完整状态。测试见 [test_gzip_jsonl.py](../tests/test_gzip_jsonl.py) 和 [test_zipapp.py](../tests/test_zipapp.py)。

## English

For a disposable first run, execute `python scripts/try_jsonl.py` from the latest source checkout. It invokes the real CLI and verifies complete gzip, a duplicate key on line 2, and a truncated gzip stream. Validator exits are 0 / 2 / 2; the demo itself exits 0 only when all expected outcomes are verified. It cleans synthetic samples, checks input hashes, and creates no extracted files. After independently verifying an existing trusted download, use `--archive PATH` to run it outside the source directory with isolated imports. The demo script is available in source distributions from v0.4.1, not in the portable archive.

Use `python -m offline_devkit jsonl FILE --gzip --json`, or replace `-m offline_devkit` with `offline-devkit.pyz`. Gzip is explicit; suffixes do not enable it. Files and binary stdin are supported without writing an extracted file. Keep compressed pipelines binary; using the file path avoids shell text conversion.

Line numbers and the default 1 MiB record limit apply to decompressed bytes, excluding LF/CRLF. Existing strict JSON rules and bounded error samples still apply. Concatenated members form one continuous byte stream, with no inserted newline or reset line numbers.

Valid records and a fully read stream return 0. Invalid JSON records return 2. Header, DEFLATE, CRC, size, truncation or underlying read failures preserve previously checked counts, set `complete=false` and `read_error`, and return 2. Counters are partial when the stream fails; zero invalid records alone does not mean success or establish prefix integrity. Empty input follows the standard-library reader and contains zero records. CRC is corruption detection, not authentication.

The wrapper leaves the caller's compressed stream open. It has no total decompressed-byte, CPU or time budget. It validates syntax rather than application schemas and does not modify or upload input. Tests exercise real file/stdin subprocesses and an isolated portable archive; CI checks the installed command too.
