import json, time, urllib.request, websocket
from pathlib import Path

class Cdp:
    def __init__(self, ws_url):
        self.ws=websocket.create_connection(ws_url, timeout=60)
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
ig_ws=None
for t in tabs:
    if "instagram.com/redhuertosagroecali" in t.get("url",""):
        ig_ws=t["webSocketDebuggerUrl"]
        print("Found IG",t["url"])
        break
if not ig_ws:
    print("No IG tab found")
    exit(1)

cdp=Cdp(ig_ws)
cdp.call("Page.enable"); cdp.call("Runtime.enable")

# Load existing progress
progress_path=Path("/tmp/ig_progress.json")
if progress_path.exists():
    data=json.loads(progress_path.read_text(encoding="utf-8"))
    ig_media=data.get("media",[])
    ig_seen=set(m["href"] for m in ig_media)
    header=data.get("header",{})
    print(f"Resuming from {len(ig_media)} media")
else:
    ig_media=[]
    ig_seen=set()
    header=json.loads(cdp.eval("JSON.stringify({title:document.title})") or "{}")

# Continue scrolling
for it in range(40):
    batch_str=cdp.eval("""
(() => {
  const as=document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
  const uniq=[...new Set(Array.from(as).map(a=>a.href))];
  const data=uniq.slice(0,150).map(href=>{
    const a=Array.from(document.querySelectorAll('a')).find(x=>x.href===href);
    let alt='', img='';
    if(a){
      const imgEl=a.querySelector('img');
      if(imgEl){ alt=imgEl.alt?.slice(0,1500)||''; img=imgEl.src?.slice(0,500)||''; }
    }
    return {href, alt, img};
  });
  return JSON.stringify(data);
})()
""")
    try:
        batch=json.loads(batch_str) if batch_str else []
    except:
        batch=[]
    new=0
    for b in batch:
        if b["href"] not in ig_seen:
            ig_seen.add(b["href"])
            ig_media.append(b)
            new+=1
    print(f"IG Iter {it}: batch {len(batch)} new {new} total {len(ig_media)}")
    # Save
    Path("/tmp/ig_progress.json").write_text(json.dumps({"header":header, "count":len(ig_media), "media":ig_media}, indent=2, ensure_ascii=False), encoding="utf-8")
    if len(ig_media)>=469:
        print("Reached 469, done")
        break
    if new==0 and it>5:
        print("No new, checking dom size")
        extra=cdp.eval("document.querySelectorAll('a[href*=\"/p/\"]').length")
        print(f"  dom links {extra}")
        if it>15 and new==0:
            break
    cdp.eval("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(4)

Path("/tmp/ig_all_final.json").write_text(json.dumps({"header":header, "media":ig_media}, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"IG FINAL total {len(ig_media)}")
cdp.close()
