# 发布与下载包

仓库已公开，日常改动基于远程 `main`，不要重新初始化或用早期源码包覆盖现有历史。当前源码版本为 0.2.0。

## 单文件运行包

```bash
python -m unittest discover -s tests -v
python scripts/build_zipapp.py
python dist/offline-devkit.pyz --version
python dist/offline-devkit.pyz jsonl examples/records.jsonl --json
```

构建只依赖 Python 标准库，不需要下载第三方包。`dist/` 是生成目录，不提交到 Git。发布时将 `offline-devkit.pyz` 和 SHA-256 校验文件附加到 GitHub Release；源码通过该标签的标准 ZIP / tar.gz 提供。先检查该提交的实际五组 CI 结果，再发布对应版本。

生成包包含本项目源码、入口与 MIT 许可证；需要 Python 3.10+。测试会在源码目录外确认归档能够独立导入，并正确传播失败退出码。

## 首次创建记录

建议名称：`offline-devkit`。建议公开，因为仓库内容是原创工具、虚构示例和技术文章。建议描述：

> Zero-dependency local Python tools: lossless JSON formatting, duplicate finder, and directory sizes. 中文教程与可读源码。

建议 Topics：`python`、`cli`、`developer-tools`、`json`、`duplicate-files`、`offline`、`chinese`。

这些是建议元数据，只有实际创建并设置后才会出现在 GitHub。

## 网页创建

1. 用 `lashonbakker-crypto` 账号打开 GitHub 的 New repository。
2. 名称填写 `offline-devkit`，选择 Public，填写上述描述。
3. 上传现有源码时不要额外初始化 README 或许可证，以免产生重复初始历史。
4. 创建后在本地仓库配置远端并 push；也可以上传完整文件树，注意包含 `.github` 下的配置。

## 可选：GitHub CLI

从官方来源安装 `gh`，在自己的终端登录，不要把令牌发到聊天里。先确认当前账号：

```bash
gh auth login
gh api user --jq .login
```

结果应为 `lashonbakker-crypto`。进入解压后的 `offline-devkit` 目录，确认只包含本项目文件：

```bash
git init -b main
git add .
git commit -m "feat: add offline developer toolkit with tests and guides"
gh repo create lashonbakker-crypto/offline-devkit --public --source=. --remote=origin --push --description "Zero-dependency local Python tools: lossless JSON formatting, duplicate finder, and directory sizes."
```

Git 尚未配置作者时，请先使用自己的署名配置 `user.name` 和 GitHub 提供的隐私邮箱。源码 ZIP 不包含 `.git` 历史，所以需要上面的本地初始化步骤。

## 创建后完善

设置上面建议的 Topics，在 Actions 检查首轮测试。可以在仓库支持时启用私密漏洞报告。确认内容与 CI 后，再建立 `v0.1.0` 标签和 Release，不提前宣称跨平台验证已通过。
