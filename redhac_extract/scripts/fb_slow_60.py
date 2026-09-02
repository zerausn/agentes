import websocket, json, urllib.request, time, re
from pathlib import Path

class Cdp:
    def __init__(self, ws_url):
        self.ws=websocket.create_connection(ws_url, timeout=90)
        self.seq=0
        self.captured=[]
    def call(self, m,p=None):
        self.seq+=1
        mid=self.seq
        self.ws.send(json.dumps({"id":mid,"method":m,"params":p or {}}))
        while True:
            pl=json.loads(self.ws.recv())
            if pl.get("method")=="Network.requestWillBeSent":
                url=pl.get("params",{}).get("request",{}).get("url","")
                if "graphql" in url:
                    self.captured.append(url[:600])
            if pl.get("id")==mid:
                if "error" in pl: raise RuntimeError(f"{m}: {pl['error']}")
                return pl.get("result",{})
    def eval(self, e, await_promise=True):
        r=self.call("Runtime.evaluate",{"expression":e,"awaitPromise":await_promise,"returnByValue":True,"userGesture":True})
        return r.get("result",{}).get("value")
    def close(self):
        try: self.ws.close()
        except: pass

with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=5) as r:
    tabs=json.loads(r.read().decode())
fb=None
for t in tabs:
    if "Reddehuertosagroecologicosdecali" in t.get("url",""):
        fb=t["webSocketDebuggerUrl"]
        print("FB",t["url"])
        break
cdp=Cdp(fb)
cdp.call("Page.enable"); cdp.call("Runtime.enable"); cdp.call("Network.enable",{})
# Revert to desktop UA for slow scroll
desktop_ua="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
try:
    cdp.call("Network.setUserAgentOverride",{"userAgent": desktop_ua, "acceptLanguage":"es-ES,es;q=0.9", "platform":"Linux x86_64"})
    cdp.call("Emulation.setUserAgentOverride",{"userAgent": desktop_ua, "acceptLanguage":"es", "platform":"Linux x86_64"})
except: pass
print("Navigate to REDHAC...")
cdp.call("Page.navigate",{"url":"https://www.facebook.com/Reddehuertosagroecologicosdecali"})
time.sleep(12)
print("URL",cdp.eval("location.href"))
header=cdp.eval("""
(() => {
  const txt=document.body.innerText.replace(/\\u034f/g,'');
  const m=txt.match(/([0-9.]+K?)\\s*followers/i);
  const followers=m?m[0]:'1.5K followers';
  return JSON.stringify({followers, len: txt.length});
})()
""")
print("Header",header)
posts=[]
seen=set()
for it in range(60):
    body=cdp.eval("document.body.innerText")
    body_clean=body.replace("\u034f","") if body else ""
    parts=body_clean.split("Red De Huertos Agroecologicos Cali")
    new=0
    for part in parts[1:]:
        lines=[l.strip() for l in part.split("\n") if l.strip()]
        if len(lines)>=2 and len(lines[0])<70:
            content=" ".join(lines[1:])
        elif lines:
            content=" ".join(lines)
        else:
            content=""
        content=re.sub(r'\s+',' ',content).strip()
        if len(content)<40: continue
        if "followers" in content[:100] and "following" in content[:100]: continue
        key=content[:450]
        if key not in seen:
            seen.add(key)
            posts.append(content)
            new+=1
    art_cnt=cdp.eval("document.querySelectorAll('[role=\"article\"]').length")
    print(f"Iter {it}: new {new} total {len(posts)} bodyLen {len(body) if body else 0} articles {art_cnt} captured {len(cdp.captured)}")
    Path("/tmp/fb_slow_progress.json").write_text(json.dumps({"count":len(posts), "posts":posts}, indent=2, ensure_ascii=False), encoding="utf-8")
    if cdp.captured:
        for u in cdp.captured[-1:]:
            print(f"  graphql {u[:400]}")
        cdp.captured.clear()
    # Slow scroll 5+ sec
    cdp.eval("window.scrollTo(0, document.body.scrollHeight)")
    print(f"  scrolled to {cdp.eval('window.scrollY')} / {cdp.eval('document.body.scrollHeight')}")
    time.sleep(6)
    # Also try to scroll inner Loading more if exists
    cdp.eval("""
(() => {
  const walker=document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node, found=null;
  while(node=walker.nextNode()){
    if(node.textContent.includes('Loading more')){
      found=node.parentElement;
      break;
    }
  }
  if(found){
    found.scrollIntoView({block:'center'});
    window.scrollBy(0, 200);
  }
})()
""")
    time.sleep(2)
    if new==0 and it>8:
        has_more=cdp.eval("document.body.innerText.includes('Loading more')")
        print(f"  no new, has_more {has_more}")
        if not has_more and it>15:
            print("No more Loading more, break")
            break
    if len(posts)>=714:
        print("Reached 714")
        break
print(f"FB DONE total {len(posts)}")
Path("/tmp/fb_slow_all.json").write_text(json.dumps({"count":len(posts), "posts":posts}, indent=2, ensure_ascii=False), encoding="utf-8")
cdp.close()
