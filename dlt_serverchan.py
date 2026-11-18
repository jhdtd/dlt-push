#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 Server酱 把号码卡片推送到微信（服务号「Server酱」）。

支持两代接口，自动识别 SendKey 格式：
  1. Server酱 Turbo：SendKey 形如 SCTxxxxx        -> https://sctapi.ftqq.com/<key>.send
  2. Server酱³    ：SendKey 形如 sctp<uid>txxxx   -> https://<uid>.push.ft07.com/send/<key>.send
也可直接用环境变量 SERVERCHAN_URL 指定完整接口地址（不加 .send）。

凭证来源（按优先级）：环境变量 SERVERCHAN_SENDKEY / 同目录 serverchan_key.txt / SERVERCHAN_URL

图片：Server酱 的 desp 支持 markdown，需公网 https 图床（工作流里用 jsDelivr）。
      没有图片地址时退化为等价的 markdown 号码表格，信息不丢。

用法：python dlt_serverchan.py [图片路径] [副标题]
退出码：0 成功；2 未配置凭证；3 推送失败。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state")
KEY_FILE = os.path.join(HERE, "serverchan_key.txt")

TITLE_MAX = 32


def load_creds():
    """返回 (endpoint_url, sendkey) 或 None。"""
    url = (os.environ.get("SERVERCHAN_URL") or "").strip()
    key = (os.environ.get("SERVERCHAN_SENDKEY") or "").strip()
    if not key and os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f:
            key = f.read().strip()
    if not key:
        return None
    if url:
        return (url.rstrip("/"), key)

    # Server酱³：sctp<uid>t...
    m = re.match(r"^sctp(\d+)t", key, re.I)
    if m:
        return ("https://%s.push.ft07.com/send/%s" % (m.group(1), key), key)
    # Server酱 Turbo
    return ("https://sctapi.ftqq.com/%s" % key, key)


def load_tickets():
    p = os.path.join(STATE_DIR, "tickets.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build_markdown(meta, image_url):
    meta = meta or {}
    when = meta.get("generated_at") or time.strftime("%Y-%m-%d %H:%M")
    note = meta.get("note") or ""
    tickets = meta.get("tickets") or []
    n = len(tickets) or 5

    lines = ["**超级大乐透 · 机选 %d 注**" % n]
    lines.append("> %s 生成%s" % (when, (" · " + note) if note else ""))
    lines.append("")

    if image_url:
        lines.append("![号码卡片](%s)" % image_url)
        lines.append("")

    if tickets:
        lines.append("| 注 | 前区 | 后区 |")
        lines.append("|:--:|:--|:--|")
        for i, t in enumerate(tickets, 1):
            front = " ".join("%02d" % v for v in t.get("front") or [])
            back = " ".join("%02d" % v for v in t.get("back") or [])
            lines.append("| %d | %s | %s |" % (i, front, back))
        lines.append("")

    lines.append("---")
    lines.append("*号码由历史频率加权随机生成，不代表预测；每注头奖概率恒定 1/2142 万，理性购彩。*")
    return "\n".join(lines)


def send(endpoint, sendkey, title, desp):
    data = urllib.parse.urlencode({"title": title, "desp": desp}).encode("utf-8")
    last = None
    for attempt in range(3):
        req = urllib.request.Request(endpoint + ".send", data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode("utf-8", "ignore") or "{}")
            if res.get("code") == 0:
                return True, res
            last = res
            time.sleep(3 * (attempt + 1))
        except urllib.error.HTTPError as e:
            last = {"code": e.code, "message": e.read().decode("utf-8", "ignore")[:200]}
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            last = {"code": -1, "message": str(e)}
            time.sleep(3 * (attempt + 1))
    return False, last or {}


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else os.path.join(STATE_DIR, "latest.png")
    subtitle = sys.argv[2] if len(sys.argv) > 2 else ""

    creds = load_creds()
    if not creds:
        print("2 [未配置] 缺少 Server酱 SendKey：设置环境变量 SERVERCHAN_SENDKEY，"
              "或写入 %s。" % KEY_FILE)
        return 2

    image_url = (os.environ.get("DLT_IMAGE_URL") or "").strip()
    if image_url and not image_url.startswith("https://"):
        print("[提示] DLT_IMAGE_URL 不是 https，微信内可能不显示，已忽略。")
        image_url = ""
    if not os.path.exists(image):
        image_url = ""

    meta = load_tickets()
    desp = build_markdown(meta, image_url)
    title = (os.environ.get("DLT_TITLE") or "超级大乐透 · 机选号码").strip()
    if subtitle and subtitle not in title:
        title = "%s %s" % (title, subtitle)
    title = title[:TITLE_MAX]

    ok, res = send(creds[0], creds[1], title, desp)
    if ok:
        data = res.get("data") or {}
        print("0 [成功] Server酱 已接收任务 pushid=%s" % (data.get("pushid") or ""))
        return 0
    print("3 [失败] code=%s message=%s" % (res.get("code"), res.get("message")))
    return 3


if __name__ == "__main__":
    sys.exit(main())
