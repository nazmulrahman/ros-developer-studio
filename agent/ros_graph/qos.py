"""Publisher/subscriber QoS compatibility (RMW rules for reliability and durability)."""


def qos_conflicts(pubs: list[dict], subs: list[dict]) -> list[dict]:
    out = []
    for p in pubs:
        pq = p.get("qos") or {}
        for s in subs:
            sq = s.get("qos") or {}
            if sq.get("reliability") == "RELIABLE" and pq.get("reliability") == "BEST_EFFORT":
                reason = "subscriber requests RELIABLE but publisher is BEST_EFFORT"
            elif sq.get("durability") == "TRANSIENT_LOCAL" and pq.get("durability") == "VOLATILE":
                reason = "subscriber requests TRANSIENT_LOCAL but publisher is VOLATILE"
            else:
                continue
            out.append({"publisher": p["node"], "subscriber": s["node"], "reason": reason})
    return out
