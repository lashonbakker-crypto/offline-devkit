# 发布与下载包

仓库已公开，日常改动基于远程 `main`，不要重新初始化或用早期源码包覆盖现有历史。当前源码版本为 0.4.0；[v0.4.0 已实际发布](https://github.com/lashonbakker-crypto/offline-devkit/releases/tag/v0.4.0)，下载包新增 `jsonl --gzip`，并保留 `dupes --verify-bytes`。

## 单文件运行包

```bash
python -m unittest discover -s tests -v
python scripts/build_zipapp.py
python dist/offline-devkit.pyz --version
python dist/offline-devkit.pyz jsonl examples/records.jsonl --json
```

构建只依赖 Python 标准库，不需要下载第三方包。`dist/` 是生成目录，不提交到 Git。发布时将 `offline-devkit.pyz` 和 SHA-256 校验文件附加到 GitHub Release；源码通过该标签的标准 ZIP / tar.gz 提供。先检查该提交的实际五组 CI 结果，再发布对应版本。

生成包包含本项目源码、入口与 MIT 许可证；需要 Python 3.10+。测试会在源码目录外确认归档能够独立导入，并正确传播失败退出码。

## GitHub 自动构建发布

在 Actions 中手动运行 **Release portable download**。它重新运行测试，从当前提交构建归档与 SHA-256，读取 `docs/releases/v版本.md`，建立与源码版本相同的标签和 Release，并附加两个下载文件。已有同名发布会停止，避免覆盖历史标签或附件。

发布任务只在手动触发时运行；GitHub 提供的短期令牌仅为发布 job 开启仓库内容写权限，不持久化凭据。该流程不会在普通提交或 PR 时自动发布。

## 下载后验证 / Verify your download

从同一个 [Release](https://github.com/lashonbakker-crypto/offline-devkit/releases/latest) 下载 `offline-devkit.pyz` 和 `SHA256SUMS.txt`，放在同一个目录，再在该目录打开终端。以下命令只读取两个文件，不需要 pip，也不会运行归档内容：

Download both assets from the same release into one directory, then open a terminal there. This standard-library command reads the files without executing the archive. On Windows use `py -3` if needed; on macOS / Linux use `python3` if `python` is unavailable.

```bash
python -c "import hashlib, sys; from pathlib import Path; expected = Path('SHA256SUMS.txt').read_text(encoding='utf-8').split()[0]; actual = hashlib.sha256(Path('offline-devkit.pyz').read_bytes()).hexdigest(); ok = actual == expected; print('SHA-256 OK' if ok else 'SHA-256 MISMATCH'); sys.exit(0 if ok else 2)"
```

完整且匹配的下载应输出 `SHA-256 OK`，退出码为 0。输出 `SHA-256 MISMATCH`、退出码为 2 时，重新从同一版本下载两个附件再检查；文件缺失或校验文件为空会产生 Python 错误并返回非零状态。不要混用不同版本的校验文件。

A matching download prints `SHA-256 OK` and exits 0. A mismatch prints `SHA-256 MISMATCH` and exits 2: download both assets again from the same version. Missing files or an empty checksum file produce a Python error and a nonzero status.

SHA-256 是根据文件内容计算的摘要，内容变化会使这里的比较失败。它能帮助发现下载损坏或版本混用；同时下载的校验文件不是独立签名，不能证明发布者身份。

The checksum helps detect corrupted or mismatched downloads. It is not an independent signature or proof of the publisher's identity.

确认校验结果后，可在源码仓库之外运行这两个命令：

After verifying, run these commands outside the source repository:

```bash
python offline-devkit.pyz --version
python offline-devkit.pyz json --compact
```

第一条在 v0.3.0 应输出 `offline-devkit 0.3.0`。第二条等待标准输入：输入 `{"number":1E-400}` 后结束输入（macOS / Linux：新行按 Ctrl+D；Windows：新行按 Ctrl+Z 后回车）。应输出 `{"number":1E-400}`，保留数字原文。单文件包仍需要 Python 3.10+；它不是无需 Python 的原生可执行文件。

For v0.3.0, the first command prints `offline-devkit 0.3.0`. The second reads stdin: enter `{"number":1E-400}` and signal EOF (Ctrl+D on a new line on macOS / Linux; Ctrl+Z then Enter on Windows). It should print `{"number":1E-400}` with the numeric token unchanged. The archive still requires Python 3.10+.

## 可重复的附件复验 / Repeatable asset verification

在包含本仓库源码的终端中，用新的验证脚本检查已下载的两个文件。以 v0.3.0 为例，假设附件放在仓库外的 `../release-download/`：

```bash
python scripts/verify_release_download.py ../release-download --expected-version 0.3.0
```

默认用当前源码核对归档内的六个模块、入口和许可证。要检查其他发布版本，使用该标签的源码目录，并追加 `--source-directory ../released-source`；不要用不同版本的源码验证附件。

源码必须保留 Git 中的原始字节。当前源码将 `LICENSE` 固定为 LF；旧标签在 Windows 上可能因 `core.autocrlf` 被检出为 CRLF，普通 `git archive` 也会受该配置影响。若使用 Git 克隆的仓库，推荐指定标签，让脚本按一次性 LF 设置导出到临时目录：

```bash
python scripts/verify_release_download.py ../release-download --source-ref v0.3.0 --expected-version 0.3.0
```

`--source-ref` 需要已安装 Git 和本地已有该标签；不会联网，不修改全局 Git 配置或工作树。源码 ZIP 用户可以直接用前面的目录方式。不要仅为通过检查而重新生成下载包或修改校验文件。

脚本先检查 SHA-256 和源码字节，两者通过后才运行归档。检查失败返回 2；成功输出 `SHA-256 OK`、`Source bytes OK` 和各项命令检查结果。实际命令在临时目录中通过 `python -I` 执行，以免误从源码目录导入模块：

- 核对版本，以及大整数、长小数、指数和 `-0` 的原文。
- 检查 0–3 个 BOM、文件 / 标准输入、校验 / 格式化共 16 种组合。
- 运行默认哈希和逐字节复核两种重复报告，确认 `--fail-if-found` 返回 1，以及目录大小结果。
- 检查有效 JSONL 的 3 行、无效示例的 4 行和第 2 / 3 行错误，确认输入错误返回 2、示例字节未改动。

This script checks already-downloaded assets without downloading or rebuilding them. It verifies the checksum, all module bytes, the entry point and license against matching release source **before executing the archive**. It then runs isolated CLI probes in a temporary directory, checks exit codes and confirms fixture bytes are unchanged. Use `--source-directory` for a different release's source. Successful verification exits 0; failures exit 2. This checks compatibility and release consistency, not an independent publisher signature or application schemas.

维护者可以在 Actions 手动运行 **Verify published download**，输入 `v0.3.0` 或后续标签。五组环境从 Release 下载相同的附件，不重新构建，并核对标签源码：Linux / Python 3.10、3.12、3.14，以及 Windows 和 macOS 15（Intel）/ Python 3.12。工作流只有仓库读取权限，不发布或覆盖附件；普通提交不会触发它。

Maintainers can manually run **Verify published download** for a published tag. Its five environments download the same release assets, compare them with tagged source and run the verifier. The shared `--source-ref` path uses `git -c core.autocrlf=false -c core.eol=lf archive` to avoid inherited newline conversion in both checkout and archive. It requires Git and an existing local ref, uses a temporary source directory, performs no network access and does not change Git settings or the working tree. Source-ZIP users can use the directory-only path. The workflow has read-only repository permissions and never publishes or overwrites assets. Intel macOS results do not establish Apple Silicon coverage.

## v0.4.0 下载附件复验记录 — 2026-10-17

发布标签固定于提交 `61072bba671b1ed3a7f721158fbe2f7d97a240aa`。该提交的[五组源码 CI](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/39078919907)与[发布任务](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/39079008448)均成功。源码检查运行 79 项测试；Windows 的 FIFO 测试按系统能力跳过，其余通过。各环境还检查安装入口、便携包 gzip 输入，以及 Bash 或 PowerShell 的三种管道情况。

[五组实际下载复验](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/39079074297)全部成功：Linux / Python 3.10、3.12、3.14，以及 Windows 和 macOS 15（Intel）/ Python 3.12。逐组检查了实际日志：

- 从公开 Release 下载同一个 `offline-devkit.pyz`（10792 字节）和 `SHA256SUMS.txt`（85 字节）。
- 运行包 SHA-256 为 `349b3fdda2c55f37e2c422935ef63718f2950f65076fe0f45309ad4f0e44fc64`，与校验文件一致。
- 运行包中的六个模块、入口和许可证逐字节对应发布标签源码，再在源码目录外执行实际附件。
- gzip 文件与二进制 stdin、解压后单行上限、CRC 和截断失败返回 2 均通过；同时保留精确 JSON 数字、BOM、重复文件及目录大小验证，样本文件未被工具改写。

发布页的校验文档链接已修正为完整仓库地址，避免 Markdown 在 Release 页面将相对链接解释到错误路径。上述结果是功能正确性验证，不提供总解压量、CPU 或运行时间预算，也不包括 Apple Silicon 或性能规模结论。

The published v0.4.0 archive passed actual download verification in all five environments: Linux / Python 3.10, 3.12 and 3.14; Windows and Intel macOS / Python 3.12. Each downloaded the same 10792-byte archive and 85-byte checksum file, verified SHA-256 and all tagged module/entry/license bytes, then ran isolated gzip file/stdin, CRC, truncation, decompressed-record-limit and existing CLI checks. Source CI ran 79 tests, with one unsupported FIFO case skipped on Windows. The installed CLI also passed a local success/truncation smoke check outside the source tree. These checks do not establish Apple Silicon support, performance bounds or a total decompression budget.

## v0.3.0 下载附件复验记录 — 2026-10-14

在 Linux / Python 3.12.14 实际下载 v0.3.0 的两个附件并运行上述脚本：

- 归档为 10514 字节，SHA-256 为 `7c5da2d75b60648946747345e008a30d0b9d745b2f076412f81a7b106afdd1cb`，与下载的校验文件和 GitHub 附件摘要一致。
- 六个模块、入口与许可证匹配发布提交 `884ee1c45bd526f3ff9962d3fb98357114c2e9f3`；独立运行验证全部通过。
- 用错误校验值复验，脚本返回 2 且未运行归档；替换模块并重算匹配的校验值，源码一致性检查仍返回 2，阻止运行该归档。
- 首次[下载验证](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38468084030)的 Linux 三组和 Intel macOS 成功；Windows 的下载校验值正确，但许可证的 Git 检出换行导致源码比较失败。修正后使用标签原始字节复验，保留首次失败记录。
- 第二次[复验](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38468778163)仍发现 Windows 的 `git archive` 继承了换行转换。新增模拟 `core.autocrlf=true` 的回归测试，确认普通归档确实转换为 CRLF，而共享导出函数保留原始 LF，且不改写用户配置。

该发布提交的[实际五组 CI](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38423538515)均成功，包括 Intel macOS；[发布任务](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38467046597)重新运行 69 项测试后成功。

2026-10-14，修正后的[五组实际下载复验](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38469927622)全部成功：Linux / Python 3.10、3.12、3.14，Windows 与 macOS 15（Intel）/ Python 3.12。各平台下载的是同一个 10514 字节附件，SHA-256 与上面的记录一致；六个模块、入口、许可证，以及全部独立命令检查均通过。对应[验证实现提交的源码 CI](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38469858706)也通过五组环境的 70 项测试；Windows 按能力跳过不支持的 FIFO 测试。此结果不包含 Apple Silicon。

The downloaded v0.3.0 assets passed local verification on Linux / Python 3.12.14. Negative checks rejected a wrong checksum and changed module bytes before execution. The final linked **five-environment download run** also succeeded on Linux / Python 3.10, 3.12, 3.14 and Windows / Intel macOS / Python 3.12: the same 10514-byte asset and checksum, tagged module/entry-point/license bytes, and isolated CLI probes all passed. The verifier implementation's five-environment source CI passed its 70 tests, with Windows skipping unsupported FIFO creation. Apple Silicon was not tested.

## v0.2.1 下载附件复验记录 — 2026-10-13

在 Linux / Python 3.12.14 实际下载 v0.2.1 的两个 Release 附件并验证：

- 归档为 9841 字节，SHA-256 为 `20aaaa2e9fdd6ec80206de323b54dcd7116f2c3cac9f0d128fcaa0efc8f6cd47`，与下载的校验文件和 GitHub 附件摘要一致。
- 归档内全部 `offline_devkit/*.py` 的字节与发布提交 `aa10216c29d6a3158d82842d708d5c53954c71cb` 一致。
- 在源码目录外用 `python -I` 运行实际附件：0 / 1 个 UTF-8 BOM 的 JSON 成功，2 / 3 个 BOM 返回 2 且无标准输出；`1E-400` 原文保留；含 `NaN` 的 JSONL 返回 2。

This verification used the downloaded v0.2.1 assets on Linux / Python 3.12.14, rather than a locally rebuilt archive. It confirmed the checksum, module bytes, isolated execution, repeated-BOM rejection, numeric token retention, and JSONL error status. It does not add a fresh Windows or macOS download test.

对应的[发布任务](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38347789821)与[发布提交五组 CI](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38347585542)均已实际查看，结果成功。将来的版本应重新核对附件和对应提交的运行结果。
