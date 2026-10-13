# 技术笔记 02：名字相同、大小相同，都不代表内容相同

“重复文件”需要先说清楚：我们找的是不同文件里的相同内容，而不是相同文件名，也不是多条路径指向同一个 inode。

## 四种情况

| 情况 | 例子 | 本项目如何处理 |
| --- | --- | --- |
| 名字相同，内容不同 | 两个目录里的 `notes.txt` | 名字不参与重复判断 |
| 大小相同，内容不同 | `same` 与 `diff` 都是 4 字节 | 进入候选，哈希不同，分组不同 |
| 名字不同，内容相同 | 示例里的 `note.txt` 与 `note-copy.txt` | 同长度、同 SHA-256，生成一组；可选逐字节复核 |
| 两个硬链接 | 两条路径指向同设备的同 inode | 只参与一次哈希，不夸大冗余估计 |

## 为什么先按长度分组

读取全部内容很耗时，而文件长度从元数据就能获得。不同长度可以直接排除。相同长度只能说明“可能重复”，必须进一步比较内容。

## 为什么分块读

一次读取大文件会占用大量内存。`hashlib.sha256().update(chunk)` 可以逐块更新摘要。本项目每块最多 1 MiB，单个哈希缓冲不随文件长度增长，但目录元数据仍需要 O(n) 内存。

## 为什么不自动删除

重复内容在不同目录里可能有不同用途：课程备份、部署包、版本归档。程序无法从哈希推断哪份应该保留。当前仅报告，把处理选择交给使用者。

`size × (数量 − 1)` 只是逻辑冗余估计。稀疏文件、压缩、写时复制、硬链接等机制可能改变真实磁盘占用，不能把这个数字直接当作“清理后能省多少空间”。

## 亲自运行

```bash
python -m offline_devkit dupes examples/files --json
python -m offline_devkit dupes examples/files --verify-bytes --json
python -m unittest discover -s tests -p test_files.py -v
```

第二条命令会多读一次同哈希候选。观察 JSON 中 `verify_bytes` 为 `true`、`byte_comparisons` 为 `1`，重复组的 `verified_by` 为 `bytes`。测试中还包含模拟哈希碰撞、跨块比较、硬链接、链接目录和文件变化。这些检查对应真实误判风险。

参考：[Python hashlib](https://docs.python.org/3/library/hashlib.html)、[Python os](https://docs.python.org/3/library/os.html)。返回 [实现原理](how-it-works.md)。
