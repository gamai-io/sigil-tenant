#!/usr/bin/env python3
import json,os,subprocess,urllib.request
BD=os.environ.get("TENANT_BASE", os.path.expanduser("~/.sigil-tenant"))
TENANTS=os.environ.get("TENANT_TENANTS_DIR", os.path.join(os.path.dirname(BD), "sigil-tenants"))
PY=os.environ.get("TENANT_PY", "python3")
CODE=os.environ.get("SIGIL_CODE", os.path.dirname(os.path.abspath(__file__)))
def health(p):
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/health"%p,timeout=2) as r: return True
    except Exception: return False
def start(tenant,svc,port,extra):
    rt=os.path.join(TENANTS,tenant)
    env=dict(os.environ); env["PYTHONPATH"]=CODE
    env.update({"SIGIL_DATA":rt+"/data","SIGIL_EFFECTS":rt+"/effects","SIGIL_PUB_DIR":rt+"/keys/pub",
      "SIGIL_CONTROL_TOKEN_FILE":rt+"/keys/control_token","SIGIL_APPROVER_TOKEN_FILE":rt+"/keys/approver_token",
      "SIGIL_CHAIN_ID":tenant+"-1","SIGIL_PORT":str(port)})
    env.update(extra)
    log=open(rt+"/%s.log"%svc,"a")
    p=subprocess.Popen([PY,"-m","sigil."+svc],env=env,stdout=log,stderr=log,start_new_session=True)
    open(rt+"/%s.pid"%svc,"w").write(str(p.pid))
def main():
    try: d=json.load(open(BD+"/tenants.json"))
    except Exception: return
    for t,v in d.items():
        base=v["base"]; rt=os.path.join(TENANTS,t)
        if not os.path.isdir(rt): continue
        specs=[("gate",base,{"SIGIL_PRIV_PATH":rt+"/keys/kms/gate-ed25519-1.pem","SIGIL_KEY_ID":"gate-ed25519-1","SIGIL_ANCHOR_KEY_ID":"anchor-ed25519-1"}),
               ("verify",base+1,{}),
               ("anchor",base+2,{"SIGIL_PRIV_PATH":rt+"/keys/kms/anchor-ed25519-1.pem","SIGIL_KEY_ID":"anchor-ed25519-1","SIGIL_ANCHOR_ALLOW_LOCAL":"1","SIGIL_GATE":"http://127.0.0.1:%d"%base})]
        for svc,port,extra in specs:
            if not health(port):
                start(t,svc,port,extra); print("restart %s %s :%d"%(t,svc,port))
if __name__=="__main__": main()
