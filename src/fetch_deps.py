import asyncio, aiohttp, json, sys, urllib.parse, re, os
names=[l.strip() for l in open(sys.argv[1]) if l.strip()]; OUT=sys.argv[2]
done=set()
if os.path.exists(OUT):
    for l in open(OUT):
        try: done.add(json.loads(l)['name'])
        except: pass
names=[n for n in names if n not in done]
STABLE=re.compile(r'^\d+\.\d+\.\d+$')
async def one(s,sem,name,f):
    url='https://registry.npmjs.org/'+urllib.parse.quote(name,safe='@')
    for att in range(3):
        try:
            async with sem:
                async with s.get(url,timeout=aiohttp.ClientTimeout(total=120)) as r:
                    if r.status!=200:
                        if r.status==404: f.write(json.dumps({'name':name,'err':404})+'\n'); return
                        await asyncio.sleep(2); continue
                    d=await r.json(content_type=None)
            t=d.get('time',{}) or {}
            vs={v:t[v] for v in (d.get('versions') or {}) if v in t and STABLE.match(v)}
            f.write(json.dumps({'name':name,'vs':vs,'created':t.get('created')})+'\n'); return
        except Exception as e:
            await asyncio.sleep(2)
    f.write(json.dumps({'name':name,'err':'fail'})+'\n')
async def main():
    sem=asyncio.Semaphore(12)
    with open(OUT,'a') as f:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=12)) as s:
            for i in range(0,len(names),300):
                await asyncio.gather(*[one(s,sem,n,f) for n in names[i:i+300]]); f.flush(); print(i,flush=True)
asyncio.run(main())
