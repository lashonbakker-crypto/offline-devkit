# 技术笔记 01：为什么格式化 JSON 也可能改变数字

JSON 中的数字是十进制文本。Python 的 `float` 通常使用二进制浮点表示，不能精确表示所有十进制小数。因此“读入再写出”可能产生变化。

## 亲自复现

在 Python 交互环境中运行：

```python
import json

source = '{"value":0.123456789012345678901,"tiny":1E-400}'
data = json.loads(source)
print(json.dumps(data))
```

你通常会看到长小数变短，`1E-400` 变成 `0.0`。这适用于本项目验证过的常规 Python 3.12 运行时；不要依赖浮点输出的具体尾数。

如果你的任务只是调整缩进，那么数字改变就不是你想要的行为。

## 本项目怎样处理

`json.loads` 提供转换回调，回调拿到的是原始数字文本。例如：

```python
class Number(str):
    pass

value = json.loads("[0.123456789012345678901,1E-400]", parse_float=Number)
assert value[0] == "0.123456789012345678901"
assert value[1] == "1E-400"
```

真正实现同时设置 `parse_int`，所以连大整数、`-0` 和指数写法也保留。格式化器把已经由解析器验证的 Number 直接作为数字写回，而不是作为带引号的字符串输出。

用现成示例验证：

```bash
python -m offline_devkit json examples/config.json --compact
```

## 重复键的另一个陷阱

Python 默认把 `{"limit":10,"limit":20}` 转成字典后只保留后一项。其他系统可能采取不同策略。本工具在键值对仍完整时拒绝重复，避免读者误解文件实际包含的设置。

`{"a":1,"\u0061":2}` 也会被拒绝，因为两个键解码后都是 `a`。

## 什么情况下选其他方案

需要计算而非格式化时，可以考虑 `decimal.Decimal` 并明确序列化规则；处理超大 JSON 或 JSON Lines 时，需要其他工具或流式实现。当前工具面向 16 MiB 以内的配置文件和样例。

参考：[Python json 官方文档](https://docs.python.org/3/library/json.html)。返回 [实现原理](how-it-works.md)。
