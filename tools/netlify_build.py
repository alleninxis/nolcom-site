"""Build a password-protected, read-only copy of NolCom for Netlify (or any static host).

  python3 netlify_build.py --password '...' [--dump /tmp/claude-0/dbdump] [--out /mnt/user-data/outputs/netlify_site]

Everything (the page and every database document) is encrypted with AES-256-GCM under a key derived from the
password (PBKDF2-SHA256, 310k iterations). The host only ever stores ciphertext; the browser decrypts after the
password is entered. The copy is read-only: no writing reports/notes/edits, no Claude features. The notebook is included."""
import argparse, base64, gzip, hashlib, json, os, shutil, glob
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

ITER = 310_000
BUNDLE = {'teams', 'scout', 'previews', 'reports', 'injrep', 'recaps', 'toplines', 'kp', 'gidx', 'slate', 'notes', 'threads', 'updates'}   # small collections: one file each
SKIP = {'overrides', 'live'}

def key_from(pw, salt):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw.encode())

def enc(key, obj_or_text):
    raw = obj_or_text if isinstance(obj_or_text, bytes) else (obj_or_text if isinstance(obj_or_text, str) else json.dumps(obj_or_text, separators=(',', ':'))).encode()
    iv = os.urandom(12)
    return iv + AESGCM(key).encrypt(iv, gzip.compress(raw, 9), None)

SHIM = r'''<script>
/* read-only database for the static copy: documents are AES-GCM encrypted, gzip'd JSON fetched on demand */
(function(){
  const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
  const kraw=sessionStorage.getItem('nck')||localStorage.getItem('nck');
  if(!kraw){ location.replace('./'); return; }
  const kp=crypto.subtle.importKey('raw',b64(kraw),'AES-GCM',false,['decrypt']);
  async function dec(path){ const k=await kp; const r=await fetch(path); if(!r.ok) return null; const b=new Uint8Array(await r.arrayBuffer());
    const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:b.slice(0,12)},k,b.slice(12));
    return JSON.parse(await new Response(new Blob([pt]).stream().pipeThrough(new DecompressionStream('gzip'))).text()); }
  const IX=dec('d/index.bin'), BUN={};
  const bundle=c=>BUN[c]||(BUN[c]=IX.then(ix=>ix.b.includes(c)?dec('d/b_'+c+'.bin'):{}));
  async function getOne(c,id){ const ix=await IX; if(ix.b.includes(c)){ const B=await bundle(c); return B[id]; } const f=ix.f[c+'/'+id]; return f?dec('d/'+f):undefined; }
  async function all(c){ const ix=await IX; if(ix.b.includes(c)) return bundle(c); const ids=ix.c[c]||[]; const out={}; await Promise.all(ids.map(async id=>{ out[id]=await getOne(c,id); })); return out; }
  const ro=()=>Promise.reject({code:'read_only',message:'This copy is read-only.'});
  const snap=(o,q)=>{ let d=Object.entries(o||{}).map(([id,v])=>({id,exists:true,data:()=>v,_v:v}));
    if(q&&q.ob){ const [f,dir]=q.ob; d.sort((x,y)=>{ const a=x._v&&x._v[f], b=y._v&&y._v[f]; if(a==null&&b==null) return 0; if(a==null) return 1; if(b==null) return -1; return (a<b?-1:a>b?1:0)*(dir==='desc'?-1:1); }); }
    if(q&&q.lim) d=d.slice(0,q.lim); return {docs:d,size:d.length,empty:!d.length}; };
  const coll=name=>{ const q={ob:null,lim:null,orderBy(f,dir){ q.ob=[f,dir||'asc']; return q; },limit(n){ q.lim=n; return q; },where(){return q},
      onSnapshot(cb){ all(name).then(o=>cb(snap(o,q))).catch(()=>cb(snap({}))); return ()=>{}; },
      get:async()=>snap(await all(name),q), add:ro, doc:id=>docRef(name+'/'+id)}; return q; };
  const docRef=k=>{ const [c,...r]=k.split('/'); const id=r.join('/'); return {id,
      get:async()=>{ const d=await getOne(c,id); return d===undefined||d===null?{exists:false,id,data:()=>undefined}:{exists:true,id,data:()=>d}; },
      set:ro, update:ro, delete:ro, onSnapshot(cb){ this.get().then(cb); return ()=>{}; }}; };
  const db={doc:docRef,collection:coll};
  const user={canEdit:async()=>false,id:async()=>null,profile:async()=>null,profiles:async()=>({})};
  window.claude={use:async n=>n==='db'?db:n==='user'?user:null};
  window.NOLCOM_STATIC=true;
})();
</script>
<style>.nc-static{background:#fff8e1;color:#5c4400;font:500 13px system-ui,sans-serif;padding:6px 12px;text-align:center}</style>
'''

