def aggregate(docs: list[dict], pipeline: list[dict]) -> list[dict]:
    """Run a small MongoDB-style aggregation pipeline over `docs`."""
    data = list(docs)
    for stage in pipeline:
        if "$match" in stage:
            criteria = stage["$match"]
            data = [d for d in data if all(d.get(k) == v for k, v in criteria.items())]
        elif "$group" in stage:
            spec = stage["$group"]
            id_field = spec.get("_id")
            groups: dict = {}
            sums: dict = {}
            counts: dict = {}
            order: list = []
            for doc in data:
                if isinstance(id_field, str) and id_field.startswith("$"):
                    key = doc.get(id_field[1:])
                else:
                    key = id_field
                if key not in groups:
                    groups[key] = {"_id": key}
                    sums[key], counts[key] = {}, {}
                    order.append(key)
                for out_field, acc in spec.items():
                    if out_field == "_id":
                        continue
                    if "$sum" in acc:
                        expr = acc["$sum"]
                        value = 1 if expr == 1 else doc.get(expr[1:], 0)
                        sums[key][out_field] = sums[key].get(out_field, 0) + value
                        groups[key][out_field] = sums[key][out_field]
                    elif "$avg" in acc:
                        expr = acc["$avg"]
                        value = doc.get(expr[1:], 0)
                        sums[key][out_field] = sums[key].get(out_field, 0) + value
                        counts[key][out_field] = counts[key].get(out_field, 0) + 1
                        groups[key][out_field] = round(
                            sums[key][out_field] / counts[key][out_field], 2
                        )
            data = [groups[k] for k in order]
        elif "$sort" in stage:
            for field, direction in reversed(list(stage["$sort"].items())):
                data = sorted(data, key=lambda d, f=field: d.get(f), reverse=(direction == -1))
        elif "$limit" in stage:
            data = data[: stage["$limit"]]
    return data
