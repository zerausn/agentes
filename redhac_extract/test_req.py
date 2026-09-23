import json, requests, websocket
ws_url = "ws://127.0.0.1:9222/devtools/page/92C2B510DA268AB078237794EDBF73B2"
ws = websocket.create_connection(ws_url, timeout=5)
js = "Array.from(document.querySelectorAll('img')).filter(img => img.naturalWidth >= 1080)[0].src"
msg = json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js, "returnByValue": True}})
ws.send(msg)
url = json.loads(ws.recv())["result"]["result"]["value"]
ws.close()

r = requests.get(url)
print(r.status_code, len(r.content), url[:60])
