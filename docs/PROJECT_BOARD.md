# GitHub Project 开发任务看板

建议 Project 名称：**基于深度强化学习的综合能源运行仿真系统**。

字段建议：Status（Backlog / Ready / In progress / Review / Done）、Priority（P0/P1/P2）、Milestone（M0–M3）、Owner、Acceptance。以下是可复制为 Issues 的任务；提供的文档或代码不等于任务已在真实园区完成。

GitHub Projects 可以将 Issues 和 Pull Requests 组织为表格、看板或路线图；配置方式见 [GitHub Projects 官方说明](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)。本文件和 `project_tasks.csv` 是任务种子，不会自动创建远端看板。

| 编号 | 任务 | 优先级 | 里程碑 | 当前状态 | 验收交付 |
|---|---|---|---|---|---|
| T01 | 确认现场设备和费用边界 | P0 | M0 | Ready | 设备表、计费表、控制边界获负责人确认 |
| T02 | 复现示例与手算验证 | P0 | M0 | Ready | 本地测试记录、规则调度输出与环境版本 |
| T03 | 真实数据接入与时间隔离 | P0 | M0 | Backlog | CSV、字段字典、质量报告、时间划分表 |
| T04 | 校准设备模型与容量约束 | P0 | M0 | Backlog | 参数依据、至少三个独立核验工况 |
| T05 | 确认观测、动作和信息可获得性 | P0 | M1 | Backlog | 决策时序表，排除未来实测值泄漏 |
| T06 | 完成 PPO/SAC 本地短训练 | P0 | M1 | Ready | 两算法模型可保存加载，测试日全部输出 |
| T07 | 正式调参与多种子比较 | P0 | M1 | Backlog | 至少 3 个种子、固定测试集、费用与可行性表 |
| T08 | 增加 MILP 优化基准 | P0 | M2 | Backlog | 统一物理模型和期末目标、求解状态与时间 |
| T09 | 增加因果预测输入和 MPC | P1 | M2 | Backlog | 预测发布时间可审计，滚动控制对照 |
| T10 | 增加多算法及多种子图表 | P1 | M2 | Backlog | 典型日、费用、违约和统计波动图 |
| T11 | 联合约束处理与异常回退 | P1 | M2 | Backlog | 容量不足、输入异常和设备故障的处理记录 |
| T12 | 接入电网潮流与必要网络约束 | P2 | M3 | Backlog | 节点电压、支路容量与电力平衡校验 |
| T13 | 接口服务与可视化前端 | P2 | M3 | Backlog | 数据导入、策略对比、结果导出及错误展示 |
| T14 | 硬件在环与历史回放 | P2 | M3 | Backlog | 时延、输入扰动、执行偏差及回退记录 |
| T15 | 整理发布版和复现说明 | P1 | M3 | Backlog | 版本、数据说明、许可证决定及可执行复现步骤 |

建议依赖顺序为 T01–T04 完成后进入真实模型适配；T05、T06 完成后再做 T07；T08、T09 提供正式对照；T11、T12 与现场边界确认后才进入 T14。具体工期由数据到位和设备复杂度决定，不预设为已经承诺的项目期限。

每个 Issue 使用仓库内 `.github/ISSUE_TEMPLATE/engineering_task.md`，必须填输入、输出、前置任务和可运行验收命令。`project_tasks.csv` 可用于整理和批量脚本开发，不承诺 GitHub 网页支持直接导入该 CSV。
