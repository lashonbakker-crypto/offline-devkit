# 把 JSONL 校验接到 Bash / PowerShell 管道

[English](04-jsonl-pipelines.en.md) · [JSONL 规则](03-jsonl.md) · [命令手册](usage.md)

一个程序生成记录，另一个程序立即检查它，这就是这里的管道。`|` 把左边的标准输出送到右边的标准输入，省去先保存数据文件的步骤。错误说明走标准错误，不混入 JSONL。

本页的示例都从仓库根目录运行，要求 Python 3.10+。Bash 示例适用于 Linux / macOS；PowerShell 示例要求 `pwsh`（PowerShell 7），没有声称在 Windows PowerShell 5.1 中验证过。

## 先看数据和结果

[examples/produce_jsonl.py](../examples/produce_jsonl.py) 是可以公开分享的合成生成器。默认输出四行 UTF-8 数据，没有 BOM：

```jsonl
{"id":1,"message":"Hello"}
{"id":2,"城市":"南京 café"}
{"id":3,"score":1E-400}
null
```

`--invalid` 把第 2 行改成两个相同的键：一个写成 `城市`，另一个写成 Unicode 转义 `\u57ce\u5e02`，JSON 解码后相同。`--fail` 只输出前两行，然后向标准错误写入说明，以退出码 3 停止。

| 情况 | 检查行数 | 有效 / 无效 | 生成器退出码 | 校验器退出码 | 整体脚本退出码 |
| --- | --- | --- | --- | --- | --- |
| `valid` | 4 | 4 / 0 | 0 | 0 | 0 |
| `invalid` | 4 | 3 / 1 | 0 | 2 | 2 |
| `producer-failure` | 2 | 2 / 0 | 3 | 0 | 3 |

三种报告的 `complete` 都是 `true`：校验器都读到了管道的末尾。第三种情况下，生成器原本要输出四条，却只输出两条。校验器无法知道生成器的计划，因此不能用 `complete=true` 代替生成器的退出状态，也不能据此断言业务数据齐全。

## Bash：立即保存两个退出码

先运行现成脚本：

```bash
bash scripts/check_jsonl_pipeline.sh valid
bash scripts/check_jsonl_pipeline.sh invalid
bash scripts/check_jsonl_pipeline.sh producer-failure
```

以上分别退出 0、2、3。每条命令会在标准输出打印 JSON 报告，在标准错误打印 `producer_exit=... validator_exit=...`。若只想查看有效输入的基本管道，也可以运行：

```bash
python3 examples/produce_jsonl.py | python3 -m offline_devkit jsonl --json
```

[完整 Bash 脚本](../scripts/check_jsonl_pipeline.sh) 的关键步骤是：

```bash
"$devkit_python" examples/produce_jsonl.py "${producer_args[@]}" |
    "$devkit_python" -m offline_devkit jsonl --json
pipeline_codes=("${PIPESTATUS[@]}")
```

`PIPESTATUS` 保存刚才管道每个程序的状态：数组第 0 项是生成器，第 1 项是校验器。必须在管道之后**立即**保存；即使先执行一次打印命令，也会把这个数组改掉。普通 `$?` 只提供一个汇总状态，不能告诉你两端各自的结果。

脚本打开 `pipefail`，并在自己的进程里关闭 `errexit`，以便先检查预期的非零状态。只要生成器失败，就返回生成器状态；否则返回校验器状态。需要从父脚本继续传播结果时，紧接着保存 `$?`，最后 `exit "$status"`。父脚本启用了 `set -e` 时，预期失败的示例应放在条件分支中运行。

Python 命令默认是 `python3`，可用 `DEVKIT_PYTHON` 指定虚拟环境里的解释器；两端必须使用同一个 Python 环境。

## PowerShell 7：明确 UTF-8，并保存生成器状态

