# 顶刊顶会清单与文献检索

## 目录
1. 各子领域公认顶会与顶刊
2. 检索渠道
3. 检索式构造与流程纪律

## 1. 各子领域公认顶会与顶刊

用户口语中的"顶刊"在计算机学科通常指顶会，两类都要覆盖。以下为各方向公认高口碑发表场所。

| 子领域 | 顶会 | 顶刊 |
|---|---|---|
| 通用机器学习 | NeurIPS, ICML, ICLR | JMLR |
| 计算机视觉 | CVPR, ICCV, ECCV | TPAMI, IJCV |
| 自然语言处理 | ACL, EMNLP, NAACL | TACL, Computational Linguistics |
| 多媒体 | ACM MM | IEEE TMM |
| 机器人/具身智能 | RSS, CoRL, ICRA, IROS | RA-L, TRO |
| 数据挖掘/信息检索 | KDD, WWW, SIGIR, WSDM | TOIS, TKDE |
| 通用人工智能 | AAAI, IJCAI | AIJ, JAIR |
| 系统/ML 系统 | OSDI, SOSP, MLSys, ATC | TOCS |
| 医学影像 | MICCAI, IPMI | TMI, Medical Image Analysis |
| 图形学 | SIGGRAPH, SIGGRAPH Asia | TOG |
| 语音 | ICASSP, Interspeech | TASLP |
| 安全/网络 | S&P, CCS, USENIX Security, NDSS | S&P Magazine |

使用要点：
- 源领域不在表内时，先确认其公认等级（学会/CCF 分级/业内口碑），不把掠夺性会议和纯收费 workshop 当来源。
- arXiv 不是发表场所，但用于追踪最新工作；只在 arXiv 出现的文章需检查其是否已被顶会接收。

## 2. 检索渠道

按可获得性选择，优先使用环境内已配置的工具，再补公开站点：

- 环境内工具：`general_search`（通用网络检索）、学术检索类工具（如已配置的 scholar 搜索）、`web.fetch` 精读具体页面。
- 公开站点：Google Scholar、Semantic Scholar、arXiv、DBLP、OpenReview、Papers with Code。
- Papers with Code 同时提供论文-代码对应关系与 benchmark，是连接第 3、4 阶段的关键站点。
- 浏览器交互路径：需要登录或动态加载的站点（如 OpenReview 过滤视图）按 browser-use-automation skill 操作，不默认写爬虫。

## 3. 检索式构造与流程纪律

时间窗：默认近 3 年；被反复验证的经典机制可放宽到 5 年；超过 5 年的工作只作为谱系背景，不作为 idea 主源。

检索式构造：
1. 用"源领域名 + 核心机制名 + 任务名"组合，如 `agent memory long-horizon video`。
2. 中英文各检一轮；英文再用同义词替换重检（memory / state / context / cache）。
3. 滚雪球：命中一篇核心论文后，顺查其参考文献、逆查被引论文，并查看同作者后续工作。
4. 每轮检索保留检索式、日期与命中数，避免重复劳动。

每篇候选文章必须记录：标题、作者、venue、年份、论文 URL、代码链接（论文内标注的官方链接），用 `idea_ledger.py add` 录入台账。
建议每个源领域初筛 15-30 篇，进入开源核验前先按与目标问题的相关度排序，避免在低相关文章上浪费核验成本。

