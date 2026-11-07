# -*- coding: utf-8 -*-
"""
跨词机械去重（确定性，不涉及语义判断）：
  第一步: 规范化 summary（去空白差异）后精确去重 —— 同一段落的完全重复
  第二步: 同日期内 summary 包含关系去重 —— 短版本是长版本的子串时保留最长，合并检索词
输入: 条目总表 CSV（需含 keyword/date/summary 列）
输出: 去重后待标注 CSV（keywords 合并，keyword 列改为 keywords）

用法:
    python dedup_items.py <输入.csv> <输出.csv>
"""
import csv, re, sys


def norm(s):
    """规范化段落文本：统一空白，便于精确比对"""
    return re.sub(r"[\s\u3000]+", "", str(s))


def main():
    if len(sys.argv) < 3:
        sys.exit("用法: python dedup_items.py <输入.csv> <输出.csv>")
    src, dst = sys.argv[1], sys.argv[2]
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    total_in = len(rows)

    # 第一步: 规范化精确去重
    seen, step1 = {}, []
    for r in rows:
        k = norm(r["summary"])
        if k in seen:
            seen[k]["_kw"].append(r["keyword"])
        else:
            r["_kw"] = [r["keyword"]]
            seen[k] = r
            step1.append(r)
    n1 = total_in - len(step1)

    # 第二步: 同日期内包含关系去重（保留最长）
    by_date = {}
    for r in step1:
        by_date.setdefault(r["date"], []).append(r)
    kept = []
    n2 = 0
    for date, grp in by_date.items():
        # 短的在前，逐条与已保留的比较：被包含则并入，否则保留
        grp_sorted = sorted(grp, key=lambda r: len(norm(r["summary"])))
        local = []
        for r in grp_sorted:
            t = norm(r["summary"])
            merged = False
            for k in local:
                if t in norm(k["summary"]):
                    k["_kw"].extend(r["_kw"])
                    merged = True
                    break
            if not merged:
                local.append(r)
        n2 += len(grp) - len(local)
        kept.extend(local)

    # 排序输出：按日期从旧到新
    kept.sort(key=lambda r: (r.get("date") or "", r.get("title") or ""))
    fields = ["keywords", "date", "title", "summary", "source_doc", "url"]
    with open(dst, "w", newline="", encoding="utf-8-sig") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        for r in kept:
            kws = list(dict.fromkeys(r["_kw"]))  # 保序去重
            w.writerow({"keywords": "、".join(kws), "date": r["date"], "title": r["title"],
                        "summary": r["summary"], "source_doc": r["source_doc"], "url": r["url"]})

    print(f"输入 {total_in} 条 → 精确去重减 {n1} 条 → 包含去重减 {n2} 条 → 输出 {len(kept)} 条 → {dst}")


if __name__ == "__main__":
    main()
