import websocket, json, urllib.request, time, re
from pathlib import Path

class Cdp:
    def __init__(self, ws_url):
        self.ws=websocket.create_connection(ws_url, timeout=30)
        self.seq=0
    def call(self, m,p=None):
        self.seq+=1
        mid=self.seq
        self.ws.send(json.dumps({"id":mid,"method":m,"params":p or {}}))
        while True:
            pl=json.loads(self.ws.recv())
            if pl.get("id")==mid:
                if "error" in pl: raise RuntimeError(pl["error"])
                return pl.get("result",{})
    def eval(self, e, await_promise=True):
        r=self.call("Runtime.evaluate",{"expression":e,"awaitPromise":await_promise,"returnByValue":True,"userGesture":True})
        return r.get("result",{}).get("value")
    def close(self):
        try: self.ws.close()
        except: pass

with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=5) as r:
    tabs=json.loads(r.read().decode())
ig_tab=None
for t in tabs:
    if "instagram.com/redhuertosagroecali" in t.get("url",""):
        ig_tab=t["webSocketDebuggerUrl"]
        break
# Create new tab for fetching likes
import requests
r=requests.put("http://127.0.0.1:9222/json/new?about:blank", timeout=10)
post_ws=r.json()["webSocketDebuggerUrl"]
print("Post tab",post_ws)
cdp=Cdp(post_ws)
cdp.call("Page.enable"); cdp.call("Runtime.enable")

ig_data=json.loads(Path("/tmp/ig_all_final.json").read_text(encoding="utf-8"))
sample=ig_data["media"][:15]
results=[]
for idx, m in enumerate(sample, start=1):
    href=m["href"]
    print(f"\n{idx}. Fetching {href[:60]}")
    cdp.call("Page.navigate",{"url":href})
    time.sleep(6)
    # Try to extract likes, comments, shares, date
    info=cdp.eval("""
(() => {
  const txt=document.body.innerText;
  // Try to find likes
  let likes='';
  let m=txt.match(/([0-9.,]+)\\s*Me gusta/);
  if(m) likes=m[0];
  else {
    m=txt.match(/([0-9.,]+)\\s*likes?/i);
    if(m) likes=m[0];
  }
  // Comments
  let comments='';
  let mc=txt.match(/([0-9]+)\\s*comentarios?/i);
  if(mc) comments=mc[0];
  // Date
  let date='';
  const timeEl=document.querySelector('time');
  if(timeEl) date=timeEl.getAttribute('datetime') || timeEl.innerText;
  // Also try to get from meta
  const ogDesc=document.querySelector('meta[property="og:description"]')?.content || '';
  // Try to get likes from og:description like "1,234 likes"
  if(!likes){
    const m2=ogDesc.match(/([0-9.,]+)\\s*likes?/i);
    if(m2) likes=m2[0];
  }
  return JSON.stringify({likes, comments, date, ogDesc: ogDesc.slice(0,300), txtSnippet: txt.slice(0,800)});
})()
""")
    print(f"  Info {info[:600] if info else ''}")
    try:
        obj=json.loads(info) if info else {}
        obj["href"]=href
        obj["alt"]=m.get("alt","")[:300]
        results.append(obj)
    except:
        results.append({"href":href, "error": info[:500] if info else ""})
    # Be nice
    time.sleep(2)

Path("/tmp/ig_likes_sample.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nDone {len(results)}")
for r in results[:5]:
    print(f"{r.get('href','')[:50]} likes {r.get('likes','')} comments {r.get('comments','')} date {r.get('date','')[:30]}")
cdp.close()
