import json,sys
# 每个源只看前 N 个条目（默认 1，即按名字长度排序后最像本体的那个）
N=int(sys.argv[2]) if len(sys.argv)>2 else 1
for l in open(sys.argv[1]):
    try: r=json.loads(l)
    except: print(l); continue
    d=r.pop('details',[])
    print(r.get('name'), 'http',r.get('search_http'), 'subjects',r.get('subjects'), 'total_s',r.get('total_s'), r.get('search',''))
    for x in d[:N]: print('   ', x.get('n'), '| raw:', x.get('ch_raw'), '| chips:', x.get('chips'), '| eps:', x.get('eps'), x.get('err',''))
