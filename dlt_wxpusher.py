#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通过 WxPusher（微信服务号通道）把号码卡片推送到个人微信。免费、无需实名。

两种凭证模式（二选一，优先 SPT）：
  1. 极简推送：环境变量 WXPUSHER_SPT（SPT_xxx，微信扫码即可获取，无需建应用）
  2. 标准推送：环境变量 WXPUSHER_APP_TOKEN（AT_xxx）+ WXPUSHER_UID（UID_xxx）

图片展示：WxPusher 的 HTML 消息支持 <img>，图片必须是公网 https 地址。
  - 有 DLT_IMAGE_URL 时渲染图片卡片；
  - 没有时退化为等价的 HTML 号码表格（信息不丢）。

用法：python dlt_wxpusher.py [图片路径] [副标题]
退出码：0 成功；2 未配置凭证；3 推送失败。
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_SIMPLE = "https://wxpusher.zjiecode.com/api/send/message/simple-push"
API_STANDARD = "https://wxpusher.zjiecode.com/api/send/message"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state")
TOKEN_FILE = os.path.join(HERE, "wxpusher_spt.txt")

FONT = "-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif"


def load_creds():
    """返回 (mode, payload 鉴权字段 dict) 或 None。"""
    spt = (os.environ.get("WXPUSHER_SPT") or "").strip()
    if not spt and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as f:
            spt = f.read().strip()
    if spt:
        return ("simple", {"spt": spt})
    token = (os.environ.get("WXPUSHER_APP_TOKEN") or "").strip()
    uid = (os.environ.get("WXPUSHER_UID") or "").strip()
    if token and uid:
        return ("standard", {"appToken": token, "uids": [uid]})
    return None


def load_tickets():
    p = os.path.join(STATE_DIR, "tickets.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _numbers_rows(meta):
    rows = []
    for i, t in enumerate(meta.get("tickets") or [], 1):
        front = " ".join("%02d" % v for v in t.get("front") or [])
        back = " ".join("%02d" % v for v in t.get("back") or [])
        rows.append(
            '<tr>'
            '<td style="padding:9px 6px;color:#a3a9b3;font-size:12px;text-align:center">%d</td>'
            '<td style="padding:9px 6px;font-family:Menlo,Consolas,monospace;font-size:15px;'
            'letter-spacing:1px;color:#343940;text-align:center">%s</td>'
            '<td style="padding:9px 6px;font-family:Menlo,Consolas,monospace;font-size:15px;'
            'letter-spacing:1px;color:#343940;text-align:center">%s</td>'
            '</tr>' % (i, front, back))
    return "".join(rows)


def build_html(meta, image_url):
    meta = meta or {}
    when = meta.get("generated_at") or time.strftime("%Y-%m-%d %H:%M")
    note = meta.get("note") or ""
    n = len(meta.get("tickets") or []) or 5
    head = (
        '<div style="font-family:%s;max-width:600px;margin:0 auto;color:#343940">'
        '<div style="font-size:17px;font-weight:600;margin-bottom:4px">超级大乐透 · 机选 %d 注</div>'
        '<div style="font-size:12px;color:#8a9099;margin-bottom:12px">%s 生成%s</div>'
        % (FONT, n, when, (" · " + note) if note else "")
    )

    body = ""
    if image_url:
        body += ('<img src="%s" style="width:100%%;display:block;border-radius:10px" />'
                 % image_url)

    rows = _numbers_rows(meta)
    if rows:
        table = (
            '<table cellspacing="0" cellpadding="0" style="width:100%%;border-collapse:collapse;'
            'background:#fff;border:1px solid #e7eaee;border-radius:10px;'
            'margin-top:%dpx">'
            '<tr style="background:#f5f6f7">'
            '<td style="padding:8px 6px;font-size:12px;color:#8a9099;text-align:center">注</td>'
            '<td style="padding:8px 6px;font-size:12px;color:#8a9099;text-align:center">前区</td>'
            '<td style="padding:8px 6px;font-size:12px;color:#8a9099;text-align:center">后区</td>'
            '</tr>%s</table>' % (12 if image_url else 0, rows)
        )
        body += table

    tail = ('<div style="font-size:11px;color:#aab0b8;margin-top:12px;line-height:1.7">'
            '号码由历史频率加权随机生成，不代表预测；每注头奖概率恒定 1/2142 万，理性购彩。</div>'
            '</div>')
    return head + body + tail


def send(mode, auth, title, content):
    if mode == "simple":
        body = dict(auth)
        body.update({"content": content, "summary": title[:100], "contentType": 2})
        url = API_SIMPLE
    else:
        body = dict(auth)
        body.update({"content": content, "summary": title[:100], "contentType": 2})
        url = API_STANDARD
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    last = None
    for attempt in range(3):
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Content-Type", "application/json; charset=utf-8")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                res = json.loads(r.read().decode("utf-8", "ignore") or "{}")
            code = res.get("code")
            if code == 1000:
                return True, res
            last = res
            time.sleep(3 * (attempt + 1))
        except urllib.error.HTTPError as e:
            last = {"code": e.code, "msg": e.read().decode("utf-8", "ignore")[:200]}
            time.sleep(3 * (attempt + 1))
        except Exception as e:
            last = {"code": -1, "msg": str(e)}
            time.sleep(3 * (attempt + 1))
    return False, last or {}


def main():
    image = sys.argv[1] if len(sys.argv) > 1 else os.path.join(STATE_DIR, "latest.png")
    subtitle = sys.argv[2] if len(sys.argv) > 2 else ""

    creds = load_creds()
    if not creds:
        print("2 [未配置] 缺少 WxPusher 凭证："
              "微信扫码获取极简推送 SPT（见 README），设置为 WXPUSHER_SPT，"
              "或写入 %s；也可用 WXPUSHER_APP_TOKEN + WXPUSHER_UID。" % TOKEN_FILE)
        return 2

    image_url = (os.environ.get("DLT_IMAGE_URL") or "").strip()
    if image_url and not image_url.startswith("https://"):
        print("[提示] DLT_IMAGE_URL 不是 https，微信内可能不显示，已忽略。")
        image_url = ""
    if not os.path.exists(image):
        image_url = ""

    meta = load_tickets()
    content = build_html(meta, image_url)
    title = (os.environ.get("DLT_TITLE") or "超级大乐透 · 机选号码").strip()
    if subtitle and subtitle not in title:
        title = "%s %s" % (title, subtitle)
    title = title[:100]

    ok, res = send(creds[0], creds[1], title, content)
    if ok:
        data = res.get("data") or []
        first = data[0] if isinstance(data, list) and data else {}
        print("0 [成功] 已通过 WxPusher 创建发送任务 contentId=%s"
              % (first.get("messageContentId") or ""))
        return 0
    print("3 [失败] code=%s msg=%s" % (res.get("code"), res.get("msg")))
    return 3


if __name__ == "__main__":
    sys.exit(main())
