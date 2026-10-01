import json, websocket, time
ws_url = "ws://127.0.0.1:9222/devtools/page/92C2B510DA268AB078237794EDBF73B2"
ws = websocket.create_connection(ws_url, timeout=5)
js = """
(async () => {
    try {
        let imgs = Array.from(document.querySelectorAll('img')).filter(img => img.naturalWidth >= 1080);
        if(imgs.length === 0) return {error: "No large img found"};
        let url = imgs[0].src;
        let r = await fetch(url, {credentials: 'include'});
        return {status: r.status, url: url.substring(0, 50)};
    } catch(e) { return {error: e.toString()}; }
})()
"""
msg = json.dumps({
    "id": 1,
    "method": "Runtime.evaluate",
    "params": {
        "expression": js,
        "awaitPromise": True,
        "returnByValue": True
    }
})
ws.send(msg)
print(ws.recv())
ws.close()
