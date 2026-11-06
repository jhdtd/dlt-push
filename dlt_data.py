#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""超级大乐透历史开奖数据：抓取、滚动增量更新、极大似然估计(MLE)权重。

数据源：中国体育彩票官方接口 webapi.sporttery.cn（gameNo=85 即超级大乐透）。
本地缓存：state/history.json，每次运行自动增量补齐最新开奖，无需手动维护。
"""
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(HERE, "state")
CACHE = os.path.join(STATE_DIR, "history.json")

API = ("https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
       "?gameNo=85&provinceId=0&pageSize=100&isVerify=1&pageNo={page}")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Referer": "https://www.sporttery.cn/",
}
FRONT_POOL = 35   # 前区 01-35
BACK_POOL = 12    # 后区 01-12


def _fetch_page(page_no, timeout=25, retries=3):
    """抓取一页（100 期），返回按期号倒序的列表。"""
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(API.format(page=page_no), headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            value = data.get("value") or {}
            out = []
            for it in value.get("list") or []:
                num = str(it.get("lotteryDrawNum") or "").strip()
                res = str(it.get("lotteryDrawResult") or "").strip()
                parts = res.split()
                if not num or len(parts) != 7:
                    continue
                out.append({"n": num, "d": str(it.get("lotteryDrawTime") or "")[:10],
                            "r": " ".join(parts)})
            return out, int(value.get("total") or 0)
        except Exception as e:  # 网络抖动重试
            last_err = e
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError("抓取第 %s 页失败: %s" % (page_no, last_err))


def _load_cache():
    if not os.path.exists(CACHE):
        return []
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f).get("draws") or []
    except Exception:
        return []


def _save_cache(draws):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "draws": draws},
                  f, ensure_ascii=False)
    os.replace(tmp, CACHE)


def update(verbose=True):
    """增量更新本地历史开奖库，返回 (draws, 新增期数)。

    首次运行会全量抓取；之后每次仅拉取新增的期，随开奖自动滚动更新。
    """
    cached = _load_cache()
    seen = {d["n"] for d in cached}
    newest = max(seen) if seen else None
    full = not cached  # 无缓存时全量抓取

    page = 1
    fresh = []
    total_pages = None
    while True:
        page_items, total = _fetch_page(page)
        if total_pages is None:
            total_pages = max(1, -(-total // 100))
        fresh.extend(page_items)
        oldest_on_page = page_items[-1]["n"] if page_items else ""
        if page >= total_pages:
            break
        if not full and oldest_on_page <= newest:
            break  # 已翻过本地缓存的最新一期，无需再往前
        page += 1

    merged = {d["n"]: d for d in cached}
    added = 0
    for d in fresh:
        if d["n"] not in merged:
            merged[d["n"]] = d
            added += 1
    draws = sorted(merged.values(), key=lambda x: x["n"], reverse=True)
    if added or not cached:
        _save_cache(draws)
    if verbose:
        print("[数据] 历史开奖 %d 期（本次新增 %d 期，最新 %s %s）"
              % (len(draws), added, draws[0]["n"] if draws else "-",
                 draws[0]["d"] if draws else "-"))
    return draws, added


def parse(draw):
    nums = [int(x) for x in draw["r"].split()]
    return nums[:5], nums[5:]


def mle_weights(draws, alpha=0.5):
    """用极大似然估计（带 Laplace 平滑）得到前区/后区的号码分布概率。

    多项分布的 MLE 就是各号码的出现频率：p_i = 出现期数 / 总期数。
    前区理论值 5/35≈0.1429，后区理论值 2/12≈0.1667，实际值因历史数据略有偏差。
    alpha 为平滑系数，避免零概率。

    返回 (front_w, back_w, n_draws)：
      front_w[i] 对应号码 01-35，back_w[j] 对应号码 01-12。
    """
    fc = [0] * FRONT_POOL
    bc = [0] * BACK_POOL
    for d in draws:
        front, back = parse(d)
        for x in front:
            if 1 <= x <= FRONT_POOL:
                fc[x - 1] += 1
        for y in back:
            if 1 <= y <= BACK_POOL:
                bc[y - 1] += 1
    n = max(1, len(draws))
    ft = n + alpha * FRONT_POOL
    bt = n + alpha * BACK_POOL
    front_w = [(fc[i] + alpha) / ft for i in range(FRONT_POOL)]
    back_w = [(bc[j] + alpha) / bt for j in range(BACK_POOL)]
    return front_w, back_w, len(draws)


def history_combos(draws):
    """历史已开出的组合集合（用于避免重复历史号码）。"""
    combos = set()
    for d in draws:
        front, back = parse(d)
        combos.add((tuple(sorted(front)), tuple(sorted(back))))
    return combos


if __name__ == "__main__":
    draws, added = update()
    fw, bw, n = mle_weights(draws)
    order = sorted(range(FRONT_POOL), key=lambda i: fw[i], reverse=True)
    print("前区出现概率 Top5: " + ", ".join("%02d %.4f" % (i + 1, fw[i]) for i in order[:5]))
    order_b = sorted(range(BACK_POOL), key=lambda i: bw[i], reverse=True)
    print("后区出现概率 Top5: " + ", ".join("%02d %.4f" % (j + 1, bw[j]) for j in order_b[:5]))