GATE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>NolCom</title>
<style>:root{--bg:#f4f5f8;--ink:#141a26;--ink2:#5b6475;--rule:#d9dde6;--panel:#fff;--acc:#1f4fb3}
@media (prefers-color-scheme:dark){:root{--bg:#0f131b;--ink:#e8ebf2;--ink2:#9aa3b5;--rule:#2a3140;--panel:#161b25;--acc:#7da2ff}}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,Segoe UI,sans-serif;padding:16px;box-sizing:border-box}
form{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:28px 26px;width:100%;max-width:360px;box-sizing:border-box}
h1{font-size:22px;margin:0 0 4px}p{color:var(--ink2);margin:0 0 18px;font-size:14px}
input[type=password]{width:100%;box-sizing:border-box;font-size:16px;padding:11px 12px;border:1px solid var(--rule);border-radius:8px;background:var(--bg);color:var(--ink)}
label{display:flex;gap:8px;align-items:center;font-size:14px;color:var(--ink2);margin:12px 0 16px}
button{width:100%;font:600 16px system-ui,sans-serif;padding:11px;border:0;border-radius:8px;background:var(--acc);color:#fff;cursor:pointer}
#msg{color:#c0392b;font-size:14px;min-height:20px;margin:10px 0 0}</style></head>
<body><form id="f"><h1>NolCom</h1><p>Enter the password to open the site.</p>
<input type="password" id="pw" autocomplete="current-password" autofocus aria-label="Password">
<label><input type="checkbox" id="rem"> Remember on this device</label><button id="go">Open</button><div id="msg"></div></form>
<script>
const SALT="__SALT__", ITER=__ITER__;
const b64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0)), tob64=u=>btoa(String.fromCharCode(...new Uint8Array(u)));
async function openWith(raw){
  const k=await crypto.subtle.importKey('raw',raw,'AES-GCM',false,['decrypt']);
  const r=await fetch('app.bin'); const b=new Uint8Array(await r.arrayBuffer());
  const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:b.slice(0,12)},k,b.slice(12));
  const html=await new Response(new Blob([pt]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
  document.open(); document.write(html); document.close();
}
(async()=>{ const s=sessionStorage.getItem('nck')||localStorage.getItem('nck'); if(s){ try{ sessionStorage.setItem('nck',s); await openWith(b64(s)); return; }catch(e){ sessionStorage.removeItem('nck'); localStorage.removeItem('nck'); } } })();
document.getElementById('f').addEventListener('submit',async e=>{ e.preventDefault(); const msg=document.getElementById('msg'), btn=document.getElementById('go');
  btn.disabled=true; msg.textContent=''; btn.textContent='Opening…';
  try{ const base=await crypto.subtle.importKey('raw',new TextEncoder().encode(document.getElementById('pw').value),'PBKDF2',false,['deriveBits']);
    const raw=await crypto.subtle.deriveBits({name:'PBKDF2',salt:b64(SALT),iterations:ITER,hash:'SHA-256'},base,256);
    await openWith(raw); const s=tob64(raw); sessionStorage.setItem('nck',s); if(document.getElementById('rem')&&document.getElementById('rem').checked) localStorage.setItem('nck',s);
  }catch(err){ msg.textContent='Wrong password.'; btn.disabled=false; btn.textContent='Open'; } });
</script></body></html>'''

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--password', required=True); ap.add_argument('--dump', default='/tmp/claude-0/dbdump')
    ap.add_argument('--page', default='/mnt/user-data/outputs/cbb-book/index.html'); ap.add_argument('--out', default='/mnt/user-data/outputs/netlify_site')
    ap.add_argument('--salt'); a = ap.parse_args()
    salt = base64.b64decode(a.salt) if a.salt else os.urandom(16); key = key_from(a.password, salt)
    if os.path.exists(a.out): shutil.rmtree(a.out)
    os.makedirs(os.path.join(a.out, 'd'))
    idx = {'b': [], 'c': {}, 'f': {}}
    for cdir in sorted(glob.glob(os.path.join(a.dump, '*'))):
        c = os.path.basename(cdir)
        if c in SKIP: continue
        docs = {}
        for f in sorted(glob.glob(os.path.join(cdir, '*.json'))):
            d = json.load(open(f)); docs[os.path.basename(f)[:-5]] = d
        if c in BUNDLE:
            open(os.path.join(a.out, 'd', f'b_{c}.bin'), 'wb').write(enc(key, docs)); idx['b'].append(c)
        else:
            idx['c'][c] = list(docs)
            for i, d in docs.items():
                h = hashlib.sha256(f'{c}/{i}'.encode()).hexdigest()[:20] + '.bin'
                open(os.path.join(a.out, 'd', h), 'wb').write(enc(key, d)); idx['f'][f'{c}/{i}'] = h
    open(os.path.join(a.out, 'd', 'index.bin'), 'wb').write(enc(key, idx))
    page = open(a.page).read()
    banner = '<div class="nc-static">Read-only copy. Writing notes, reports and edits happens on the main site.</div>'
    page = page.replace('<head>', '<head>' + SHIM, 1)
    i = page.find('<body'); j = page.find('>', i) + 1
    page = page[:j] + banner + page[j:]
    open(os.path.join(a.out, 'app.bin'), 'wb').write(enc(key, page))
    open(os.path.join(a.out, 'index.html'), 'w').write(GATE.replace('__SALT__', base64.b64encode(salt).decode()).replace('__ITER__', str(ITER)))
    open(os.path.join(a.out, 'robots.txt'), 'w').write('User-agent: *\nDisallow: /\n')
    open(os.path.join(a.out, '_headers'), 'w').write('/*\n  X-Robots-Tag: noindex, nofollow\n  Referrer-Policy: no-referrer\n/d/*\n  Cache-Control: no-cache\n/app.bin\n  Cache-Control: no-cache\n')
    tot = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(a.out) for f in fs)
    print(f'built {a.out}: {sum(len(v) for v in idx["c"].values())} single docs, bundles {idx["b"]}, total {tot/1e6:.1f} MB; salt {base64.b64encode(salt).decode()}')

if __name__ == '__main__': main()
