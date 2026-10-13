# 学习来源与核查记录

初版接口核查日期：2026-10-11；JSONL、单文件包与公开展示文档核查日期：2026-10-13。代码、演示数据和文章为本项目原创；这些是实现与学习时参照的原始文档，没有直接复制第三方实现。

| 官方来源 | 用于核查 |
| --- | --- |
| [Python json](https://docs.python.org/3/library/json.html) | 数字回调、重复键钩子、默认非标准数字行为 |
| [Python hashlib](https://docs.python.org/3/library/hashlib.html) | SHA-256 与增量 `update` |
| [Python os](https://docs.python.org/3/library/os.html) | `scandir`、`stat`、文件描述符与分块读取 |
| [Python argparse](https://docs.python.org/3/library/argparse.html) | 子命令、参数类型与错误行为 |
| [Python unittest](https://docs.python.org/3/library/unittest.html) | 测试发现、临时数据与断言 |
| [JSON Lines](https://jsonlines.org/) | UTF-8、BOM、空白行、行结束符与最终换行规则 |
| [Python zipapp](https://docs.python.org/3.10/library/zipapp.html) | 仅用标准库构建单文件运行包 |
| [GitHub README](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes) | 用途、快速开始、反馈入口 |
| [GitHub topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics) | 可检索且与已实现功能相关的标签 |
| [GitHub actions/checkout](https://github.com/actions/checkout) | CI 检出；核查 v7 标签指向的提交 |
| [GitHub actions/setup-python](https://github.com/actions/setup-python) | CI Python 版本配置；核查 v7 标签指向的提交 |

CI 的 Action 使用完整提交 SHA 固定版本，并关闭检出凭据持久化。Dependabot 配置用于后续提出 GitHub Actions 更新 PR；是否实际运行取决于 GitHub 仓库服务状态与设置。

官方文档的默认页面会随新 Python 版本变化。项目最低支持 Python 3.10，没有使用后来加入的 `array_hook` 或 `hashlib.file_digest`。新增 API 时请重新检查最低版本。
