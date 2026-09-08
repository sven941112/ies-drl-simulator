# GitHub 发布与仓库信息

## 1. 建议填写内容

| 字段 | 内容 |
|---|---|
| Repository name | `ies-drl-simulator` |
| 中文项目名 | 基于深度强化学习的综合能源运行仿真系统 |
| Description | Deep reinforcement learning for electricity-heat-cooling-gas dispatch, with a physical simulator, PPO/SAC baselines and engineering guides. |
| Topics | `integrated-energy-system`、`reinforcement-learning`、`energy-management`、`ppo`、`sac`、`gymnasium`、`energy-storage` |
| 首页 | 根目录 `README.md` |
| Project 看板 | `docs/PROJECT_BOARD.md` 中的任务结构 |

这些信息是发布草案，本项目包不代表已经创建远端仓库、Issue 或 Project。

## 2. 上传方式

先在 GitHub 创建空仓库，选择正确的所属账号与可见性。因本地已经包含 README 和 `.gitignore`，新建远端仓库时不再预填这两项。创建步骤参考 [GitHub 新建仓库说明](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository)。

在解压后的 `ies-drl-simulator` 目录中执行：

```bash
git init
git add .
git commit -m "Initial integrated energy DRL simulator and engineering guide"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ies-drl-simulator.git
git push -u origin main
```

把 `YOUR_USERNAME` 换成实际账号。使用自己的 GitHub 身份完成认证，不把令牌写入脚本或仓库。该新仓库命令不适用于覆盖一个已有历史的仓库。

也可以把解压后的文件通过 GitHub 文件上传功能提交；需要上传文件本身，而不是只上传 ZIP。CLI 方式更容易完整保留 `.github` 下的工作流和模板。

## 3. 建立工程任务

按 `PROJECT_BOARD.md` 逐项建立 Issues，并关联到 Project。先推进模型和数据任务，再做正式训练和算法扩展。不要把本次短训练验证标为已经完成了正式性能验收。

## 4. 发布前填写

- 维护者与联系渠道：由项目负责人填写，避免公开不必要的个人联系方式。
- 许可证：由项目负责人决定；本包未擅自指定第三方复用授权。
- 数据：示例合成数据可保留其生成脚本和说明；真实业务数据采用另行确定的访问方式。
- 版本记录：当前为 v0.1 原型；正式实验完成后补充结果和复现条件。

已提供 GitHub Actions 文件，但其远端权限、执行结果与运行额度以实际仓库设置为准。本地通过不表示远端 CI 已执行。
