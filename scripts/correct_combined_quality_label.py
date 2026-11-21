"""Correct this newly published digest in place; creates no additional message."""
import json,hashlib,secrets,ssl,sqlite3,urllib.request
from pathlib import Path
from datetime import datetime
from sector_heatmap.combined_reports import PRIVATE,screen_section,render
from sector_heatmap.workspaces import private_write
from sector_heatmap.market_calendar import IST
ident="combined-0b0e2703b7f585f880fc160d"
config=json.loads((PRIVATE/"config.json").read_text())
receipt=json.loads((PRIVATE/"combined-reports"/(ident+".receipt.json")).read_text())
if receipt.get("message_id")!=72 or receipt.get("chat_id")!=-1003930561430:raise ValueError("Unexpected report destination")
with sqlite3.connect(PRIVATE/"combined-outbox.sqlite3") as db:
 row=db.execute("select payload from events where id=?",(ident,)).fetchone();event=json.loads(row[0])
 result=json.loads((PRIVATE/"combined-reports/screener-09dfa4f6b89ccd90.json").read_text())
 snapshot=event["snapshot"];original=json.dumps(event)
 snapshot["sections"]=[(name,screen_section(result,datetime.fromisoformat(snapshot["generated"])) if name=="SCREENER" else section) for name,section in snapshot["sections"]]
 image=PRIVATE/"combined-reports"/(ident+"-quality-corrected.png");render(snapshot,image)
 caption=event["public_caption"]+"\nScreener broker evidence: DELAYED."
 boundary="SectorPulse"+secrets.token_hex(12)
 values={"chat_id":str(receipt["chat_id"]),"message_id":str(receipt["message_id"]),"media":json.dumps({"type":"photo","media":"attach://photo","caption":caption})}
 parts=[]
 for key,value in values.items():
  parts.append(("--"+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+value+"\r\n").encode())
 data=image.read_bytes()
 parts.append(("--"+boundary+'\r\nContent-Disposition: form-data; name="photo"; filename="combined-report.png"\r\nContent-Type: image/png\r\n\r\n').encode()+data+b"\r\n")
 parts.append(("--"+boundary+"--\r\n").encode())
 request=urllib.request.Request("https://api.telegram.org/bot"+config["telegram"]["token"]+"/editMessageMedia",data=b"".join(parts),headers={"Content-Type":"multipart/form-data; boundary="+boundary},method="POST")
 with urllib.request.urlopen(request,timeout=20,context=ssl.create_default_context()) as response:ack=json.load(response)
 if not ack.get("ok") or ack["result"]["message_id"]!=72:raise ValueError("Report correction was not confirmed")
 private_write(PRIVATE/"combined-reports"/(ident+".before-quality-correction.json"),original)
 event.update(image=str(image),image_sha256=hashlib.sha256(data).hexdigest(),public_caption=caption)
 db.execute("update events set payload=? where id=?",(json.dumps(event),ident));db.commit()
 private_write(image.with_suffix(".json"),json.dumps(snapshot))
 correction={"accepted":True,"message_id":ack["result"]["message_id"],"chat_id":ack["result"]["chat"]["id"],"new_message_created":False,"correction":"Explicit DELAYED broker evidence label"}
 private_write(PRIVATE/"combined-reports"/(ident+".correction-receipt.json"),json.dumps(correction))
 print(json.dumps(correction))
