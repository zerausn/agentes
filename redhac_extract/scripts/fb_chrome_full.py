import json, time, urllib.request, websocket, re
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

# Find FB tab in Chrome (which has Edge profile)
with urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=5) as r:
    tabs=json.loads(r.read().decode())
fb_ws=None
for t in tabs:
    if "Reddehuertosagroecologicosdecali" in t.get("url","") and t.get("type")=="page":
        fb_ws=t["webSocketDebuggerUrl"]
        print("FB Chrome tab",t["url"])
        break
if not fb_ws:
    import requests
    r=requests.put("http://127.0.0.1:9222/json/new?https://www.facebook.com/Reddehuertosagroecologicosdecali", timeout=10)
    fb_ws=r.json()["webSocketDebuggerUrl"]
    print("Created FB")

cdp=Cdp(fb_ws)
cdp.call("Page.enable"); cdp.call("Runtime.enable")

# Ensure navigation to main page
print("Ensure FB main...")
cdp.call("Page.navigate",{"url":"https://www.facebook.com/Reddehuertosagroecologicosdecali"})
time.sleep(10)
print("URL",cdp.eval("location.href"))
# Get header
header=cdp.eval("""
(() => {
  const txt=document.body.innerText.replace(/\\u034f/g,'');
  const m=txt.match(/([0-9.,]+)\\s*(mil)?\\s*seguidores/i);
  const followers=m?m[0]:'1549 seguidores';
  const contact=txt.match(/[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}/i)?.[0] || 'redhuertosagroecologicoscali@gmail.com';
  const cat=txt.match(/Página · [^\\n]+/)?.[0] || 'Agricultura';
  const addr=txt.match(/Calle[^\\n]+/)?.[0] || 'Calle13, Santiago de Cali, Colombia, 760032';
  return JSON.stringify({followers, contact, category:cat, address:addr, title:document.title, url:location.href});
})()
""")
print("Header",header)
header_obj=json.loads(header) if header else {}

# Try to find scrollable with hasFeed
# First, scroll inner div approach
posts=[]
seen=set()
# Use body innerText parsing but with inner div scroll
for it in range(60):
    # Scroll the inner feed container
    scroll_res=cdp.eval("""
(() => {
  const allDivs=Array.from(document.querySelectorAll('div'));
  const scrollables=allDivs.filter(d=>d.scrollHeight > d.clientHeight + 80 && d.scrollHeight>1500);
  // Find the one that contains REDHAC posts
  let target=null;
  let maxSH=0;
  for(const d of scrollables){
    const txt=d.innerText || '';
    if(txt.includes('Red De Huertos') && d.scrollHeight>maxSH){
      maxSH=d.scrollHeight;
      target=d;
    }
  }
  if(!target && scrollables.length>0){
    // fallback to largest
    target=scrollables.reduce((a,b)=>a.scrollHeight>b.scrollHeight?a:b, scrollables[0]);
  }
  if(target){
    const before=target.scrollTop;
    target.scrollTop = target.scrollHeight;
    // also window
    window.scrollTo(0, document.body.scrollHeight);
    return JSON.stringify({found:true, before, after: target.scrollTop, sh: target.scrollHeight, ch: target.clientHeight, bodyLen: document.body.innerText.length, articles: document.querySelectorAll('[role="article"]').length});
  } else {
    window.scrollTo(0, document.body.scrollHeight);
    return JSON.stringify({found:false, windowSH: document.body.scrollHeight, bodyLen: document.body.innerText.length, articles: document.querySelectorAll('[role="article"]').length});
  }
})()
""")
    print(f"Iter {it} scroll {scroll_res}")
    time.sleep(4)
    # Collect body innerText and parse posts
    body=cdp.eval("document.body.innerText")
    if not body: continue
    body_clean=body.replace("\u034f","")
    parts=body_clean.split("Red De Huertos Agroecologicos Cali")
    new=0
    for part in parts[1:]:
        lines=[l.strip() for l in part.split("\n") if l.strip()]
        # Skip first garbled date line if short
        if len(lines)>=2 and len(lines[0])<70:
            content=" ".join(lines[1:])
        elif lines:
            content=" ".join(lines)
        else:
            content=""
        content=re.sub(r'\s+',' ',content).strip()
        if len(content)<50: continue
        if "Privacidad" in content and "Condiciones" in content and len(content)<900: continue
        # Dedupe
        key=content[:400]
        if key not in seen:
            seen.add(key)
            posts.append(content)
            new+=1
    print(f"  collected new {new} total {len(posts)} body len {len(body)} parts {len(parts)}")
    # Also try to get articles via role
    art_cnt=cdp.eval("document.querySelectorAll('[role=\"article\"]').length")
    print(f"  articles in DOM {art_cnt}")
    # Save progress
    Path("/tmp/fb_chrome_progress.json").write_text(json.dumps({"header":header_obj, "count":len(posts), "posts":posts}, indent=2, ensure_ascii=False), encoding="utf-8")
    if new==0 and it>5:
        # check if body len stopped growing
        if it>10:
            print("No new for 5 iterations, checking if more to load")
            # Try clicking Ver más publicaciones if exists
            clicked=cdp.eval("""
(() => {
  const btns=Array.from(document.querySelectorAll('[role="button"], a')).filter(b=>b.innerText && (b.innerText.includes('Ver más') || b.innerText.includes('See more') || b.innerText.includes('Mostrar más')));
  let c=0;
  for(const b of btns.slice(0,3)){
    try{ b.click(); c++; }catch(e){}
  }
  return c;
})()
""")
            print(f"  clicked Ver más {clicked}")
            time.sleep(3)
            # check again after click
            body2=cdp.eval("document.body.innerText")
            if body2 and len(body2) == len(body):
                print("  still no growth, breaking")
                if it>15:
                    break
    if len(posts)>=150:
        break

print(f"FB DONE total {len(posts)}")
Path("/tmp/fb_chrome_all.json").write_text(json.dumps({"header":header_obj, "posts":posts}, indent=2, ensure_ascii=False), encoding="utf-8")
print("Saved FB")
# Also try to get page About info more detailed
about=cdp.eval("""
(() => {
  // Try to click Información tab
  const infoTab=Array.from(document.querySelectorAll('a')).find(a=>a.innerText.trim()==='Información');
  if(infoTab) infoTab.click();
  return 'clicked info';
})()
""")
print("About click",about)
time.sleep(4)
about_text=cdp.eval("document.body.innerText.slice(0,4000)")
print("About text",about_text[:2000] if about_text else "")
Path("/tmp/fb_about.txt").write_text(about_text or "", encoding="utf-8")
cdp.close()
