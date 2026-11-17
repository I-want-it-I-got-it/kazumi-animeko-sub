import json,sys
for l in open(sys.argv[1]):
    try: r=json.loads(l)
    except: print(l); continue
    d=r.pop('details',[])
    print(json.dumps(r,ensure_ascii=False))
    for x in d[:5]: print('   ',json.dumps(x,ensure_ascii=False)[:330])
    if d: print('    subjects=',len(d),'sum s=', round(sum(x.get('s',0) for x in d),1), 'sum kb=', sum(x.get('kb',0) for x in d))
