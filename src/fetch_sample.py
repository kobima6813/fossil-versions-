import asyncio, aiohttp, json, random, sys, time, urllib.parse, re
N=int(sys.argv[1]); OUT=sys.argv[2]; SEED=int(sys.argv[3]) if len(sys.argv)>3 else 1; CONC=int(sys.argv[4]) if len(sys.argv)>4 else 48
names=json.load(open('package/names.json'))  # from: npm pack all-the-package-names@2.0.2622 && tar xzf *.tgz
random.seed(SEED); sample=random.sample(names,N)
done=set()
try:
    for l in open(OUT):
        try: done.add(json.loads(l)['name'])
        except: pass
except FileNotFoundError: pass
sample=[s for s in sample if s not in done]
MARK=re.compile(r'claude|cursor|copilot|chatgpt|gpt-|lovable|bolt\.new|v0\.dev|vibe.?cod|generated (with|by) (ai|an ai)|codex|windsurf|gemini', re.I)
def slim(name,d):
    t=d.get('time',{}) or {}
    vs=d.get('versions',{}) or {}
    vt=[(t[v],v) for v in vs if v in t]
    vt.sort()
    def deps(v):
        o=vs.get(v,{})
        return {'d':o.get('dependencies') or {}, 'v':o.get('devDependencies') or {}, 'p':o.get('peerDependencies') or {}}
    first=vt[0][1] if vt else None; last=vt[-1][1] if vt else None
    rd=d.get('readme') or ''
    r={'name':name,'created':t.get('created'),'modified':t.get('modified'),'nv':len(vs),'first':first,'first_t':vt[0][0] if vt else None,'last':last,'last_t':vt[-1][0] if vt else None,
       'fd':deps(first) if first else None,'ld':deps(last) if last and last!=first else None,
       'rl':len(rd),'mark':sorted(set(m.group(0).lower() for m in MARK.finditer(rd)))[:6],'repo':bool(d.get('repository')),'nm':len(d.get('maintainers') or []),
       'unpub':bool(t.get('unpublished')),'desc':(d.get('description') or '')[:80]}
    return r
async def one(s,sem,name,f):
    url='https://registry.npmjs.org/'+urllib.parse.quote(name,safe='@')
    for att in range(3):
        try:
            async with sem:
                async with s.get(url,timeout=aiohttp.ClientTimeout(total=40)) as r:
                    if r.status==404: f.write(json.dumps({'name':name,'err':404})+'\n'); return
                    if r.status!=200:
                        await asyncio.sleep(1+att*2); continue
                    cl=int(r.headers.get('content-length') or 0)
                    if cl>12_000_000: f.write(json.dumps({'name':name,'err':'big','cl':cl})+'\n'); return
                    d=await r.json(content_type=None)
            f.write(json.dumps(slim(name,d))+'\n'); return
        except Exception as e:
            await asyncio.sleep(1+att*2)
    f.write(json.dumps({'name':name,'err':'fail'})+'\n')
async def main():
    sem=asyncio.Semaphore(CONC); t0=time.time()
    conn=aiohttp.TCPConnector(limit=CONC)
    with open(OUT,'a') as f:
        async with aiohttp.ClientSession(connector=conn) as s:
            B=2000
            for i in range(0,len(sample),B):
                await asyncio.gather(*[one(s,sem,n,f) for n in sample[i:i+B]]); f.flush()
                print(i+B, round(time.time()-t0), flush=True)
asyncio.run(main())
