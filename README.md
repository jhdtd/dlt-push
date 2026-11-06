# 大乐透机选号码 · 云端定时推送

每周一、三、六 12:00（北京时间）在 GitHub Actions 上运行，生成 5 注大乐透号码卡片，
通过 PushPlus 推到个人微信。**不需要电脑开机**。

## 它怎么工作

1. `dlt_data.py` — 从体彩官方接口增量抓取历史开奖（含首次全量），缓存在 `state/history.json`
2. `dlt_card.py` — 用极大似然估计(MLE)的号码频率加权、无放回抽样生成 5 注
   （同注不重复、不与历史开出组合重复、多注之间不重复），渲染成表格卡片图
3. `dlt_wxpusher.py` — 把图片（公网外链）+ 号码表格通过 WxPusher 推到微信服务号
4. 工作流把当次图片提交回仓库，用 jsDelivr 生成 `https://` 外链给微信展示

## 一次性配置（约 3 分钟）

### 1. 获取你的 SPT（极简推送令牌）

1. 用微信扫下面的二维码（或打开链接）：
   <https://wxpusher.zjiecode.com/api/qrcode/RwjGLMOPTYp35zSYQr0HxbCPrV9eU0wKVBXU1D5VVtya0cQXEJWPjqBdW3gKLifS.jpg>
2. 关注「WxPusher」服务号后，它会立刻把你的 **SPT**（`SPT_` 开头的一串字符）发给你
3. 复制保存——这就是你的推送凭证，**不要泄露给任何人**
4. 之后所有消息都会出现在这个服务号里

> 无需注册账号、无需实名、完全免费。

### 2. 建仓库并上传代码

> 必须是 **Public（公开）** 仓库：微信里的图片走 jsDelivr 外链，私有仓库取不到。
> 内容只有号码图片和脚本，没有隐私信息。

新建一个空仓库后，在本目录执行（把 URL 换成你自己的）：

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
| `WXPUSHER_SPT` | 第 1 步拿到的 SPT（`SPT_` 开头） |

### 4. 手动跑一次验证

仓库 → Actions → 左侧「大乐透号码推送」→ Run workflow → 绿色按钮。
约 1 分钟后微信收到消息；如果没收到，点开这次运行看哪一步红了。

## 常见问题

**微信里只有文字表格、没有图片？**
说明 jsDelivr 那一刻没取到图（首次提交后 CDN 需要几秒）。脚本会自动退化成同款表格的文字版，
号码不会丢。下次运行通常就正常了。

**想改时间 / 注数？**
- 时间：`dlt-push.yml` 里的 `cron`（UTC，北京时间 12:00 = `0 4 * * 1,3,6`）
- 注数：`python dlt_card.py 5` 里的数字（1–10）

**GitHub 定时任务会延迟吗？**
会。免费额度下 cron 常有 5–20 分钟延迟，12:00 的任务实际可能在 12:05–12:20 送达。

## 说明

号码是「历史频率加权 + 随机」，不是预测。每注头奖概率恒为 1/21,425,712，理性购彩。
