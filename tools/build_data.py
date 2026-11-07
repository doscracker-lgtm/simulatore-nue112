"""ANNCSU builder: comuni via codice ISTAT; nessun indirizzo inventato."""
import csv,io,json,re,sqlite3,urllib.request,urllib.parse,zipfile,unicodedata,datetime,tempfile,traceback
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'site'/'data';OUT.mkdir(parents=True,exist_ok=True)
PAGE='https://www.anncsu.gov.it/it/consultazione-dellarchivio/open-data/Accedi-ai-servizi-di-dowload-massivo-in-Open-data/'
MUNICIPALITIES='https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json'
def norm(s):return ''.join(c for c in unicodedata.normalize('NFD',str(s or '')) if unicodedata.category(c)!='Mn').lower().strip()
def key(s):return re.sub('[^a-z0-9]','',norm(s))
def field(row,*names):
    for n in names:
        v=str(row.get(key(n),'') or '').strip()
        if v:return v
    return ''
def istat(s):
    s=str(s or '').strip()
    if s.endswith('.0'):s=s[:-2]
    return s.zfill(6) if s.isdigit() and len(s)<=6 else s
class Links(HTMLParser):
    def __init__(self):super().__init__();self.result=[];self.href=None;self.text=[]
    def handle_starttag(self,t,a):
        if t=='a':self.href=dict(a).get('href');self.text=[]
    def handle_data(self,d):
        if self.href:self.text.append(d)
    def handle_endtag(self,t):
        if t=='a' and self.href:self.result.append((self.href,' '.join(self.text)));self.href=None

