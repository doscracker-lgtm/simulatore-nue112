"""Preparazione dati in GitHub Actions. Nessuna esecuzione Python richiesta agli studenti."""
import csv,io,json,re,sqlite3,urllib.request,urllib.parse,zipfile,unicodedata,datetime,os,tempfile
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'site'/'data';OUT.mkdir(exist_ok=True)
PAGE='https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/Accedi-ai-servizi-di-dowload-massivo-in-Open-data/'
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',s or '') if unicodedata.category(c)!='Mn').lower().strip()
def key(s):return re.sub('[^a-z0-9]','',norm(s))
class Links(HTMLParser):
    def __init__(self):super().__init__();self.result=[];self.href=None;self.text=[]
    def handle_starttag(self,t,a):
        if t=='a':self.href=dict(a).get('href');self.text=[]
    def handle_data(self,d):
        if self.href:self.text.append(d)
    def handle_endtag(self,t):
        if t=='a' and self.href:self.result.append((self.href,' '.join(self.text)));self.href=None

def read(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'NUE112-Study-DataBuilder/1.0'}),timeout=240)
def field(row,names):
    for n in names:
        v=row.get(key(n),'')
        if v.strip():return v.strip()
    return ''
def main():
    p=Links()
    with read(PAGE) as r:p.feed(r.read().decode('utf-8',errors='replace'))
    urls={}
    for href,label in p.result:
        if 'campania' in norm(label):
            for kind in ['stradario','indirizzario']:
                if kind in norm(label):urls[kind]=urllib.parse.urljoin(PAGE,href)
    if len(urls)!=2:raise RuntimeError('Download regionali non individuati. Non pubblico un database vuoto.')
    config=json.loads((ROOT/'tools'/'columns.json').read_text())
    diagnostics=[];count=0
    with tempfile.TemporaryDirectory() as tmp:
        c=sqlite3.connect(str(Path(tmp)/'rows.db'));c.execute('create table r(city text,street text,num text,lat real,lon real)')
        for kind,url in urls.items():
            dest=Path(tmp)/(kind+'.zip')
            with read(url) as src,open(dest,'wb') as dst:
                while chunk:=src.read(1024*1024):dst.write(chunk)
            if not zipfile.is_zipfile(dest):raise RuntimeError(kind+': risposta non ZIP')
            with zipfile.ZipFile(dest) as z:
                for name in z.namelist():
                    if not name.lower().endswith(('.txt','.csv')):continue
                    with z.open(name) as raw:
                        f=io.TextIOWrapper(raw,encoding='utf-8-sig',errors='replace',newline='');first=f.readline();sep=max([';',',','\t','|'],key=first.count);headers=next(csv.reader([first],delimiter=sep));keys=[key(x) for x in headers]
                        diagnostics.append({'file':name,'columns':headers});(OUT/'schema-diagnostic.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2))
                        citykeys=set(map(key,config['city']));streetkeys=set(map(key,config['street']))
                        if not citykeys.intersection(keys) or not streetkeys.intersection(keys):raise RuntimeError('Schema ufficiale non riconosciuto: consultare artifact schema-diagnostic e correggere tools/columns.json. Nessuna pubblicazione eseguita.')
                        batch=[]
                        for values in csv.reader(f,delimiter=sep):
                            row=dict(zip(keys,values));city=field(row,config['city']);street=field(row,config['street']);dug=field(row,config['dug'])
                            if not city or not street:continue
                            if dug and not norm(street).startswith(norm(dug)+' '):street=dug+' '+street
                            num=field(row,config['number']) if kind=='indirizzario' else '';esp=field(row,config['suffix'])
                            if num and esp:num+='/'+esp
                            try:
                                lat=float(field(row,config['lat']).replace(',','.'));lon=float(field(row,config['lon']).replace(',','.'))
                                if not (39<lat<43 and 12<lon<17):lat=lon=None
                            except ValueError:lat=lon=None
                            batch.append((city,street,num,lat,lon))
                            if len(batch)>=10000:c.executemany('insert into r values(?,?,?,?,?)',batch);count+=len(batch);batch=[];c.commit()
                        if batch:c.executemany('insert into r values(?,?,?,?,?)',batch);count+=len(batch);c.commit()
        if not count:raise RuntimeError('Nessun record acquisito.')
        c.execute('create index idx on r(city,street,num)');version=datetime.datetime.now(datetime.timezone.utc).isoformat();cities=[]
        for i,(city,) in enumerate(c.execute('select distinct city from r order by city').fetchall()):
            streets={}
            for street,num,lat,lon in c.execute('select distinct street,num,lat,lon from r where city=? order by street,length(num),num',(city,)):
                s=streets.setdefault(street,{'name':street,'numbers':[]})
                if num:s['numbers'].append({'n':num,'lat':lat,'lon':lon})
            file=f'city-{i:04d}.json';(OUT/file).write_text(json.dumps({'city':city,'streets':list(streets.values())},ensure_ascii=False,separators=(',',':')),encoding='utf-8');cities.append({'id':str(i),'name':city,'file':file})
        c.close()
    (OUT/'catalog.json').write_text(json.dumps({'version':version,'cities':cities,'source':'ANNCSU','records':count,'urls':urls},ensure_ascii=False),encoding='utf-8')
    size=sum(p.stat().st_size for p in (ROOT/'site').rglob('*') if p.is_file())
    if size>900*1024*1024:raise RuntimeError('Sito oltre soglia prudenziale 900 MiB: suddividere gli archivi prima della pubblicazione.')
    print(json.dumps({'cities':len(cities),'records':count,'bytes':size}))
if __name__=='__main__':main()
