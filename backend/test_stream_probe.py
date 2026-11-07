import httpx, time, json
start=time.perf_counter()
first=None
chunks=0
with httpx.Client(timeout=90) as client:
    with client.stream('POST','http://127.0.0.1:8018/api/v1/query/stream',json={'question':'What are the B.Tech fee details?','top_k':6}) as response:
        print('status',response.status_code)
        for line in response.iter_lines():
            if not line.startswith('data: '): continue
            event=json.loads(line[6:])
            if event['type']=='chunk':
                chunks+=1
                if first is None: first=time.perf_counter()-start
                print('chunk',repr(event['text'][:80]),'at',round(time.perf_counter()-start,2),'s')
            elif event['type'] in ('sources','done','error'):
                print('event',event['type'])
print('first_token_seconds',first,'chunks',chunks,'total_seconds',round(time.perf_counter()-start,2))
