# 在 GitHub Actions 中检查 JSONL 数据

让提交到仓库的数据自动接受同一套 JSONL 检查：有效数据使 job 成功，重复键、坏记录、压缩截断或缺少文件使 job 失败。验证发生在 runner 本地，工具不上传数据。

## 复制两个文件

从本项目最新源码复制以下文件到**你自己的仓库**，保持目标路径：

| 本项目文件 | 你的仓库中的目标位置 |
| --- | --- |
| [check-jsonl.yml](../examples/github-actions/check-jsonl.yml) | `.github/workflows/check-jsonl.yml` |
| [check_jsonl.py](../examples/github-actions/check_jsonl.py) | `.github/scripts/check_jsonl.py` |

然后只改工作流中的这一条命令，把数据路径换成仓库内已经跟踪的文件；路径含空格时加引号：

```yaml
run: python .github/scripts/check_jsonl.py data/records.jsonl.gz --gzip
```

普通 JSONL 不带 `--gzip`：

```yaml
run: python .github/scripts/check_jsonl.py data/records.jsonl
```

示例检查**一个明确的文件**，不展开 glob、不扫描目录；路径不存在时失败。gzip 必须显式选择，扩展名不自动改变输入方式。复制这两个文件和你的数据变更后，提交或发起 PR 即可触发检查。

配方使用 Python 3.12，无需 pip；普通 `pull_request`、`push` 和手动触发均已配置。默认不加路径过滤，避免改数据路径时漏改过滤规则。工作流只有 `contents: read`，checkout 不持久化凭据，不需要额外密钥。job 最长 5 分钟。

## 它怎样决定成功或失败

| 输入 / 准备情况 | helper 退出码 | 报告与 job |
| --- | --- | --- |
| 完整且有效的 JSONL / gzip | 0 | JSON 报告 `complete=true`，job 成功 |
| 重复键或其他无效记录 | 2 | 报告错误行号，job 失败 |
| gzip 被截断或读取失败 | 2 | `complete=false`，job 失败；计数是部分结果 |
| 文件缺失、路径无法展开 / 解析、附件哈希不符或附件过大 | 2 | 错误写到 stderr，job 失败；不输出数据检查报告 |

helper 直接传播隔离执行的校验器状态和 JSON 输出。不要追加 `|| true` 或设置 `continue-on-error: true`，否则会改变这条失败规则。

最新源码中的 helper 会在准备工具前拒绝无法展开的家目录路径，以及输入路径解析中的循环链接，返回 2 和简短错误。已有配方请更新复制的 `check_jsonl.py`；仅重新下载相同的 v0.4.0 附件不会更新这个独立脚本。路径错误回归还会确认没有下载或执行归档。

**job 失败与禁止合并是两件事。** 如需把检查作为合并条件，应另在仓库规则中将该检查设为必需状态；本示例不修改仓库规则。手动触发要求工作流先存在于默认分支，首次 fork PR 也可能需要维护者批准运行；等待批准不表示数据验证失败。依据见 [GitHub 触发事件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch)及[路径过滤说明](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onpushpull_requestpull_request_targetpathspaths-ignore)。

## 固定工具版本与本地练习

helper 默认从固定公开 URL 下载已发布的 **v0.4.0** 单文件包，最多读取 1 MiB + 1 字节；超过 1 MiB 即拒绝。读取完成后与源码中固定的 SHA-256 比较，通过后才复制到私有临时目录，并用 `python -I` 执行。哈希为：

```text
349b3fdda2c55f37e2c422935ef63718f2950f65076fe0f45309ad4f0e44fc64
```

默认准备工具需要网络；**这不改变校验器本身离线运行的行为**。30 秒是网络阻塞超时，整个 job 受 5 分钟上限约束；它不等同于 CLI 已提供总解压量或 CPU 预算。固定哈希检查版本字节一致性，不是独立的发布者签名。升级版本时应同时核实并更新 `RELEASE_URL` 与 `RELEASE_SHA256`，重新验证示例。

用已下载的相同附件可以离线练习；将路径换成你现有、已按[发布说明](publishing.md)核对的附件：

```bash
python examples/github-actions/check_jsonl.py examples/records.jsonl --archive ../release-download/offline-devkit.pyz
```

应看到三条有效记录、`complete=true`，退出 0。把输入换成 `examples/invalid-records.jsonl`，应报告第 2 / 3 行错误并退出 2。`--archive` 同样强制核对固定哈希，不会关闭验证，也不会下载附件。输入内容不被改写。

## 实测完整配方

从本项目源码目录运行：

```bash
python scripts/verify_ci_recipe.py
```

脚本只下载并核验一次附件，在临时目录复制配方文件，执行 YAML 中实际的单行 `run` 命令，再依次验证普通 JSONL、转义重复键、截断 gzip、缺少输入、错误哈希的可执行假附件，以及过大的附件。应输出七条预期结果，最后显示：

```text
All seven consumer recipe cases passed; dataset hashes unchanged; untrusted code was not executed.
```

演练脚本退出 0，表示它确认五种失败情况按预期返回 2；不是把坏数据判为有效。数据集哈希保持不变，没有解压输出；错误哈希的假附件即使自身会返回 2，也必须在执行前被拒绝，哨兵文件不能出现。已有附件时可以追加 `--archive PATH`，整个演练无需网络。

本项目 CI 在 Linux 三个 Python 版本、Windows、Intel macOS 上运行这份脚本。它验证复制后的脚本和命令，不会自动给你的仓库添加工作流或合并规则；结果应以对应提交的实际 Actions 为准。

该检查只验证 JSON 语法、本项目严格规则和读取完整性，不检查业务字段、平台导入要求或记录数下限；空 JSONL 按零条有效记录处理。

## English

Copy the two recipe files to `.github/workflows/check-jsonl.yml` and `.github/scripts/check_jsonl.py` in your repository. Edit the single `run` line to point to an explicitly tracked dataset file. Keep `--gzip` for compressed input; remove it for plain JSONL. Quote paths containing spaces. No glob expansion or implicit decompression is performed; a missing input fails.

The workflow uses ordinary pull requests, pushes, and manual dispatch, with read-only contents permission and checkout credential persistence disabled. It requires Python 3.12, no pip, and no additional secrets. It intentionally has no path filter. Dispatch requires the workflow on the default branch; fork runs may need approval. A failed job does not automatically prevent merging: configure a required status check separately if desired.

The helper downloads the fixed v0.4.0 archive and checks its hardcoded SHA-256 before executing a private temporary copy with `python -I`. Preparation uses network access; `--archive PATH` uses existing bytes without network and still enforces the same checksum. Inputs are unchanged, stdout remains the validator's JSON, and its status propagates: 0 for complete valid input; 2 for invalid records, incomplete gzip, or preparation/input failures. Do not mask the exit with `|| true` or `continue-on-error`.

The latest source helper rejects unresolved home paths and input-path symlink loops before preparing the tool, with a short error and exit 2. Update your copied `check_jsonl.py` to get this fix; downloading the same v0.4.0 archive does not update the separate helper. Regression checks confirm that path failures neither download nor execute the archive.

Run `python scripts/verify_ci_recipe.py` to exercise seven copied-recipe cases, or append `--archive PATH` for an offline run. The success message means expected bad cases were rejected. Our CI executes this verifier on five environments; it does not install workflows in another repository. Limits: a 1 MiB tool download, 30-second network blocking timeout, and a 5-minute job timeout. These are not CLI decompression/CPU budgets or a publisher signature. Schema requirements and minimum record counts remain application policy; empty JSONL is accepted as zero records.
