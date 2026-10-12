<p align="center"><img src="assets/banner.svg" alt="Offline DevKit — local files, clear answers" width="100%"></p>

# Offline DevKit

[![Tests](https://github.com/lashonbakker-crypto/offline-devkit/actions/workflows/ci.yml/badge.svg)](https://github.com/lashonbakker-crypto/offline-devkit/actions/workflows/ci.yml)

**把日常开发里的小麻烦，变成可理解、可复用的本地工具。**

[English](README.en.md) · [快速开始](#一分钟上手) · [完整命令](docs/usage.md) · [源码讲解](docs/how-it-works.md) · [贡献指南](CONTRIBUTING.md)

一个用 Python 标准库实现的轻量命令行工具箱：严格检查并格式化 JSON、查找重复文件、统计目录大小。运行时零第三方依赖，文件内容留在本机。适合直接使用，也适合作为学习命令行、文件系统和自动测试的开源例子。

| 工具 | 解决什么问题 | 实现亮点 |
| --- | --- | --- |
| `json` | 配置文件难读、重复键、非标准数字 | 保留数字原文，拒绝重复键与 `NaN` / `Infinity` |
| `dupes` | 下载目录、资料备份里有重复内容 | 先按大小筛选，再分块计算 SHA-256；硬链接只算一次 |
| `sizes` | 想知道哪个子目录、哪些文件最大 | 汇总一级目录，输出最大文件与机器可读报告 |

**Python 3.10+ · Windows / macOS / Linux 的 CI 配置 · MIT**

## 一分钟上手

克隆仓库后进入项目目录。以下方式直接运行源码，无需安装包，也不需要联网：

```bash
git clone https://github.com/lashonbakker-crypto/offline-devkit.git
cd offline-devkit
python -m offline_devkit json examples/config.json
python -m offline_devkit dupes examples/files
python -m offline_devkit sizes examples/files --top 3
```

克隆需要网络，下载源码 ZIP 后解压也可以；进入目录后的三个工具命令不需要网络。

Windows 如果没有 `python` 命令，请用 `py -3`；macOS / Linux 可以用 `python3`。

附带的三个文本文件中，`note.txt` 和 `copies/note-copy.txt` 内容相同，`unique.txt` 内容不同。你应看到一组重复文件。检查配置示例时，长小数和 `1E-400` 会保持原样。

可选：安装到虚拟环境，使 `offline-devkit` 在其他目录也能使用：

```bash
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell：.\.venv\Scripts\Activate.ps1
python -m pip install .
offline-devkit --help
```

安装步骤可能需要下载构建工具 `setuptools`。安装完成后的工具运行，以及上面的源码运行方式，都不需要网络。目前没有承诺在 PyPI 发布，请从本仓库安装。

## 三个日常用法

### 检查 JSON，或生成可读的新文件

```bash
python -m offline_devkit json examples/config.json --check
python -m offline_devkit json examples/config.json --sort-keys > formatted.json
```

`--check` 成功时没有输出，适合脚本检查。输入必须是 UTF-8，允许 BOM，大小上限为 16 MiB。格式化保留数字字符序列，包括指数、大整数、长小数与 `-0`；字符串的转义方式和空白可能变化。

命令输出统一使用 UTF-8 和 LF 换行，包括 Windows 上的重定向输出。`--check` 与格式化的可处理嵌套深度可能不同，取决于 Python 的解码器和递归限制；超出能力时会报告错误。

### 找出重复文件，先看清楚再处理

```bash
python -m offline_devkit dupes ./Downloads --min-size 1024 --exclude "*.tmp"
python -m offline_devkit dupes ./Downloads --json > duplicates-report.json
```

工具只报告，**没有删除或修改文件的功能**。`redundant_bytes` 是冗余内容的逻辑字节估计，不代表真实可释放磁盘空间。报告中的第一条路径只是排序结果，不是建议保留的文件。

### 看目录大小，定位大文件

```bash
python -m offline_devkit sizes . --top 10
python -m offline_devkit sizes . --exclude "*.log" --json
```

默认跳过 `.git`、`.venv`、`venv`、`node_modules`、`__pycache__`、`.pytest_cache` 目录，以及符号链接和 Windows 重解析点。显式加 `--include-ignored` 可以纳入依赖与缓存目录；它仍然不会遍历链接。特殊文件（例如命名管道）不计入报告。

## 退出码

| 退出码 | 含义 |
| --- | --- |
| `0` | 完成，没有处理错误；普通重复文件报告发现重复仍返回 0 |
| `1` | 指定 `dupes --fail-if-found` 且发现重复组 |
| `2` | 参数或输入错误，或者扫描 / 读取不完整 |
| `130` | 用户中断 |

## 读代码与参与项目

| 入口 | 内容 |
| --- | --- |
| [命令手册](docs/usage.md) | 参数、输出字段、退出码、边界行为 |
| [实现原理](docs/how-it-works.md) | 为什么不能直接用浮点数格式化 JSON；如何避免误判重复文件 |
| [技术笔记 01](docs/01-json-numbers.md) | 用一个可以复现的例子理解 JSON 精度问题 |
| [技术笔记 02](docs/02-duplicates.md) | 文件大小、哈希、硬链接与目录扫描的区别 |
| [贡献指南](CONTRIBUTING.md) | 怎样报告问题、修改代码、运行测试 |
| [发布记录](CHANGELOG.md) | 当前版本及行为变动 |
| [路线图](ROADMAP.md) | 后续可以贡献的具体方向 |

核心代码在 [offline_devkit](offline_devkit/)，测试在 [tests](tests/)。

```bash
python -m unittest discover -s tests -v
```

本地验证环境为 Python 3.12 / Linux，40 项测试通过。发布前的[跨平台 CI](https://github.com/lashonbakker-crypto/offline-devkit/actions/runs/38272248834)已通过 Linux / Python 3.10、3.12、3.14，以及 Windows、macOS / Python 3.12 的行为测试、安装和命令检查。后续提交的状态以顶部徽章与 Actions 页面为准。

## 使用边界

- 在稳定、可信的本地目录运行。扫描不是文件系统快照，也不是对恶意并发修改的隔离边界；检测到文件变化会报告错误，但无法检测所有竞态。
- `sizes` 统计文件长度（逻辑大小），硬链接的每个路径都会计数；压缩、稀疏文件、写时复制、磁盘块占用不在本项目统计范围。
- SHA-256 相同是重复内容的实用判断依据；本工具没有逐字节复核，也不提供数学上零碰撞的证明。
- 输出报告包含文件路径，分享报告前请检查内容。程序不发起网络请求；保存标准输出由你的 shell 负责。
- 不要将格式化结果重定向回原输入文件，也不要把目录扫描报告写入正在扫描的目录。用新文件或目录外的路径。

## 许可与来源

代码、示例和文档为本项目原创，使用 [MIT License](LICENSE)。[学习来源](docs/references.md)列出 Python 与 GitHub 官方文档；没有复制第三方项目的实现。
