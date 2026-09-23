import json, websocket
ws_url = "ws://127.0.0.1:9222/devtools/page/92C2B510DA268AB078237794EDBF73B2"
ws = websocket.create_connection(ws_url, timeout=5)
msg = json.dumps({
    "id": 1,
    "method": "Runtime.evaluate",
    "params": {
        "expression": "Array.from(document.querySelectorAll('img')).map(img => ({w: img.naturalWidth, h: img.naturalHeight, src: img.src.substring(0,60)}))",
        "returnByValue": True
    }
})
ws.send(msg)
print(ws.recv())
ws.close()
