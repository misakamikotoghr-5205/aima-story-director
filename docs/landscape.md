# 已有编排工具、许可边界与改进

核查日期：2026-11-04。已阅读下列官方仓库 README、LICENSE 和对应编排文档；没有运行外部机器人代码，也没有设备访问或真机操作。

## 已经存在什么

机器人动作时间线、并行通道、条件行为、日志与回放都不是新概念。AIMA Story Director 是窄用途的离线话术/语义动作排练工具，不是机器人 SDK，也没有声称比成熟机器人行为平台更完整。

| 对照 | 公开可验证能力 | 我们的差距 | 值得保留或借鉴的方向 |
| --- | --- | --- | --- |
| [Boston Dynamics Spot SDK README](https://github.com/boston-dynamics/spot-sdk/blob/04537ddafe0641d1751af3eb9e76cb785fc18594/README.md)、[Choreography Service](https://github.com/boston-dynamics/spot-sdk/blob/04537ddafe0641d1751af3eb9e76cb785fc18594/docs/concepts/choreography/choreography_service.md) | 按时间片编排动作和通道，校验动作的进入/退出条件，提供上传、执行与状态接口 | 本项目没有真实动作资源、运动学、完成回执或设备控制；语义 `wave` 不是 Spot 或智元的动作 ID | 借鉴在执行前验证编排与明确轨道的设计；保留无硬件依赖的中文话术审稿与可重放 fixture |
| [BehaviorTree.CPP README](https://github.com/BehaviorTree/BehaviorTree.CPP/blob/a9d6e5637f4a4fcd29fcd16b8db049de7c42006b/README.md) | 响应式行为树、并发异步动作、类型化数据流、记录/回放/分析状态变化，另有 Groot 编辑器 | 我们只有无环场景和固定事件快照，不具备持续 tick、实时传感器、动作取消或行为树编辑器 | 借鉴把决策过程作为可观察和可检查对象；新增批量分支排练，而不是伪装成完整行为树运行时 |

## 版本与许可证

| 来源 | 核查 commit / 许可 | 本次采用方式 |
| --- | --- | --- |
| `boston-dynamics/spot-sdk` | `04537ddafe0641d1751af3eb9e76cb785fc18594`；[Boston Dynamics SDK License 20191101-BDSDK-SL](https://github.com/boston-dynamics/spot-sdk/blob/04537ddafe0641d1751af3eb9e76cb785fc18594/LICENSE) | 仅参考公开编排概念；**不是通用 MIT/Apache 许可**。许可限制用于其他硬件，不能把其 SDK 代码直接用于智元设备。本次未复制、安装或导入 |
| `BehaviorTree/BehaviorTree.CPP` | `a9d6e5637f4a4fcd29fcd16b8db049de7c42006b`；[MIT LICENSE](https://github.com/BehaviorTree/BehaviorTree.CPP/blob/a9d6e5637f4a4fcd29fcd16b8db049de7c42006b/LICENSE) | 仅借鉴可观察决策与回放的设计；没有复制源码、XML、图形或加入 C++/ROS 依赖 |

新代码在 `aima_director/rehearsal.py`，为针对现有 JSON DSL 独立编写的约束探索与 case 导出实现。本项目不是上述仓库的 fork，不把通用概念称为独创。没有引入需再分发的第三方代码或素材；若以后选择复用，应保留对应版权与许可，而不是统一改成 MIT。

## 已实装：可行分支排练与覆盖报告

原来每次 `simulate` 只能跑用户自行编写的一份事件文件。即使图结构可达，也可能因为前后条件要求同一个固定事件同时为 true/false，导致某条路线实际上永远不能走到。

新增 `rehearse`：

1. 在已校验的无环场景图上探索 then/else，沿路线积累每个事件的等值与不等值约束。
2. 排除与先前等值条件冲突的前缀。为可行决策路径生成最小事件快照；未指定事件保持缺失。
3. 另外生成代表性的“事件存在但不匹配”用例。布尔值两种都被排除时，仍允许事件缺失走 else，不把缺失等同于 false。
4. 使用原有 `simulate` 实际执行每个生成 fixture，核对预期决策并保存可验哈希链的时间线、SVG、台词与执行准备清单。
5. 分支表列出 `covered`、`infeasible` 或 `unexplored`，链接到可重放 `events.json`。图上可达但条件不可满足的场景会出现在未到达列表中。

算法并未复制 Spot 或 BehaviorTree.CPP 的实现；相等比较的固定快照约束可以用少量标准库代码实现，没有必要引入硬件 SDK 或整个行为树框架。

## 边界与验证

默认 64 条可行决策路径、128 个 case、4,096 次场景展开、50,000 条模拟指令，均有硬上限。若上限被触及，报告会是 `complete=false`、CLI 退出 `3`，未探索结果不会被误报成不可能。完整性只针对当前无环 DSL 与固定快照：不是所有传感器事件流、所有字符串/数字、真实时序或硬件安全的穷举证明。

新增 8 项测试覆盖三个现有示例、相关条件矛盾、缺失/显式 false、数字/字符串反例、then/else 同目标、各种预算上限、导出重放与完整性、CLI 退出。连同原有校验与 dry-run 拒绝硬件测试共 23 项。运行：

```bash
python3 scripts/check.py
python3 -m aima_director rehearse examples/distance-reminder.json --out output/rehearsal
```

本次没有添加硬件模式、设备地址、传感器输入或 SDK 控制。后续真实设备适配仍须依据确认的智元机型文档独立实现并实际验收。
