"""Draft visual only. Values are illustrative; no market fetch or message delivery."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

W,H=1200,1540
im=Image.new("RGB",(W,H),"#EDF2F8")
d=ImageDraw.Draw(im)
FONT="/usr/share/fonts/truetype/dejavu/"
def font(size,bold=False):
 return ImageFont.truetype(FONT+("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),size)
def text(x,y,s,size=28,color="#203B55",bold=False):
 d.text((x,y),s,font=font(size,bold),fill=color)
def box(rect,fill,r=22,outline=None):
 d.rounded_rectangle(rect,radius=r,fill=fill,outline=outline,width=2)
def right(x,y,s,size=28,color="#203B55",bold=False):
 f=font(size,bold);d.text((x-d.textlength(s,font=f),y),s,font=f,fill=color)

box((36,36,1164,1504),"#FFFFFF",30)
d.rounded_rectangle((36,36,1164,270),radius=30,fill="#203B55")
d.rectangle((36,220,1164,270),fill="#203B55")
text(76,69,"SECTOR PULSE",25,"#FFFFFF",True)
box((831,65,1120,108),"#DCE8F4",12)
text(848,73,"DESIGN PREVIEW",19,"#203B55",True)
text(76,124,"Sector rotation",62,"#FFFFFF",True)
text(79,208,"A market snapshot, ready to share.",27,"#C9D9E9")
text(77,303,"SAMPLE DATA  /  NOT A LIVE MARKET REPORT",23,"#8A5B1F",True)
text(77,349,"Data as of: [date and time IST]",25,"#596E82")
right(1120,349,"Universe: NSE sectors",25,"#596E82")
d.line((77,403,1120,403),fill="#DFE7EF",width=2)
text(77,435,"6 of 9",43,"#167A71",True)
text(77,491,"sectors positive",23,"#596E82")
text(440,435,"AUTO",43,"#203B55",True)
text(440,491,"session leader",23,"#596E82")
text(810,435,"+0.65%",43,"#203B55",True)
text(810,491,"NIFTY 50 reference",23,"#596E82")
text(77,555,"Sector heatmap",33,"#203B55",True)
right(1120,565,"Session change (%)",23,"#596E82")
sectors=[("AUTO",1.82),("METAL",1.35),("REALTY",.96),("BANK",.74),("PHARMA",.42),("ENERGY",.18),("FMCG",-.22),("IT",-.68),("MEDIA",-1.14)]
for i,(name,val) in enumerate(sectors):
 col,row=i%3,i//3;x=77+col*356;y=615+row*145
 color=("#167A71" if val>1 else "#D5EDE6" if val>.5 else "#EAF5EF" if val>0 else "#FAEAE8" if val>-.5 else "#E8C0BD" if val>-.9 else "#B85860")
 ink="#FFFFFF" if val>1 or val<-.9 else "#203B55"
 box((x,y,x+332,y+125),color,15)
 text(x+22,y+18,name,23,ink,True)
 text(x+22,y+52,f"{val:+.2f}%",39,ink,True)
text(77,1080,"Relative to NIFTY 50",32,"#203B55",True)
right(1120,1090,"Percentage-point difference",21,"#596E82")
box((77,1139,583,1322),"#F1F7F6",18)
box((607,1139,1120,1322),"#FCF3F2",18)
text(100,1157,"LEADING",21,"#167A71",True)
text(633,1157,"LAGGING",21,"#A24751",True)
for idx,(name,val) in enumerate([("Auto",1.17),("Metal",.70),("Realty",.31)]):
 y=1194+idx*36;text(100,y,name,24)
 right(557,y,f"+{val:.2f} pp",24,"#167A71",True)
for idx,(name,val) in enumerate([("Media",-1.79),("IT",-1.33),("FMCG",-.87)]):
 y=1194+idx*36;text(633,y,name,24)
 right(1092,y,f"{val:.2f} pp",24,"#A24751",True)
d.line((77,1361,1120,1361),fill="#DFE7EF",width=2)
text(77,1384,"Illustrative layout only. All figures are fictional.",23,"#596E82")
text(77,1423,"Production version: verified snapshot, source and freshness label.",22,"#596E82")
out=Path(__file__).resolve().parents[1]/"docs/design/sector-rotation-notification-draft.png"
out.parent.mkdir(parents=True,exist_ok=True)
im.save(out,optimize=True)
print(str(out))

