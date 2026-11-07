# xuexi-wenhui-harvest

学习强国"习近平文汇"频道论述穷尽采集技能（WorkBuddy skill）。

按用户给定的检索词表，从学习强国"习近平文汇"频道穷尽采集习近平总书记的原文段落，产出可追溯（日期＋出处＋链接）的结构化工作底稿。全程只收本人原文，不做任何改写。

## 核心机制

- 学习强国前端为阿里云 WAF 防护，按 TLS 指纹拦截非浏览器流量 → **DrissionPage 接管真实 Chrome**，人类节奏操作
- 检索结果页 JS 点击切换"习近平文汇"tab，`page.listen` 截获检索 API JSON
- 逐词分目录存原始 JSON，断点续传，验证码挂起人工处理

## 结构

```
├── SKILL.md                  # 技能主文件：触发条件、五步工作流、纪律红线
├── scripts/
│   ├── xuexi_wenhui.py       # 主采集（--test / --word 词 / --all --words-file 词表.txt --out 目录）
│   ├── parse_wenhui_json.py  # 原始JSON → 条目总表CSV + 句子表CSV
│   └── dedup_items.py        # 机械去重（规范化精确去重 + 同日期包含合并）
└── references/
    └── playbook.md           # 实战手册：防风控纪律、API结构、已知坑、检索词表六层设计、五档语义标注体系
```

## 使用（WorkBuddy skill）

放置于 `~/.workbuddy/skills/xuexi-wenhui-harvest/` 即可。工作流：

1. 六层检索词表（核心表述/行为层/主体层/机制层/典故层/泛词层，泛词最后跑）
2. `xuexi_wenhui.py` 采集原始 JSON（单线程、随机间隔、断点续传）
3. `parse_wenhui_json.py` 解析建表
4. `dedup_items.py` 确定性去重
5. 模型语义标注（核心论述/要求部署/语境提及/反面警示/无关，样例批先经人工审核）
6. 按档位分章、章内按时间从旧到新，产出带日期与出处的工作底稿

## 纪律红线

- 只收习近平总书记本人原文，绝不改写
- 单线程＋人类节奏；出现验证码/IP 封禁立即停止并报告，不换 IP 硬爬
- 语义判断一律用模型，禁止正则/机械规则代劳

## 依赖

- 本机 Chrome、Python 3.8+、`pip install DrissionPage`
- 沙箱/代理环境运行：`env -u http_proxy -u https_proxy -u all_proxy python ...`
