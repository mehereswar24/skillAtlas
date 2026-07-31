def parse_request(raw: str) -> dict:
    head, _, body = raw.partition("\r\n\r\n")
    request_line, *header_lines = head.split("\r\n")
    method, target, version = request_line.split(" ", 2)

    path, _, query_string = target.partition("?")
    query = {}
    for pair in filter(None, query_string.split("&")):
        key, _, value = pair.partition("=")
        query[key] = value

    headers = {}
    for line in header_lines:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()

    return {
        "method": method,
        "path": path,
        "query": query,
        "version": version,
        "headers": headers,
        "body": body,
    }
