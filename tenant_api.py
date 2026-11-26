#!/usr/bin/env python3
import json,os,subprocess,time,urllib.request,urllib.error,secrets
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
BASE=os.environ.get("TENANT_BASE", os.path.expanduser("~/.sigil-tenant"))
TENANTS=os.environ.get("TENANT_TENANTS_DIR", os.path.join(os.path.dirname(BASE), "sigil-tenants"))
BD=BASE; ST=os.path.join(BD,"tenants.json"); TF=os.path.join(BD,"admin.token"); FCF=os.path.join(BD,"fc.token")
HOST=os.environ.get("TENANT_API_HOST","127.0.0.1"); PORT=int(os.environ.get("TENANT_API_PORT","18400"))
ALLOW_PRIVATE=os.environ.get("TENANT_ALLOW_PRIVATE","0")=="1"
FC_HOST=os.environ.get("FC_HOST","127.0.0.1"); FC_PORT=int(os.environ.get("FC_PORT","18500"))
PRICES={"receipts":0.001,"chain_verify":0.001,"verify":0.005,"sandbox":0.02,"health":0.0}
OPENAPI={"openapi":"3.0.3","info":{"title":"SIGIL Tenant API","version":"4.0"},
 "paths":{"/health":{"get":{}},"/tenants":{"get":{},"post":{}},"/tenants/{t}":{"delete":{}},
  "/t/{t}/receipts":{"get":{}},"/t/{t}/chain/verify":{"get":{}},"/t/{t}/verify":{"post":{}},
  "/t/{t}/usage":{"get":{}},"/t/{t}/billing":{"get":{}},"/t/{t}/sandbox":{"post":{}}}}
def rd(p,d=""):
    try: return open(p).read().strip()
    except Exception: return d
def load():
    try: return json.load(open(ST))
    except Exception: return {}
def save(d): json.dump(d,open(ST,"w"),indent=2)
def migrate():
    d=load(); ch=False
    for t in d:
        if "api_key" not in d[t]: d[t]["api_key"]=secrets.token_urlsafe(24); ch=True
        d[t].setdefault("usage",{})
    if ch: save(d)
def bump(n,ep):
    d=load(); t=d.get(n)
    if t is None: return
    t.setdefault("usage",{}); t["usage"][ep]=t["usage"].get(ep,0)+1; save(d)
