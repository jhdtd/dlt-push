# 大乐透机选号码 · 云端定时推送

每周一、三、六 12:00（北京时间）在 GitHub Actions 上运行，生成 5 注大乐透号码卡片，
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

## 准点触发（可选，解决 GitHub 定时延迟）

GitHub 免费版的 `schedule` 实测可能延迟数小时（本项目 6 次运行实际落在 19:15–20:43）。
要准点，用外部定时器触发：

1. 建一个 **Fine-grained PAT**：GitHub → Settings → Developer settings →
   Personal access tokens → Fine-grained tokens → 只勾选本仓库，
   权限 `Actions: Read and write`，有效期自定
2. 打开 <https://cron-job.org>（免费注册），新建 cronjob：
   - URL：`https://api.github.com/repos/<owner>/<repo>/actions/workflows/dlt-push.yml/dispatches`
   - 方法：`POST`，请求体：`{"ref":"main"}`
   - Header：`Authorization: Bearer <你的 PAT>`、`Accept: application/vnd.github+json`
   - 计划：每周一、三、六 12:00（时区选 Asia/Shanghai）
3. 原生 cron 保留作兜底；`state/last_push.json` 保证不会重复推送

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
