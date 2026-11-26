"""Catalog-only search ranking. Suggestions never substitute a selected contract."""
import re
def normalized(value):return re.sub(r'[^A-Z0-9]','',str(value).upper())
def one_edit(a,b):
 if abs(len(a)-len(b))>1:return False
 if a==b:return True
 if len(a)==len(b):
  diff=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
  return len(diff)==1 or len(diff)==2 and diff[1]==diff[0]+1 and a[diff[0]]==b[diff[1]] and a[diff[1]]==b[diff[0]]
 if len(a)>len(b):a,b=b,a
 i=j=changes=0
 while i<len(a) and j<len(b):
  if a[i]==b[j]:i+=1;j+=1
  else:
   changes+=1;j+=1
   if changes>1:return False
 return True
def ranked(rows,query,limit=80):
 query=str(query or '').strip().upper();words=query.split();needle=normalized(query);hits=[];near=[]
 for row in rows:
  tokens=[str(row.get(k) or '').upper() for k in ('underlying','symbol','description')]
  text=' '.join(tokens)
  if not words or all(word in text for word in words):
   code=normalized(row.get('underlying') or row['symbol'].split(':')[-1])
   score=0 if needle and needle==code else 1 if needle and code.startswith(needle) else 2
   hits.append((score,row))
  elif len(needle)>=4 and len(words)==1:
   code=normalized(row.get('underlying') or row['symbol'].split(':')[-1])
   if one_edit(needle,code):near.append((3,dict(row,suggested=True)))
 result=hits if hits else near
 return [row for _,row in sorted(result,key=lambda item:(item[0],item[1].get('expiry') or 0,item[1]['symbol']))[:limit]]