def rtoken(n): return rd(os.path.join(TENANTS,n,"keys","control_token"))
def proxy(port,path,method="GET",body=None,token=None,host="127.0.0.1",timeout=10,extra_headers=None):
    h={"Content-Type":"application/json"}
    if token: h["X-SIGIL-Token"]=token
    if extra_headers: h.update(extra_headers)
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request("http://%s:%d%s"%(host,port,path),data=data,method=method,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return r.status,json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code,json.loads(e.read() or b"{}")
        except Exception: return e.code,{"error":str(e)}
    except Exception as e: return 502,{"error":str(e)[:80]}
def health(port): return proxy(port,"/health")[1]
SANDBOX_IMG=os.environ.get("SANDBOX_IMG","alpine:latest")
def run_container(cmd,timeout=20):
    args=["timeout",str(timeout+3),"docker","run","--rm","--network=none","--read-only","--memory","256m","--pids-limit","128","--cap-drop","ALL","--security-opt","no-new-privileges","--user","65534:65534","--tmpfs","/tmp:rw,size=64m","-w","/tmp",SANDBOX_IMG,"sh","-c",cmd]
    t=time.time()
    try:
        pr=subprocess.run(args,capture_output=True,timeout=timeout+8)
        return {"ok":pr.returncode==0,"out":(pr.stdout+pr.stderr).decode("utf-8","replace")[-4000:],"ms":int((time.time()-t)*1000),"rc":pr.returncode}
    except Exception as e:
        return {"ok":False,"error":str(e)[:120],"ms":int((time.time()-t)*1000)}

def invoice_tenant(n):
    d=load(); t=d.get(n)
    if not t: return None
    us=t.get("usage",{}); billed=t.get("billed",{})
    items={}; total=0.0
    for k,v in us.items():
        dd=v-billed.get(k,0)
        if dd>0:
            amt=round(dd*PRICES.get(k,0.0),4); items[k]={"count":dd,"price":PRICES.get(k,0.0),"amount":amt}; total+=amt
    inv={"id":"inv-"+secrets.token_hex(6),"created":int(time.time()),"currency":"EUR","items":items,"total":round(total,4),"status":"pending","stripe":"not_configured"}
    key=os.environ.get("STRIPE_SECRET_KEY","")
    if key:
        try:
            import stripe
            stripe.api_key=key
            cid=t.get("stripe_customer")
            if not cid:
                cu=stripe.Customer.create(name=n,metadata={"tenant":n}); cid=cu["id"]; t["stripe_customer"]=cid
            if total>0:
                stripe.InvoiceItem.create(customer=cid,amount=int(round(total*100)),currency="eur",description="SIGIL usage "+n)
                si=stripe.Invoice.create(customer=cid,auto_advance=True,collection_method="send_invoice",days_until_due=7)
                inv["stripe"]="created"; inv["stripe_invoice"]=si["id"]
        except Exception as e:
            inv["stripe"]="error: "+str(e)[:100]
    t["billed"]={k:v for k,v in us.items()}
    t.setdefault("invoices",[]).append(inv)
    d[n]=t; save(d)
    return inv

SHARD_HOST=os.environ.get("SHARD_HOST","127.0.0.1"); SHARD_PORT=int(os.environ.get("SHARD_PORT","7150")); SHARD_TOKEN_FILE=os.path.join(BD,"shard.token")
def run_vsock(n,cmd,timeout=20):
    tokn=rd(SHARD_TOKEN_FILE)
    if not tokn:
        r=run_container(cmd); r["_sbx"]="container"; return r
    try:
        key="tn-"+n; h={"Content-Type":"application/json","X-Token":tokn}
        urllib.request.urlopen(urllib.request.Request("http://%s:%d/v1/workspaces/open"%(SHARD_HOST,SHARD_PORT),data=json.dumps({"key":key}).encode(),headers=h,method="POST"),timeout=8).read()
        r=urllib.request.urlopen(urllib.request.Request("http://%s:%d/v1/workspaces/%s/exec"%(SHARD_HOST,SHARD_PORT,key),data=json.dumps({"cmd":cmd,"timeout":timeout}).encode(),headers=h,method="POST"),timeout=timeout+8)
        d=json.loads(r.read() or b"{}")
        return {"ok":d.get("ok",False),"rc":d.get("rc"),"out":d.get("out",""),"ms":d.get("ms"),"receipt":d.get("receipt"),"_sbx":"firecracker-vsock"}
    except Exception as e:
        r=run_container(cmd); r["_sbx"]="container"; r["vsock_err"]=str(e)[:80]; return r

def _ai_dir(n):
    d=os.path.join(TENANTS,n,"ai_act"); os.makedirs(d,exist_ok=True); return d
def ai_act_log(n,actor,action,tool=None,risk_class="minimal",human_oversight=False,decision=None,summary=None):
    import hashlib
    d=_ai_dir(n); lf=d+"/audit_trail.jsonl"; cf=d+"/chain_head.json"
    try: prev=json.load(open(cf)).get("head","GENESIS")
    except Exception: prev="GENESIS"
    rec={"id":secrets.token_hex(8),"ts":int(time.time()),"actor":actor,"action":action,"tool":tool,"risk_class":risk_class,"human_oversight":human_oversight,"decision":decision,"summary":(summary or "")[:500],"prev_hash":prev}
    body=json.dumps(rec,sort_keys=True,ensure_ascii=False)
    rec["hash"]=hashlib.sha256((prev+body).encode()).hexdigest()
    open(lf,"a").write(json.dumps(rec,ensure_ascii=False)+"\n")
    open(cf,"w").write(json.dumps({"head":rec["hash"]}))
    return rec["hash"]
def ai_act_verify(n):
    import hashlib
    lf=_ai_dir(n)+"/audit_trail.jsonl"
    if not os.path.exists(lf): return {"ok":True,"records":0,"head":"GENESIS"}
    prev="GENESIS"; k=0
    for line in open(lf):
        line=line.strip()
        if not line: continue
        r=json.loads(line); st=r.pop("hash"); body=json.dumps(r,sort_keys=True,ensure_ascii=False)
        if hashlib.sha256((prev+body).encode()).hexdigest()!=st or r.get("prev_hash")!=prev: return {"ok":False,"broken_at":k}
        prev=st; k+=1
    return {"ok":True,"records":k,"head":prev}
def ai_act_pack(n):
    lf=_ai_dir(n)+"/audit_trail.jsonl"; ev=[]; byr={}; bya={}
    if os.path.exists(lf):
        for line in open(lf):
            line=line.strip()
            if line: ev.append(json.loads(line))
    for r in ev:
        byr[r.get("risk_class","?")]=byr.get(r.get("risk_class","?"),0)+1
        bya[r.get("actor","?")]=bya.get(r.get("actor","?"),0)+1
    t=load().get(n) or {}
    try: gate=proxy(t.get("base",0),"/chain/verify",token=rtoken(n))[1] if t else {}
    except Exception: gate={}
    return {"tenant":n,"generated":int(time.time()),"standard":"EU AI Act Art.12/19/26/72","retention_days":180,"total_events":len(ev),"by_risk_class":byr,"by_actor":bya,"chain_verify":ai_act_verify(n),"receipts_chain":gate,"events_tail":ev[-20:]}

class H(BaseHTTPRequestHandler):
    def _j(self,c,o):
        b=json.dumps(o,ensure_ascii=False).encode(); self.send_response(c); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b))); self.end_headers(); self.wfile.write(b)
    def _ip_ok(self):
        ip=self.client_address[0]
        if ip.startswith("127.") or ip in ("::1",""):
            return True
        return ALLOW_PRIVATE and (ip.startswith("10.") or ip.startswith("100.") or ip.startswith("192.168."))
    def _admin(self): return bool(rd(TF)) and self.headers.get("X-Admin-Token","")==rd(TF)
    def _tkey(self,n):
        t=load().get(n); return bool(t) and self.headers.get("X-Api-Key","")==t.get("api_key","")
    def _body(self):
        n=int(self.headers.get("Content-Length","0") or 0)
        try: return json.loads(self.rfile.read(n) or b"{}")
        except Exception: return {}
    def do_GET(self):
        if not self._ip_ok(): return self._j(403,{"error":"ip"})
        p=self.path.split("?")[0]
        if p=="/openapi.json": return self._j(200,OPENAPI)
        if p=="/health": return self._j(200,{"ok":True,"tenants":len(load())})
        if p=="/pricing": return self._j(200,{"currency":"EUR","prices":PRICES})
        if p=="/tenants":
            out={}
            for n,t in load().items():
                b=t["base"]; out[n]={"base":b,"chain":t.get("chain"),"has_key":bool(t.get("api_key")),"gate":health(b),"verify":health(b+1),"anchor":health(b+2)}
            return self._j(200,out)
        if p.startswith("/t/"):
            parts=p.strip("/").split("/"); n=parts[1]
            if not self._tkey(n): return self._j(401,{"error":"unauthorized"})
            t=load()[n]; base=t["base"]; ct=rtoken(n)
            if p.endswith("/receipts"):
                bump(n,"receipts"); q=("?"+self.path.split("?")[1]) if "?" in self.path else ""
                return self._j(*proxy(base,"/receipts"+q,token=ct))
            if p.endswith("/chain/verify"): bump(n,"chain_verify"); return self._j(*proxy(base,"/chain/verify",token=ct))
            if p.endswith("/audit/verify"): return self._j(200,ai_act_verify(n))
            if p.endswith("/audit"): return self._j(200,ai_act_pack(n))
            if p.endswith("/usage"): return self._j(200,{"tenant":n,"usage":t.get("usage",{}),"base":base,"chain":t.get("chain")})
            if p.endswith("/billing"):
                us=t.get("usage",{}); items={}; total=0.0
                for k,v in us.items():
                    amt=round(v*PRICES.get(k,0.0),4); items[k]={"count":v,"price":PRICES.get(k,0.0),"amount":amt}; total+=amt
                return self._j(200,{"tenant":n,"currency":"EUR","items":items,"total":round(total,4)})
            if p.endswith("/health"): bump(n,"health"); return self._j(200,{"gate":health(base),"verify":health(base+1),"anchor":health(base+2)})
            return self._j(404,{"error":"unknown"})
        self._j(404,{"error":"not found"})
    def do_POST(self):
        if not self._ip_ok(): return self._j(403,{"error":"ip"})
        p=self.path.split("?")[0]
        if p=="/tenants":
            if not self._admin(): return self._j(401,{"error":"unauthorized"})
            req=self._body(); name=(req.get("name") or "").strip().lower().replace(" ","-")
            if not name: return self._j(400,{"error":"name"})
            d=load()
            if name in d: return self._j(409,{"error":"exists","base":d[name]["base"],"chain":d[name].get("chain")})
            base=int(req.get("base") or (18400+10*(len(d)+1)))
            try: subprocess.run(["bash",os.path.join(BD,"tenant_up.sh"),name,str(base)],timeout=45,capture_output=True)
            except Exception as e: return self._j(500,{"error":str(e)[:80]})
            key=secrets.token_urlsafe(24)
            d[name]={"base":base,"chain":name+"-1","created":int(time.time()),"api_key":key,"usage":{}}
            save(d)
            return self._j(201,{"tenant":name,"base":base,"chain":name+"-1","api_key":key,"gate":health(base),"verify":health(base+1),"anchor":health(base+2)})
        if p.startswith("/t/") and p.endswith("/verify"):
            n=p.strip("/").split("/")[1]
            if not self._tkey(n): return self._j(401,{"error":"unauthorized"})
            bump(n,"verify"); t=load()[n]
            return self._j(*proxy(t["base"]+1,"/verify",method="POST",body=self._body(),token=rtoken(n)))
        if p.startswith("/t/") and p.endswith("/sandbox"):
            n=p.strip("/").split("/")[1]
            if not self._tkey(n): return self._j(401,{"error":"unauthorized"})
            body=self._body(); cmd=body.get("cmd") or "id"
            res=run_vsock(n,cmd); sbx=res.pop("_sbx","container")
            bump(n,"sandbox")
            try: ai_act_log(n,"tenant","sandbox_exec",tool=sbx,risk_class="limited",summary=cmd)
            except Exception: pass
            return self._j(200,{"tenant":n,"sandbox":sbx,"result":res})
        if p.startswith("/t/") and p.endswith("/invoice"):
            n=p.strip("/").split("/")[1]
            if not self._tkey(n): return self._j(401,{"error":"unauthorized"})
            inv=invoice_tenant(n)
            return self._j(200, inv or {"error":"no tenant"})
        if p.startswith("/t/") and p.endswith("/audit-event"):
            n=p.strip("/").split("/")[1]
            if not self._tkey(n): return self._j(401,{"error":"unauthorized"})
            b=self._body()
            h=ai_act_log(n,b.get("actor","tenant"),b.get("action","event"),tool=b.get("tool"),risk_class=b.get("risk_class","minimal"),human_oversight=bool(b.get("human_oversight",False)),decision=b.get("decision"),summary=b.get("summary"))
            return self._j(200,{"logged":h})
        if p.startswith("/t/") and p.endswith("/attest"):
            n=p.strip("/").split("/")[1]
            if not self._tkey(n): return self._j(401,{"error":"unauthorized"})
            b=self._body(); arts=b.get("artifacts") or []
            summ="%s %s job=%s artifacts=%d"%(b.get("source","?"),b.get("kind","?"),b.get("job_id","-"),len(arts))
            h=ai_act_log(n,"attestor",b.get("kind","attest"),tool=b.get("source","?"),risk_class=b.get("risk_class","limited"),decision="attested",summary=summ)
            d=load(); t=d.get(n,{}); t.setdefault("attestations",[]).append({"id":h,"ts":int(time.time()),"source":b.get("source"),"kind":b.get("kind"),"job_id":b.get("job_id"),"partition":b.get("partition"),"artifacts":arts,"meta":b.get("meta",{})}); d[n]=t; save(d)
            return self._j(200,{"attested":h,"chain_head":ai_act_verify(n).get("head"),"artifacts":len(arts)})
        self._j(404,{"error":"not found"})
    def do_DELETE(self):
        if not self._ip_ok(): return self._j(403,{"error":"ip"})
        if not self._admin(): return self._j(401,{"error":"unauthorized"})
        n=self.path.rstrip("/").split("/")[-1]; d=load()
        if n not in d: return self._j(404,{"error":"no tenant"})
        rt=os.path.join(TENANTS,n)
        for f in ("gate.pid","verify.pid","anchor.pid"):
            pp=os.path.join(rt,f)
            if os.path.exists(pp):
                try: os.kill(int(open(pp).read().strip()),15)
                except Exception: pass
        d.pop(n,None); save(d); return self._j(200,{"stopped":n})
    def log_message(self,*a): pass
if __name__=="__main__":
    migrate(); s=ThreadingHTTPServer((HOST,PORT),H); print("tenant-api v4 %s:%d"%(HOST,PORT),flush=True); s.serve_forever()
