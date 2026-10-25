# 只要最大的十个文件，为什么要排全部文件

`sizes --top 10` 在收集元数据后，需要输出最大的十个文件。过去的实现先对全部文件排序，再截取前十个。当前 `main` 改用标准库 `heapq.nsmallest`，比较键仍然是 `(-size, relative_path)`：文件越大，负数越小；大小相同时，路径按字典序排列。

在 `top` 很小、文件很多时，选择过程只需要维护少量候选，减少报告生成阶段的临时分配。目录汇总、总逻辑字节数、错误状态和 JSON 字段保持一致。它仍然收集全部文件元数据，完整扫描的内存用量仍随文件数量增长；这不是全流程常数内存的扫描器。

## 本轮实际测量

2026-10-25，Linux / Python 3.12.14。输入为已经放入内存的合成 `FileRecord`，64 个一级目录，文件大小为 `(index * 7919) % 10007`，包含大量大小相同的记录。`top=10`；预热一次，耗时取五次调用的中位数。峰值分配在单独一次调用中用 `tracemalloc` 测量，避免把追踪开销混进计时。

基线为提交 [`2ad842b`](https://github.com/lashonbakker-crypto/offline-devkit/commit/2ad842be8e8753cb7002e5af76649bd7ec2d50bc) 的完整排序实现。表内是**整次 `size_report` 调用**，包括目录汇总、最大文件选择和报告构造，未包含目录扫描、文件内容读取、输入元数据的分配和 CLI 启动。

| 元数据条数 | 完整排序耗时中位数 | 当前实现耗时中位数 | 完整排序峰值追踪分配 | 当前实现峰值追踪分配 |
| --- | --- | --- | --- | --- |
| 1,000 | 0.511 ms | 0.399 ms | 131,081 B | 28,089 B |
| 10,000 | 5.937 ms | 3.886 ms | 1,138,921 B | 28,089 B |
| 100,000 | 133.310 ms | 47.807 ms | 11,218,985 B | 30,137 B |

三种规模的完整报告 SHA-256 在修改前后完全一致，包含一级目录统计、最大文件列表和元数据。100,000 条时的摘要为 `460467ab35e933ba822bfbf661d615c854859b5900af880e9716d68a2ae2bee8`。这验证了本次确定性样本的报告一致性；回归测试另外覆盖截断位置的同大小文件、`top=1`、`top` 等于或大于文件数，以及全部文件的总量不被 `top` 截断。

这里的峰值是**追踪开始后本次函数调用分配的 Python 内存**，不是进程 RSS，也不包括已分配的全部 `FileRecord`。数字不能外推为“扫描十万个真实文件只占 30 KB”。耗时受机器、Python 版本和运行负载影响，不作为 CI 性能阈值。

## 复现当前实现

从源码仓库运行，脚本不扫描真实目录，也不创建十万个文件：

```bash
python scripts/benchmark_size_report.py --counts 1000 10000 100000 --top 10 --repeats 5
```

输出 JSON，含各次 `samples_seconds`、`median_seconds`、`peak_traced_bytes` 和完整报告的 `report_sha256`。退出码 0 表示结果与完整排序参考一致，重复运行的报告一致；性能数字不要求与上表完全相同。也可以用 `--top 1`、`--top 1000` 比较选择规模的影响；`top` 变大时，不保证选择算法更快。

若需要在同一台机器重测旧实现，使用一个新的工作目录，命令适用于 Bash 和 PowerShell：

```bash
git worktree add --detach ../offline-devkit-before 2ad842be8e8753cb7002e5af76649bd7ec2d50bc
python scripts/benchmark_size_report.py --source-root ../offline-devkit-before --counts 1000 10000 100000 --top 10 --repeats 5
```

基准脚本来自当前源码，导入的 `FileRecord`、`Scan` 和 `size_report` 来自选定的旧工作目录。用前一条命令重测当前实现，对照各规模的摘要与计时。脚本不会写入两个目录，`git worktree add` 只用于准备旧版本。

## 五分钟源码练习

先运行 `python -m offline_devkit sizes examples/files --top 1 --json`。应看到 `files_scanned=3`、`total_bytes=187`，最大文件列表只有 `unique.txt`（75 字节），目录汇总仍覆盖全部三个文件。

然后阅读 [files.py](../offline_devkit/files.py) 的 `size_report`，找到比较键 `(-item.size, item.relative_path)`。尝试解释：为什么负号能让更大的文件排在前面；两个文件一样大时，为什么还要比较路径。最后运行一次基准，观察“返回列表只要十条”和“输入仍需读取全部元数据”的区别。

原始 API 行为参考 [Python 3.10 heapq 文档](https://docs.python.org/3.10/library/heapq.html#heapq.nsmallest)。下一步可以独立测量真实目录扫描的耗时与元数据占用，不能用本表替代磁盘 I/O 基准。