```powershell
pwsh -NoProfile -File scripts/check_jsonl_pipeline.ps1 -Mode valid
pwsh -NoProfile -File scripts/check_jsonl_pipeline.ps1 -Mode invalid
pwsh -NoProfile -File scripts/check_jsonl_pipeline.ps1 -Mode producer-failure
```

以上也分别退出 0、2、3。默认调用 `python`；可通过 `-Python` 参数指定解释器完整路径。当前 PowerShell 接收到子脚本结果后，可以立即读取 `$LASTEXITCODE`。

[完整 PowerShell 脚本](../scripts/check_jsonl_pipeline.ps1) 显式使用不带 BOM 的 UTF-8：

```powershell
$devkitUtf8 = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = $devkitUtf8
[Console]::OutputEncoding = $devkitUtf8
[Console]::InputEncoding = $devkitUtf8
```

`$OutputEncoding` 控制 PowerShell 把文本发送给原生程序时的编码，控制台编码用于原生输出与输入的衔接。示例通过脚本块保存左边的退出码：

```powershell
& {
    & $Python examples/produce_jsonl.py @producerArguments
    $script:devkitProducerExit = $LASTEXITCODE
} | & $Python -m offline_devkit jsonl --json
$devkitValidatorExit = $LASTEXITCODE
```

脚本块输出的是 JSONL 文本。赋值语句不会向管道输出退出码。这里的 `&` 是调用操作符，`@producerArguments` 把参数数组传给生成器；`$script:` 使退出码在外围脚本中可见。管道结束后立即保存校验器状态，再决定脚本最终返回什么。

脚本对预期的原生程序非零退出码关闭自动错误提升，并在 `finally` 中恢复原来的编码设置。它在单独的 `pwsh` 进程中运行，不依赖用户的 PowerShell profile，也不使用 `Get-Content` / `Out-File` 的默认编码来传递数据。不要把 Bash 的 `$?` 或 `PIPESTATUS` 写法直接搬到 PowerShell。

## 怎样确认这些示例真的可用

```bash
python scripts/verify_jsonl_pipelines.py --shell bash
```

```powershell
python scripts/verify_jsonl_pipelines.py --shell powershell
```

验证程序使用实际安装的 `bash` 或 `pwsh`，不是模拟 shell。没有对应程序时会明确失败。它检查三种情况的进程退出码、两端状态、行数、完整读取标志、第 2 行中文重复键错误，以及所有示例文件的 SHA-256 是否保持不变。中文键同时检验管道有没有把 UTF-8 文字改坏。

本地已在 Linux / Python 3.12.14 / Bash 5.2.21 运行并通过。CI 的 Linux / macOS 执行 Bash 版本，Windows 执行 PowerShell 版本；每次输出实际 shell 与 Python 版本。远程结果请查看对应提交的 [Actions](https://github.com/lashonbakker-crypto/offline-devkit/actions)，不要把一台机器的结果当作所有平台的保证。

## 读完应该能解释什么

1. 能用自己的话说明标准输出、标准错误、标准输入和 `|` 的关系。
2. 能预测表中三种退出码，解释为什么生成器失败时校验器仍可能退出 0。
3. 能指出 Bash 和 PowerShell 分别在哪里保存生成器 / 校验器状态。
4. 能说明 UTF-8、BOM、物理行号各负责什么，以及 `complete=true` 的确切含义。

建议先运行 `invalid`，确认错误在第 2 行；再运行 `producer-failure`，观察有效记录的报告和整体失败可以同时出现。理解后再读 [jsonl_tools.py](../offline_devkit/jsonl_tools.py) 的逐行读取逻辑与 [cli.py](../offline_devkit/cli.py) 的退出码处理。

官方参考：[Bash 管道](https://www.gnu.org/software/bash/manual/html_node/Pipelines.html)、[Bash PIPESTATUS](https://www.gnu.org/software/bash/manual/html_node/Bash-Variables.html)、[PowerShell 编码变量](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables)、[PowerShell LASTEXITCODE](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_automatic_variables)。
