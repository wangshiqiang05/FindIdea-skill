# 🧠 FindIdea Skill

## 🔍 是什么？

FindIdea 是一个面向 AI Agent 的**跨领域迁移式研究 idea 挖掘技能**：把成熟领域中已被代码验证的机制，迁移到问题结构同构的目标领域，从选题一路落到可运行的代码基线。

**✨ 核心能力**

- 🧩 **结构同构六维映射**：从输入、输出、监督、瓶颈、推理、约束六个维度判定相似领域，不靠拍脑袋
- 📚 **顶刊顶会检索**：覆盖 12 个子领域的高口碑会议与期刊，内置检索式与滚雪球方法
- ✅ **开源真实性审计**：自动识别真开源 / 假开源，API 限额时自动降级为网页抓取
- 💡 **一篇论文一个 idea**：结构化卡片含迁移映射表、PoC 阈值与风险，全程可追溯
- 🔎 **新颖性交叉验证**：多视角审查 + 多渠道检索 + 多模型交叉，术语扩展防"异名同物"
- 🛠️ **原代码分层改造**：在真开源仓库上逐层适配，核心机制不动
- 📒 **全流程台账**：JSONL 记录每个环节的证据与状态，支持断点续做；脚本零第三方依赖

**🔄 工作流**

| 阶段 | 内容 |
|---|---|
| 0. 📋 | 确认输入与约束，初始化台账 |
| 1. 🎯 | 锚定目标领域，梳理核心瓶颈 |
| 2. 🧭 | 发现结构同构的相似源领域 |
| 3. 📚 | 检索顶刊 / 顶会近年论文 |
| 4. ✅ | 逐篇核验真开源 / 假开源 |
| 5. 💡 | 每篇真开源论文生成一个迁移 idea |
| 6. 🔎 | 多渠道、多模型交叉验证新颖性 |
| 7. 🛠️ | 在原代码上分层改造出本领域基线 |

## 🚀 怎么安装和使用

### ⬇️ 安装

1. 获取项目：

```bash
git clone https://github.com/wangshiqiang05/FindIdea-skill.git
```

或在仓库页面选择 **Code → Download ZIP** 下载并解压。

2. 将 `findidea-skill` 文件夹整体放入 AI Agent 的技能目录，保持目录结构完整。Agent 会通过 `SKILL.md` 自动识别，无需额外注册。通常情况下是：

- 🪟 **Windows**：`C:\Users\<你的用户名>\.agents\skills`
- 🐧 **Linux**：`~/agents/skills`
  

### 💬 使用

安装后直接用自然语言驱动 Agent，例如：

- 🗣️ "我在做 VLM 长视频理解，帮我找几个可做的研究 idea"
- 🔓 "帮我核验这篇论文是不是真开源：https://github.com/..."
- 🧐 "检查这个 idea 有没有人做过：[idea 描述]"
- 🧠 "帮我想一个xxx领域的idea"

两个脚本也可独立运行：

```bash
# 开源真实性审计
python3 scripts/github_audit.py owner/repo

# 台账管理
python3 scripts/idea_ledger.py init
python3 scripts/idea_ledger.py list
python3 scripts/idea_ledger.py stats
```

---

📄 本项目采用 **MIT 许可证**，详见 [LICENSE](LICENSE)。

