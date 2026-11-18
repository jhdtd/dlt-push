# 大乐透机选号码 · 云端定时推送

每周一、三、六 12:00（北京时间，遇调度延迟自动补推）在 GitHub Actions 上运行，生成 5 注大乐透号码卡片，
通过 **Server酱** 推到个人微信。**不需要电脑开机**。

## 它怎么工作

1. `dlt_data.py` — 从体彩官方接口增量抓取历史开奖（含首次全量），缓存在 `state/history.json`
2. `dlt_card.py` — 用极大似然估计(MLE)的号码频率加权、无放回抽样生成 5 注
   （同注不重复、不与历史开出组合重复、多注之间不重复），渲染成表格卡片图，并输出 `state/tickets.json`
3. `dlt_serverchan.py` — 把 markdown（图片 + 号码表格）通过 Server酱 推到微信服务号
4. 工作流把当次图片提交回仓库，用 jsDelivr 生成 `https://` 外链供微信展示
5. `state/last_push.json` 记录推送日期，重复触发（如外部定时器 + 原生 cron 同时生效）只会发一次

## 一次性配置

### 1. 拿 Server酱 SendKey

1. 打开 <https://sct.ftqq.com>（Server酱 Turbo），用**微信扫码**登录
2. 按提示关注「Server酱」服务号
3. 在「SendKey」页面复制那串 key（`SCT` 开头；若使用 Server酱³ 则是 `sctp<uid>t...`）
4. 免费额度每天 5 条，每周 3 条推送足够用

> SendKey 等同推送凭证，不要泄露。

### 2. 建仓库并上传代码

> 必须是 **Public（公开）** 仓库：微信里的图片走 jsDelivr 外链，私有仓库取不到。

```bash
git init
git add .
git commit -m "init: 大乐透云端推送"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

### 3. 配置 Secret

仓库 → Settings → Secrets and variables → Actions → New repository secret：

| Name | Value |
|---|---|
| `SERVERCHAN_SENDKEY` | 第 1 步拿到的 SendKey |

### 4. 手动跑一次验证

仓库 → Actions → 左侧「大乐透号码推送」→ Run workflow → 绿色按钮。
约 1 分钟后微信收到消息；没收到就点开这次运行看哪一步红了。

## 准点推送怎么保证（无需第三方账号）

GitHub 免费版的 `schedule` 实测会延迟数小时（本项目 6 次运行都落在北京 19:15–20:43）。
工作流用「双时段 cron + 时间窗口守卫」来抵消：

```yaml
- cron: "0 4 * * 1,3,6"    # 北京 12:00：不延迟时准点推送
- cron: "0 20 * * 0,2,5"   # 北京 04:00：若延迟 7~8 小时，正好落在北京 11~12 点
```

守卫逻辑（`判断是否需要推送` 步骤）：

| 北京当前时间 | 行为 |
|---|---|
| 10:00–14:00 | 正常推送（准点窗口） |
| 14:00–22:00 | 补推（定时被延迟了，晚到但不错过） |
| 22:00–10:00 | 跳过（避免凌晨发消息） |
| 当天已推送 | 跳过（`state/last_push.json` 去重） |
| 手动/外部触发 | 直接推送，不受限制 |

如果将来 GitHub 的延迟消失，`0 4` 那条会准时在 12:00 触发，`0 20` 那条则落在凌晨被守卫跳过，两者不会重复。

想用外部定时器做到分钟级准点，工作流也支持 `repository_dispatch`（type: `dlt-push`），
用 cron-job.org 之类的服务带 PAT 调用即可。

## 常见问题

**微信里只有文字表格、没有图片？**
说明 jsDelivr 那一刻没取到图。脚本会自动退化成同款表格的文字版，号码不会丢，下次通常正常。

**想改时间 / 注数？**
- 时间：`dlt-push.yml` 里的 `cron`（UTC，北京时间 12:00 = `0 4 * * 1,3,6`）
- 注数：`python dlt_card.py 5` 里的数字（1–10）

**公众号消息没有通知横幅？**
进入和「Server酱」的聊天 → 右上角 → 打开消息通知（关掉免打扰）。

## 说明

号码是「历史频率加权 + 随机」，不是预测。每注头奖概率恒为 1/21,425,712，理性购彩。