def read(url):return urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'NUE112-Study-DataBuilder/2.0'}),timeout=240)
def records(path,diagnostics):
    with zipfile.ZipFile(path) as z:
        found=False
        for name in z.namelist():
            if not name.lower().endswith(('.csv','.txt')):continue
            found=True
            with z.open(name) as raw:
                f=io.TextIOWrapper(raw,encoding='utf-8-sig',errors='replace',newline='')
                first=f.readline();sep=max([';',',','\t','|'],key=first.count)
                headers=next(csv.reader([first],delimiter=sep));keys=[key(x) for x in headers]
                diagnostics.append({'file':name,'columns':headers})
                (OUT/'schema-diagnostic.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
                print('SCHEMA',name,json.dumps(headers,ensure_ascii=False),flush=True)
                for values in csv.reader(f,delimiter=sep):
                    if not values or not any(v.strip() for v in values):continue
                    yield dict(zip(keys,values))
        if not found:raise RuntimeError('Nessun CSV/TXT nel file ZIP '+str(path.name))
def coordinates(row):
    try:
        lat=float(field(row,'LATITUDINE','LAT','COORDINATA_Y').replace(',','.'))
        lon=float(field(row,'LONGITUDINE','LON','COORDINATA_X').replace(',','.'))
        if 39<lat<43 and 12<lon<17:return lat,lon
    except ValueError:pass
    return None,None

def main():
    diagnostics=[]
    with read(PAGE) as r:page=r.read().decode('utf-8',errors='replace')
    p=Links();p.feed(page);urls={}
    for href,label in p.result:
        if 'campania' in norm(label):
            for kind in ['stradario','indirizzario']:
                if kind in norm(label):urls[kind]=urllib.parse.urljoin(PAGE,href)
    if len(urls)!=2:raise RuntimeError('Link regionali non individuati nella pagina ANNCSU.')
    with read(MUNICIPALITIES) as r:municipalities=json.load(r)
    if not isinstance(municipalities,list):raise RuntimeError('Formato elenco Comuni non valido.')
    names={istat(m.get('codice')):m.get('nome') for m in municipalities if m.get('codice') and m.get('nome')}
    if not names:raise RuntimeError('Elenco Comuni vuoto: impossibile risolvere CODICE_ISTAT.')
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for kind,url in urls.items():
            print('DOWNLOAD',kind,flush=True)
            dest=tmp/(kind+'.zip')
            with read(url) as src,open(dest,'wb') as dst:
                while chunk:=src.read(1024*1024):dst.write(chunk)
            if not zipfile.is_zipfile(dest):raise RuntimeError(kind+': risposta non ZIP.')
        c=sqlite3.connect(tmp/'rows.db')
        c.executescript('CREATE TABLE streets(code TEXT,name TEXT,street TEXT,sid TEXT,localid TEXT);CREATE TABLE nums(code TEXT,street TEXT,num TEXT,lat REAL,lon REAL);')
        unknown=set();streets=0;batch=[]
        for row in records(tmp/'stradario.zip',diagnostics):
            code=istat(field(row,'CODICE_ISTAT'))
            city=field(row,'DENOMINAZIONE_COMUNE','NOME_COMUNE','COMUNE') or names.get(code,'')
            street=field(row,'ODONIMO','DENOMINAZIONE_URBANISTICA','DENOMINAZIONE_ODONIMO','DENOMINAZIONE_STRADA')
            if not city:unknown.add(code);continue
            if not street:raise RuntimeError('ODONIMO assente in un record stradario. Vedi diagnostica.')
            batch.append((code,city,street,field(row,'PROGRESSIVO_NAZIONALE'),field(row,'CODICE_COMUNALE')));streets+=1
            if len(batch)>=10000:c.executemany('INSERT INTO streets VALUES(?,?,?,?,?)',batch);batch=[]
        if batch:c.executemany('INSERT INTO streets VALUES(?,?,?,?,?)',batch)
        if unknown:raise RuntimeError('Codici ISTAT senza nome nel repertorio di supporto: '+', '.join(sorted(unknown)[:30])+'. Serve una tabella Comuni aggiornata; non pubblico dati parziali.')
        if not streets:raise RuntimeError('Nessuna strada acquisita.')
        c.executescript('CREATE INDEX sn ON streets(code,sid);CREATE INDEX sl ON streets(code,localid);')
        print('STRADE LETTE',streets,flush=True)
        numbers=0;bad=0;batch=[]
        for row in records(tmp/'indirizzario.zip',diagnostics):
            code=istat(field(row,'CODICE_ISTAT'))
            if code not in names:raise RuntimeError('Codice ISTAT indirizzario non riconosciuto: '+code)
            street=field(row,'ODONIMO','DENOMINAZIONE_URBANISTICA','DENOMINAZIONE_ODONIMO','DENOMINAZIONE_STRADA')
            if not street:
                sid=field(row,'PROGRESSIVO_NAZIONALE_STRADA','PROGRESSIVO_NAZIONALE_ODONIMO','PROGRESSIVO_STRADA','PROGRESSIVO_ODONIMO')
                localid=field(row,'CODICE_COMUNALE_STRADA','CODICE_COMUNALE_ODONIMO','CODICE_STRADA')
                result=c.execute('SELECT DISTINCT street FROM streets WHERE code=? AND sid=?',(code,sid)).fetchall() if sid else []
                if not result and localid:result=c.execute('SELECT DISTINCT street FROM streets WHERE code=? AND localid=?',(code,localid)).fetchall()
                if len(result)!=1:raise RuntimeError('Indirizzario senza ODONIMO o collegamento strada univoco. Controllare schema-diagnostic (include ora entrambi i CSV). Non uso il progressivo accesso come ID strada.')
                street=result[0][0]
            num=field(row,'CIVICO','NUMERO_CIVICO','NUMERO_ACCESSO','NUMERO')
            if not num:
                if not set(map(key,['CIVICO','NUMERO_CIVICO','NUMERO_ACCESSO','NUMERO'])).intersection(row):raise RuntimeError('Colonna numero civico non riconosciuta. Vedi schema-diagnostic aggiornato.')
                bad+=1;continue
            esp=field(row,'ESPONENTE','ESPONENTE_CIVICO')
            if esp:num+='/'+esp
            lat,lon=coordinates(row);batch.append((code,street,num,lat,lon));numbers+=1
            if len(batch)>=10000:c.executemany('INSERT INTO nums VALUES(?,?,?,?,?)',batch);batch=[]
        if batch:c.executemany('INSERT INTO nums VALUES(?,?,?,?,?)',batch)
        if not numbers:raise RuntimeError('Nessun numero civico acquisito: controllo richiesto.')
        c.executescript('CREATE INDEX nc ON nums(code,street);');c.commit()
        version=datetime.datetime.now(datetime.timezone.utc).isoformat();cities=[]
        for code,name in c.execute('SELECT DISTINCT code,name FROM streets ORDER BY name').fetchall():
            roads={s:{'name':s,'numbers':[]} for (s,) in c.execute('SELECT DISTINCT street FROM streets WHERE code=? ORDER BY street',(code,))}
            for street,num,lat,lon in c.execute('SELECT street,num,MAX(lat),MAX(lon) FROM nums WHERE code=? GROUP BY street,num ORDER BY street,LENGTH(num),num',(code,)):
                roads.setdefault(street,{'name':street,'numbers':[]})['numbers'].append({'n':num,'lat':lat,'lon':lon})
            file='city-'+code+'.json'
            (OUT/file).write_text(json.dumps({'city':name,'streets':list(roads.values())},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
            cities.append({'id':code,'name':name,'file':file})
        c.close()
        (OUT/'catalog.json').write_text(json.dumps({'version':version,'cities':cities,'source':'ANNCSU','streets_read':streets,'numbers_read':numbers,'accesses_without_number':bad,'urls':urls,'municipality_name_source':MUNICIPALITIES},ensure_ascii=False),encoding='utf-8')
    size=sum(p.stat().st_size for p in (ROOT/'site').rglob('*') if p.is_file())
    if size>900*1024*1024:raise RuntimeError('Sito oltre 900 MiB: ridurre dimensioni prima della pubblicazione.')
    print(json.dumps({'cities':len(cities),'streets':streets,'numbers':numbers,'bytes':size}),flush=True)
if __name__=='__main__':main()
