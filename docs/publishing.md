# 发布与下载包

仓库已公开，日常改动基于远程 `main`，不要重新初始化或用早期源码包覆盖现有历史。当前源码版本为 0.3.0，下载包包含 `dupes --verify-bytes`。

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

## 下载附件复验记录 — 2026-10-13

在 Linux / Python 3.12.14 实际下载 v0.2.1 的两个 Release 附件并验证：

- 归档为 9841 字节，SHA-256 为 `20aaaa2e9fdd6ec80206de323b54dcd7116f2c3cac9f0d128fcaa0efc8f6cd47`，与下载的校验文件和 GitHub 附件摘要一致。
- 归档内全部 `offline_devkit/*.py` 的字节与发布提交 `aa10216c29d6a3158d82842d708d5c53954c71cb` 一致。
- 在源码目录外用 `python -I` 运行实际附件：0 / 1 个 UTF-8 BOM 的 JSON 成功，2 / 3 个 BOM 返回 2 且无标准输出；`1E-400` 原文保留；含 `NaN` 的 JSONL 返回 2。

This verification used the downloaded v0.2.1 assets on Linux / Python 3.12.14, rather than a locally rebuilt archive. It confirmed the checksum, module bytes, isolated execution, repeated-BOM rejection, numeric token retention, and JSONL error status. It does not add a fresh Windows or macOS download test.

对应的[发布任务](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38347789821)与[发布提交五组 CI](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38347585542)均已实际查看，结果成功。将来的版本应重新核对附件和对应提交的运行结果。
