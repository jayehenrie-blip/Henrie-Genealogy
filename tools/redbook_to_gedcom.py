#!/usr/bin/env python3
"""Convert the Red Book text (extracted from red_book.pdf) into GEDCOM 5.5.1.

Usage:
    python3 tools/redbook_to_gedcom.py book.txt data/henrie-full.ged data/henrie.ged

book.txt is the PDF's text with "=====PAGE n=====" markers (see tools/extract_text.py).
Writes two files:
  * henrie-full.ged  everything parsed from the book (keep private)
  * henrie.ged       the public copy: living people keep their names only

The conversion is heuristic. The book follows a regular pattern
(person sketch, then a numbered list of children, "*" = has own entry later),
but some entries will need hand correction. Corrections belong in the GEDCOM,
not in this script, once the GEDCOM has been checked by a person.
"""
import re, sys, json, datetime, unicodedata, difflib
from collections import defaultdict

THIS_YEAR = datetime.date.today().year
MONTHS = {"jan":"JAN","feb":"FEB","mar":"MAR","apr":"APR","may":"MAY","jun":"JUN","june":"JUN","jul":"JUL","july":"JUL",
          "aug":"AUG","sep":"SEP","sept":"SEP","oct":"OCT","nov":"NOV","dec":"DEC"}

# ---------------------------------------------------------------- model
class Person:
    def __init__(s, pid, name):
        s.id=pid; s.name=name; s.sex=None
        s.birth={}; s.death={}; s.burial={}
        s.story=[]; s.ordinances=[]; s.pages=set(); s.famc=None; s.fams=[]
        s.has_entry=False; s.title=None; s.note_parents=None
class Family:
    def __init__(s, fid):
        s.id=fid; s.husb=None; s.wife=None; s.children=[]; s.marr={}

people={}; fams={}
def new_person(name, page):
    p=Person(f"I{len(people)+1}", clean_name(name)); p.pages.add(page); people[p.id]=p; return p
def new_family():
    f=Family(f"F{len(fams)+1}"); fams[f.id]=f; return f

# ---------------------------------------------------------------- text helpers
def clean_name(n):
    n=re.sub(r"\s+"," ",n).strip(" ,.;:*")
    n=re.sub(r"\s+\.","",n)
    return n
def titlecase(n):
    def tc(w):
        if re.fullmatch(r"[A-Z]{1}\.?",w): return w
        if w.startswith("(") : return "("+tc(w[1:])
        lw=w.lower()
        if lw in ("jr.","jr","sr.","sr"): return lw.capitalize()
        if lw.startswith("mc") and len(w)>3: return "Mc"+w[2:].capitalize()
        if lw in ("ii","iii","iv"): return w.upper()
        return "-".join(p.capitalize() for p in w.split("-"))
    return " ".join(tc(w) for w in n.split())
def norm(n):
    n=unicodedata.normalize("NFKD",n).lower()
    n=re.sub(r"\(.*?\)","",n); n=re.sub(r"[^a-z ]"," ",n); n=re.sub(r"\b(jr|sr|mrs|mr|dr)\b","",n)
    return " ".join(n.split())
def first_last(n):
    w=norm(n).split(); return (w[0],w[-1]) if w else ("","")

DATE_RE = (r"(?:(?:abt\.?|about|before|after|bef\.?|aft\.?|prob\.?|probably|circa|c\.)\s*)?"
           r"(?:\d{1,2}(?:\s*[-–]\s*\d{1,2})*\s+)?"
           r"(?:[A-Z][a-z]{2,4}\.?(?:\s*[-–]\s*[A-Z][a-z]{2,4}\.?)?\s+)?"
           r"(?:\d{1,2}(?:\s*[-–]\s*\d{1,2})*,?\s+)?"
           r"\d{4}(?:\s*[-–]\s*\d{1,4})?")
def ged_date(raw):
    """Return a GEDCOM DATE value for the book's date phrase."""
    r=raw.strip().rstrip(",.")
    about = bool(re.match(r"(abt|about|prob|probably|circa|c\.)",r,re.I))
    before = bool(re.match(r"(before|bef)",r,re.I)); after=bool(re.match(r"(after|aft)",r,re.I))
    r2=re.sub(r"^(abt\.?|about|before|after|bef\.?|aft\.?|prob\.?|probably|circa|c\.)\s*","",r,flags=re.I)
    m=re.fullmatch(r"(?:(\d{1,2})\s+)?(?:([A-Za-z]{3,5})\.?\s+)?(\d{4})",r2)
    if m and (not m.group(2) or m.group(2).lower() in MONTHS):
        d,mo,y=m.groups(); parts=[x for x in [d, MONTHS.get((mo or "").lower()), y] if x]
        v=" ".join(parts)
        return ("ABT " if about else "BEF " if before else "AFT " if after else "")+v
    m=re.fullmatch(r"(\d{4})\s*[-–]\s*(\d{1,4})",r2)
    if m:
        a,b=m.groups(); b=a[:4-len(b)]+b
        return f"BET {a} AND {b}" if int(b)>int(a) else f"ABT {a}"
    y=re.search(r"\d{4}",r2)
    mo=re.search(r"\b([A-Z][a-z]{2,4})\.?",r2)
    base=" ".join(x for x in [MONTHS.get(mo.group(1).lower()) if mo else None, y.group(0) if y else None] if x)
    return f"INT {base} ({r})" if base else f"({r})"
def year_of(ev):
    d=ev.get("date") or ""
    m=re.search(r"\b(1[5-9]\d\d|20[0-2]\d)\b",d); return int(m.group(1)) if m else None

ABBR = r"(?:Co|Twsp|Twp|Mt|St|Ft|Ste|Ida|Ore|Calif|Ariz|Nev|Colo|Wyo|Wash|Mont|Ill|Penn|Pa|Va|Ky|Tenn|Mo|Ia|Kan|Neb|Mich|Wis|Minn|Tex|Okla|N|S|E|W|U|D|C|L|Mass|Conn|Ut)"
def cut_place(s):
    s=s.strip().lstrip(",").strip()
    s=re.sub(r"^(in|at|near)\s+","",s)
    # stop at clear boundaries
    stop=re.search(r"\[|;|\(see|, d\.|, d |, m\.|, and |, s\. of|, dau\.|, son of|, daughter of|, twin| d\. \d|, bur\.|, stillborn|, unmarried| He | She | They |, he |, she |, where|, died",s)
    if stop: s=s[:stop.start()]
    # a sentence end that isn't an abbreviation
    for m in re.finditer(r"\.\s+(?=[A-Z])",s):
        if not re.search(r"\b"+ABBR+r"$",s[:m.start()]):
            s=s[:m.start()]; break
    s=re.sub(r"(?<=[a-z])\d+$","",s.strip(" ,.;:")).strip(" ,.;:")
    if not s or re.match(r"^\d",s) or len(s)>90 or not re.match(r"[A-Z]",s): return ""
    if re.match(r"(Utah|Idaho|Calif|Nev|Ariz)\b",s) is None and len(s.split())>12: return ""
    return s

def vital(text, tag):
    """Find 'b. DATE, PLACE' (tag='b') or 'd.'/'bur.' in text."""
    m=re.search(r"(?:^|[\s,;(])"+tag+r"\.?\s+("+DATE_RE+r")([^\[;]*)",text)
    if not m: return {}
    date=m.group(1); rest=m.group(2)
    ev={"date":ged_date(date),"raw":re.sub(r"\s+"," ",date).strip()}
    pl=cut_place(rest)
    if pl: ev["place"]=pl
    return ev

def ordinances(text):
    return [re.sub(r"\s+"," ",x).strip() for x in re.findall(r"\[([^\]]*?(?:bapt|end\.|S\.\s*to|sealed)[^\]]*)\]",text)]
def strip_brackets(text):
    t=re.sub(r"\[p\.\s*\d+\]","",text)
    t=re.sub(r"\[[^\]]*?(?:bapt|end\.|S\.\s*to|sealed|S\. to)[^\]]*\]","",t)
    t=re.sub(r"\s+([,.;])",r"\1",t)
    return re.sub(r"[ \t]+"," ",t).strip()

def spouse_chunks(text):
    """Yield (index, raw) for each 'm. (n) ...' marriage phrase in a sentence."""
    out=[]
    for m in re.finditer(r"\bm\.\s*(?:\((\d)\)\s*)?(.{0,260}?)(?=;\s*m\.|\.\s+\(|\.\s+(?:He|She|They|Both|Rulon|The|Their)\b|\.\s*$|\.\s+[A-Z][a-z]+ (?:was|had|d\.|and|m\.)|$)",text):
        idx=int(m.group(1))-1 if m.group(1) else len(out)
        out.append((idx,m.group(2)))
    return out
def parse_spouse(raw):
    """From '29 Oct. 1914, in Manti (L.D.S. Temple), to Theo Hichcock, dau. of ...' get name/date/place/parents."""
    raw=strip_brackets(raw)
    res={}
    bm=re.search(r",\s*b\.\s.*$",raw)
    if bm:
        tail=bm.group(0); raw=raw[:bm.start()]
        b=vital(tail,"b"); d=vital(tail,"d")
        if b: res["birth"]=b
        if d: res["death"]=d
    par=re.search(r",?\s*(?:dau\.?|daughter|s\.|son)\s+of\s+(.*)$",raw)
    if par: res["parents"]=par.group(1).strip(" .,"); raw=raw[:par.start()]
    dm=re.match(r"\s*("+DATE_RE+r")\s*,?",raw)
    if dm: res["date"]=ged_date(dm.group(1)); res["raw"]=dm.group(1); raw=raw[dm.end():]
    raw=re.sub(r"\(L\.\s*D\.\s*S\.\s*Temple\)|\(LDS Temple\)","",raw)
    if re.search(r"\bto\s+[A-Z]",raw):
        before,after=re.split(r"\bto\s+(?=[A-Z])",raw,maxsplit=1)
        place=cut_place(before); name=after
    else:
        parts=[p.strip() for p in raw.split(",") if p.strip()]
        if not parts: return None
        # trailing 'on 1 June 1921' etc.
        name=parts[-1] if len(parts)==1 else None
        if name is None:
            # name is the part with no state/county words, usually the last
            name=parts[-1]; place=", ".join(parts[:-1])
            if re.search(r"\b(Utah|Co\.|Idaho|Calif|Temple|Ariz|Nev|Ore|Wyo|Colo)\b",name) and len(parts)>1:
                name=parts[0]; place=", ".join(parts[1:])
            place=cut_place(place)
        else: place=""
    name=re.sub(r"\s+on\s+\d.*$","",name); name=name.split(";")[0]
    name=re.split(r"\s+(?:b\.|who|He|She|was|They|in\s|at\s|\()",name)[0]
    name=clean_name(name)
    if not name or not re.match(r"[A-Z]",name) or len(name.split())>6 or re.search(r"\d",name): return None
    if name.lower() in ("she","he","they","her","him"): return None
    res["name"]=name
    if place: res["place"]=place
    return res

# ---------------------------------------------------------------- parse
def is_caps_name(s):
    s=re.sub(r"\(.*?\)","",s)
    L=[c for c in s if c.isalpha()]
    return len(L)>=5 and sum(c.isupper() for c in L)/len(L)>0.8 and len(s.split())>=2
HDR=re.compile(r"^([A-Z][A-Za-z'\.\- ()]{2,70}?):?\s*,\s*(.*)$")
HDR2=re.compile(r"^([A-Z][A-Z'\.\- ()]{2,70}?)\s+((?:eldest|oldest|youngest|only|second|third|\d+\w*)\s+(?:child|son|dau).*)$")
KID=re.compile(r"^\s*(\*\s*)?(\d{1,2})(?:\.|,(?=\s+[A-Z][a-z]+ [A-Z][^,]{1,40}, b\.))\s+([A-Z].*)$")
KID2=re.compile(r"^\s*(\*\s*)(\d{1,2})\s+([A-Z][a-z]+ .*?, b\..*)$")
GKID=re.compile(r"^\s*\((\d{1,2})\)\s+([A-Z].*)$")
ROMAN=re.compile(r"^[IVXL]+[,.]")

def load_lines(path):
    page=0; out=[]
    raw=open(path,encoding="utf-8").read().split("\n")
    for i,l in enumerate(raw):
        m=re.match(r"=====PAGE (\d+)=====",l)
        if m:
            pdfp=int(m.group(1)); page=None; continue
        if page is None:
            if re.fullmatch(r"\s*\d{1,3}\s*",l): page=int(l); continue
            page=out[-1][0] if out else 0
        if not l.strip(): continue
        l=re.sub(r"\b[lI](?=\s+(?:Jan|Feb|Mar|Apr|May|June|July|Aug|Sept|Oct|Nov|Dec)\b)","1",l)
        l=re.sub(r"\b(\d)l(?=\s+(?:Jan|Feb|Mar|Apr|May|June|July|Aug|Sept|Oct|Nov|Dec)\b)",r"\g<1>1",l)
        # a numbered child that starts in the middle of a line ("... 1947]. 10. Melody Ann ...")
        mm=re.search(r"(?<=[\].])\s+(\d{1,2})\.\s+(?=[A-Z][a-z]+ [A-Z][a-z]+)",l)
        if mm and not re.match(r"\s*(\*\s*)?\d",l[:3]) or (mm and mm.start()>10):
            out.append((page,l[:mm.start()].rstrip(),pdfp)); l=l[mm.start():].strip()
        out.append((page,l.rstrip(), pdfp))
    return out

def logical_items(lines):
    """Group physical lines into items: ('hdr', text), ('kid', star, n, text), ('gkid', n, text), ('text', text), ('title', text)."""
    items=[]; cur=None
    def flush():
        nonlocal cur
        if cur: items.append(cur); cur=None
    for page,l,pdfp in lines:
        s=l.strip()
        if pdfp<7: continue   # front matter
        if pdfp>=399: break   # indexes
        m=KID.match(l) or KID2.match(l); g=GKID.match(l); h=HDR2.match(s) or HDR.match(s)
        if g and cur and re.search(r"\bm\.\s*$",cur["t"]): g=None
        if m:
            flush(); cur={"k":"kid","star":bool(m.group(1)),"n":int(m.group(2)),"t":m.group(3),"page":page}; continue
        if g:
            flush(); cur={"k":"gkid","n":int(g.group(1)),"t":g.group(2),"page":page}; continue
        if h and is_caps_name(h.group(1)) and not ROMAN.match(s) and not s.startswith("CHAPTER"):
            flush(); cur={"k":"hdr","name":h.group(1),"t":h.group(2),"page":page}; continue
        if is_caps_name(s) and "," not in s and len(s)<70 and not re.search(r"[a-z]{3}",s.replace("Mc","")):
            flush(); items.append({"k":"title","t":s,"page":page}); continue
        if re.match(r"^CHAPTER\b",s):
            flush(); items.append({"k":"title","t":s,"page":page}); continue
        if cur and cur["k"] in ("kid","gkid","hdr") and not (cur["k"]=="hdr" and len(cur["t"])>900):
            # continuation of a child line only while it looks like the same record
            if cur["k"]!="hdr" and (cur["t"].rstrip().endswith((".",":","]")) and len(l)<70 and not re.match(r"(She|He|They|Both|It|[a-z(\[])",s) or (re.search(r"\bhad \d+ child",s) and re.match(r"[A-Z][a-z]+\b",s) and not re.match(r"(She|He|They|It|Both)\b",s) and not re.search(r";|m\. \(|\.\s",s.split(" had ")[0]))):
                flush(); cur={"k":"text","t":s,"page":page,"short":len(l)<75}; continue
            cur["t"]+=("" if cur["t"].endswith("-") else " ")+s
            if cur["k"]=="hdr" and (len(l)<72 and s.endswith((".",":",'"',"”"))): flush()
            continue
        if cur and cur["k"]=="text":
            if cur.get("short"):
                flush(); cur={"k":"text","t":s,"page":page,"short":len(l)<75}
            else:
                cur["t"]+=" "+s; cur["short"]=len(l)<75 and s.endswith((".",'"',"”",":","!","?"))
            continue
        flush(); cur={"k":"text","t":s,"page":page,"short":len(l)<75 and s.endswith((".",'"',"”",":"))}
    flush()
    return items

stated=[]
def run(book, out_full, out_public):
    lines=load_lines(book)
    items=logical_items(lines)
    by_norm=defaultdict(list)    # norm name -> [pid] awaiting their own entry (starred or any child)
    def register(p): by_norm[norm(p.name)].append(p.id)

    def marry(p, sp_info, page, idx=None):
        """Attach spouse described by sp_info to p, return family."""
        name=sp_info["name"]
        def better(o):
            on=people[o].name
            if len(name.split())>len(on.split()) or (len(name.split())==len(on.split()) and norm(name)!=norm(on) and "-" not in name):
                people[o].name=name
        for fid in p.fams:
            f=fams[fid]; other=f.wife if f.husb==p.id else f.husb
            on,nn2=norm(people[other].name).split() if other else [],norm(name).split()
            if other and on and nn2 and on[0]==nn2[0] and (set(on[1:])&set(nn2[1:])) :
                better(other)
                if sp_info.get("birth") and not people[other].birth: people[other].birth=sp_info["birth"]
                if sp_info.get("death") and not people[other].death: people[other].death=sp_info["death"]
                if sp_info.get("date") and not f.marr.get("date"): f.marr["date"]=sp_info["date"]; f.marr["raw"]=sp_info.get("raw")
                if sp_info.get("place") and not f.marr.get("place"): f.marr["place"]=sp_info["place"]
                return f
            if other and (norm(people[other].name)==norm(name) or first_last(people[other].name)==first_last(name)
                          or (first_last(people[other].name)[1]==first_last(name)[1] and difflib.SequenceMatcher(None,first_last(people[other].name)[0],first_last(name)[0]).ratio()>=0.6)):
                better(other)
                if sp_info.get("date") and not f.marr.get("date"): f.marr["date"]=sp_info["date"]; f.marr["raw"]=sp_info.get("raw")
                if sp_info.get("place") and not f.marr.get("place"): f.marr["place"]=sp_info["place"]
                if sp_info.get("parents") and not people[other].note_parents: people[other].note_parents=sp_info["parents"]
                if sp_info.get("birth") and not people[other].birth: people[other].birth=sp_info["birth"]
                if sp_info.get("death") and not people[other].death: people[other].death=sp_info["death"]
                return f
        s=new_person(name,page); s.has_entry=True
        if sp_info.get("parents"): s.note_parents=sp_info["parents"]
        if sp_info.get("birth"): s.birth=sp_info["birth"]
        if sp_info.get("death"): s.death=sp_info["death"]
        f=new_family()
        if p.sex=="F": f.wife=p.id; f.husb=s.id; s.sex="M"
        else: f.husb=p.id; f.wife=s.id; s.sex = "F" if p.sex=="M" else None
        f.marr={k:v for k,v in sp_info.items() if k in ("date","place","raw")}
        p.fams.append(f.id); s.fams.append(f.id)
        return f


    def spouse_vitals(p, plain):
        """Sentences like 'Amanda was b. 15 Jan. 1829, at Clarence' give a spouse's birth and death."""
        for fid in p.fams:
            f=fams[fid]; o=f.wife if f.husb==p.id else f.husb
            if not o: continue
            sp=people[o]; fn=sp.name.split()[0]
            pats=[re.escape(fn)] + (["She"] if sp.sex=="F" else ["He"] if sp.sex=="M" else ["She","He"])
            for pat in pats:
                m=re.search(r"\b"+pat+r" was b\.",plain)
                if not m: continue
                seg=plain[m.start():m.start()+260]
                seg=re.split(r"\.\s+(?=(?:They|He|She|Daniel|James|Information|The)\b)",seg)[0]
                if not sp.birth:
                    b=vital(seg,"b")
                    if b: sp.birth=b
                if not sp.death:
                    d=vital(seg[8:],"d")
                    if d: sp.death=d
                break


    def pick_couple(p, st, page):
        m=re.match(r"^(.{3,90}?)\s+had \d+ child",st)
        if not m or not p.fams: return None
        head=m.group(1)
        parts=re.split(r"\s+(?:&|and)\s+",head,maxsplit=1)
        if len(parts)<2: return None
        left,right=parts
        pw=set(norm(p.name).split())
        lw=set(norm(left).split())-{"jr","sr"}
        if not lw or not lw<=pw: return None
        right=re.sub(r"^(?:his|her)\s+(?:first|second|third|fourth|1st|2nd|3rd|former|late)?\s*(?:wife|husband),?\s*","",right).strip(" ,")
        maiden=re.findall(r"\(([A-Za-z]+)\)",right)
        rw=set(norm(re.sub(r"\(.*?\)","",right)).split())|{x.lower() for x in maiden}
        best=None;bs=0
        for i,fid in enumerate(p.fams):
            f=fams[fid]; o=f.wife if f.husb==p.id else f.husb
            if not o: continue
            ow=norm(people[o].name).split()
            if not ow: continue
            sc=(2 if ow[0] in rw else 0)+len((set(ow[1:]) & rw)-pw)
            if sc>bs: bs=sc;best=i
        if best is not None and bs>=2: return best
        # a spouse not seen yet
        nm=re.sub(r"\s*\(([A-Za-z]+)\)\s*[A-Z][a-z]+$",r" \1",right).strip(" ,")
        if re.fullmatch(r"[A-Z][A-Za-z.]*(?: [A-Z][A-Za-z.]*){0,4}",nm) and len(nm.split())>=2:
            f=marry(p,{"name":nm},page); return p.fams.index(f.id)
        return None

    def fam_for(p, idx):
        fl=p.fams
        if not fl:
            f=new_family()
            if p.sex=="F": f.wife=p.id
            else: f.husb=p.id
            p.fams.append(f.id); return f
        return fams[fl[min(idx,len(fl)-1)]]

    def add_child(parent, idx, text, page, star):
        name_part=re.split(r",|\s+b\.\s|\s+\[|;",text,maxsplit=1)[0]
        name_part=re.sub(r"\s+(twin|stillborn).*","",name_part)
        name_part=re.sub(r"\s*\((?:male|female)\).*|\s+(?:\d+\w*|eldest|oldest|youngest)\s+(?:child|son|dau).*","",name_part)
        nm=clean_name(name_part)
        if not nm or len(nm.split())>7: return None
        c=new_person(nm,page)
        c.birth=vital(text,"b"); c.death=vital(text,"d")
        if re.search(r"\b(stillborn|d\. young|d\. same day|d\. in infancy|died young)\b",text) and not c.death:
            c.death={"date":"","raw":"young"}
        c.ordinances=ordinances(text)
        rest=text[len(name_part):]
        # spouses of the child
        for i,raw in spouse_chunks(strip_brackets(rest)):
            info=parse_spouse(raw)
            if info: marry(c,info,page)
        f=fam_for(parent, idx)
        f.children.append(c.id); c.famc=f.id
        # short notes (served in..., killed in ...) become a one-line story
        extra=strip_brackets(text)
        extra=re.sub(r"^.*?\.\s+(?=[A-Z][a-z]+ (?:served|was|is|lived|died|served))","",extra) if len(extra)>160 else ""
        register(c)
        return c

    # Chapter I starts with Michael Henry (emigrant) in prose, not in the usual header form.
    michael=new_person("Michael Henry",1); michael.sex="M"; michael.has_entry=True; michael.title="Emigrant ancestor"
    michael.birth={"date":"ABT 1683","raw":"about 1683","place":"Scotland"}
    michael.death={"date":"DEC 1760","raw":"Dec. 1760","place":"Readington Twsp., Hunterdon Co., New Jersey"}
    michael.burial={"place":"Three Bridges, Hunterdon Co., New Jersey"}
    jean=new_person("Jean Henry",1); jean.sex="F"; jean.has_entry=True
    jean.birth={"date":"ABT 1694","raw":"about 1694"}; jean.death={"date":"JUN 1761","raw":"June 1761","place":"Readington Twsp., Hunterdon Co., New Jersey"}
    jean.burial={"place":"Three Bridges, Hunterdon Co., New Jersey"}
    f=new_family(); f.husb=michael.id; f.wife=jean.id; michael.fams.append(f.id); jean.fams.append(f.id)

    cur=michael; story_to=michael; fam_idx=0; last_kid=None; seen_kid=False; in_refs=False
    for it in items:
        k=it["k"]; page=it["page"]
        if k=="title":
            continue
        if k=="hdr":
            hname=it["name"]; text=it["t"]
            nn=norm(hname)
            wm=re.match(r"\s*(?:(?:first|second|third|fourth|1st|2nd|3rd)\s+)?(wife|husband|widow)\s+of\s+([A-Z][\w\.]*(?: [A-Z][\w\.]*)*)",text)
            if wm:
                # a sketch of a spouse: find that spouse among the named person's families
                target=None; hfl=first_last(titlecase(hname))
                for q in people.values():
                    for fid in q.fams:
                        f=fams[fid]; o=f.wife if f.husb==q.id else f.husb
                        if o and (norm(people[o].name)==nn or first_last(people[o].name)==hfl) and norm(q.name).split()[0]==norm(wm.group(2)).split()[0]:
                            target=people[o]; owner=q
                if target is None:
                    target=new_person(titlecase(hname),page); target.has_entry=True
                b=vital(text,"b"); d=vital(text,"d")
                if b and not target.birth: target.birth=b
                if d and not target.death: target.death=d
                target.ordinances+=ordinances(text); target.pages.add(page)
                rest=strip_brackets(text)
                if len(rest)>40: target.story.append(("p",rest))
                story_to=target
                continue
            # parents named in the header: "2nd child of Arthur & Amanda (Funk) Cox"
            pid=None
            hb=vital(text,"b"); hy=year_of(hb) if hb else None
            pm=re.search(r"(?:child|son|dau\.?|daughter|s\.)\s+of\s+([A-Z][\w\.']*)[^&]*?(?:&|and)\s+([A-Z][\w\.']*)",text)
            pfirst={pm.group(1).lower().rstrip("."),pm.group(2).lower().rstrip(".")} if pm else set()
            fl=first_last(hname)
            pool=set(by_norm.get(nn,[]))|{x for v in by_norm.values() for x in v if first_last(people[x].name)==fl}
            best=None;bs=-99
            for x in pool:
                c=people[x]
                if c.has_entry: continue
                sc=0; cy=year_of(c.birth)
                if hy and cy:
                    if abs(hy-cy)>1: continue
                    sc+=3
                if pfirst and c.famc:
                    ff=fams[c.famc]; pn={norm(people[q].name).split()[0] for q in (ff.husb,ff.wife) if q and norm(people[q].name)}
                    sc+=2*len(pn & pfirst)
                    if not (pn & pfirst): sc-=3
                if norm(c.name)==nn: sc+=1
                if sc>bs: bs=sc;best=x
            if best is not None and bs>=0: pid=best
            if pid:
                p=people[pid]
            else:
                p=new_person(titlecase(hname),page)
                register(p)
            p.has_entry=True; p.pages.add(page)
            full="("+text  # keep vitals
            if re.match(r"\s*(\d+\w*|eldest|oldest|youngest|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)?\s*(child|son|s\.)\b",text) or re.search(r"\b(son|s\.) of\b",text[:80]): p.sex=p.sex or "M" if re.search(r"\b(son|s\.)\b",text[:40]) else p.sex
            if re.search(r"\b(dau\.|daughter)\b",text[:40]) or re.search(r"\b(wife) of\b",text[:40]): p.sex="F"
            if re.search(r"\b(son|s\.) of\b",text[:40]): p.sex="M"
            b=vital(text,"b"); d=vital(text,"d"); bu=vital(text,"bur")
            if b and (not p.birth or len(b.get("place",""))>len(p.birth.get("place",""))): p.birth=b
            if d: p.death=d
            if bu: p.burial=bu
            p.ordinances+=ordinances(text)
            # header spouse(s) and the spouse's birth
            plain=strip_brackets(text)
            for i,raw in spouse_chunks(plain):
                info=parse_spouse(raw)
                if info: marry(p,info,page)
            spouse_vitals(p, plain)
            cur=p; story_to=p; fam_idx=0; last_kid=None; seen_kid=False; in_refs=False
            for n in re.findall(r"had (\d+) child",plain): stated.append((p.id,0,int(n),page))
            continue
        if k=="kid":
            c=add_child(cur, fam_idx, it["t"], page, it["star"])
            if c: last_kid=c; seen_kid=True
            continue
        if k=="gkid":
            if last_kid is None: continue
            c=add_child(last_kid, 0, it["t"], page, False)
            continue
        # plain text
        t=it["t"]
        _sn=re.search(r"had (\d+) child",t)
        if re.match(r"^References?\s*:",t): in_refs=True
        st=strip_brackets(t)
        # switching to a later marriage's children
        if re.search(r"\b(second|2nd) (wife|husband)\b.*had \d+ children|m\. \(2\).*(had|They had) \d+ child|and .{3,40} had \d+ children",st) and cur.fams \
           and re.match(r"("+("" if seen_kid else "He|She|")+re.escape(cur.name.split()[0])+r")\b",st):
            if re.search(r"\b(second|2nd)\b|m\. \(2\)",st): fam_idx=1
            if re.search(r"\b(third|3rd)\b|m\. \(3\)",st): fam_idx=2
            if re.search(r"\b(first|1st)\b",st): fam_idx=0
            # make sure the family exists
            for i,raw in spouse_chunks(st):
                info=parse_spouse(raw)
                if info: marry(cur,info,page)
            m=re.search(r"(?:second|third|first|fourth) (?:wife|husband),?\s+([A-Z][A-Za-z ]+?(?:\s*\([A-Za-z]+\))?\s*[A-Z][a-z]+),? had",st)
            if m:
                nm=m.group(1)
                pm2=re.match(r"\s*([A-Z][A-Za-z ]*?)\s*\(([A-Za-z]+)\)\s*[A-Z][a-z]+\s*$",nm)
                nm=f"{pm2.group(1)} {pm2.group(2)}" if pm2 else nm
                ff=marry(cur,{"name":nm.strip()},page); fam_idx=cur.fams.index(ff.id)
        # "John Nathaniel & Hazel Dean (Barton) Henrie had 3 children": pick the marriage by the named spouse
        pc=pick_couple(cur, st, page)
        if pc is not None:
            fam_idx=pc; story_to=cur
        if seen_kid and last_kid is not None and re.match(r"^[A-Z][a-z]+(?: [A-Z][a-z]+)* (m\.|and)",st) and not in_refs:
            # remarks about the last child (e.g. "Ila Mary Cox m. (2) ...")
            pass
        if re.search(r"\bhad \d+ child",st) and story_to is not cur and re.match(re.escape(cur.name.split()[0]),st):
            story_to=cur
        if _sn and not in_refs and (re.match(r"(They|He|She|"+re.escape(cur.name.split()[0])+r")\b",st)):
            stated.append((cur.id,fam_idx,int(_sn.group(1)),page))
        if in_refs:
            cur.story.append(("ref",st)); continue
        if not seen_kid and re.search(r"\bm\.\s*(\(\d\)\s*)?\d",st[:200]):
            fn0=norm(cur.name).split()[0] if norm(cur.name) else "zzz"
            if re.match(r"^(He|She|"+re.escape(cur.name.split()[0])+r")\b",st):
                head=re.split(r"(?<=[a-z]{3})\.\s+(?=(?:They|Information|The|In|After|When|While|His|Her)\b)",st)[0]
                for i,raw in spouse_chunks(head):
                    info=parse_spouse(raw)
                    if info: marry(cur,info,page)
            spouse_vitals(cur, st)
        if len(st)>2 and not re.search(r"\bhad \d+ child[^.]*:\s*$",st):
            story_to.story.append(("p",st))
        story_to.pages.add(page)

    # ---------------------------------------------------------------- tidy
    # infer sex from family role and from first names
    for f in fams.values():
        if f.husb and not people[f.husb].sex: people[f.husb].sex="M"
        if f.wife and not people[f.wife].sex: people[f.wife].sex="F"
    fn=defaultdict(lambda: defaultdict(int))
    for p in people.values():
        if p.sex: fn[norm(p.name).split()[0] if norm(p.name) else ""][p.sex]+=1
    for p in people.values():
        if not p.sex and norm(p.name):
            c=fn[norm(p.name).split()[0]]
            if c: p.sex=max(c,key=c.get)
    # fix family roles where the "husband" is female
    for f in fams.values():
        if f.husb and f.wife and people[f.husb].sex=="F" and people[f.wife].sex=="M": f.husb,f.wife=f.wife,f.husb
        elif f.husb and not f.wife and people[f.husb].sex=="F": f.wife,f.husb=f.husb,None

    # living = no death, born within 100 years (or estimated so)
    def est_year(p, depth=0):
        y=year_of(p.birth)
        if y: return y
        if depth>3: return None
        if p.famc:
            for par in (fams[p.famc].husb, fams[p.famc].wife):
                if par:
                    yy=est_year(people[par],depth+1)
                    if yy: return yy+25
        for fid in p.fams:
            for c in fams[fid].children:
                yy=year_of(people[c].birth)
                if yy: return yy-25
            f=fams[fid]; o=f.wife if f.husb==p.id else f.husb
            if o and year_of(people[o].birth): return year_of(people[o].birth)
        return None
    living=set()
    for p in people.values():
        y=est_year(p)
        if not p.death and (y is None or y>THIS_YEAR-100):
            living.add(p.id)
    write_ged(out_full, set())
    write_ged(out_public, living)
    if os.environ.get("AUDIT"):
        seen=set()
        with open(os.environ["AUDIT"],"w") as fh:
            for pid,idx,n,page in stated:
                if (pid,idx) in seen: continue
                seen.add((pid,idx)); p=people[pid]
                got=len(fams[p.fams[min(idx,len(p.fams)-1)]].children) if p.fams else 0
                if got!=n: fh.write(f"p.{page}\t{pid}\t{p.name}\tfamily {idx+1}\tbook says {n}\tfound {got}\n")
    stats={"people":len(people),"families":len(fams),"living_hidden":len(living),
           "with_story":sum(1 for p in people.values() if any(k=="p" for k,_ in p.story)),
           "with_birth":sum(1 for p in people.values() if p.birth)}
    print(json.dumps(stats))

import os
PLACES=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"places.json")))
def geocode(place):
    first=re.sub(r"\s*\(.*","",place.split(",")[0]).strip()
    first=re.sub(r"^(near|probably|prob\.)\s+","",first)
    for k,v in PLACES.items():
        if "|" in k:
            nm,hint=k.split("|")
            if nm==first and hint in place: return v
    if first in PLACES: return PLACES[first]
    for k,v in PLACES.items():
        if "|" not in k and not k.startswith("_") and re.search(r"\b"+re.escape(k)+r"\b",place): return v
    return None

def ged_lines(level, tag, value):
    """Split long values into CONT (newline) / CONC (continuation) lines."""
    out=[]; first=True
    for para in str(value).split("\n"):
        chunks=[para[i:i+200] for i in range(0,len(para),200)] or [""]
        for j,ch in enumerate(chunks):
            if first: out.append(f"{level} {tag} {ch}".rstrip()); first=False
            elif j==0: out.append(f"{level+1} CONT {ch}".rstrip())
            else: out.append(f"{level+1} CONC {ch}")
    return out

def write_ged(path, living):
    L=["0 HEAD","1 SOUR HENRIE_RED_BOOK","2 NAME Red Book to GEDCOM converter","1 GEDC","2 VERS 5.5.1","2 FORM LINEAGE-LINKED","1 CHAR UTF-8",
       f"1 DATE {datetime.date.today().strftime('%d %b %Y').upper()}",
       "1 NOTE Converted from 'Ancestry and Descendants of William Henrie 1799-1883' by Manetta (Prince) Henrie (1954),",
       "2 CONT electronic edition by Ryan Henrie (2002). The Red Book is the primary source (@S1@).",
       "2 CONT Facts from later research are added with their own SOUR records and never replace the book's text."]
    if living: L.append("2 CONT Public copy: people who may be living show their name only.")
    def ev(tag, e, lvl=1):
        if not e: return []
        out=[f"{lvl} {tag}"]
        if e.get("date"): out.append(f"{lvl+1} DATE {e['date']}")
        if e.get("place"):
            out.append(f"{lvl+1} PLAC {e['place']}")
            g=geocode(e["place"])
            if g:
                out+=[f"{lvl+2} MAP", f"{lvl+3} LATI {'N' if g[0]>=0 else 'S'}{abs(g[0])}", f"{lvl+3} LONG {'E' if g[1]>=0 else 'W'}{abs(g[1])}"]
        if e.get("raw") and e.get("raw")!="young": out.append(f"{lvl+1} NOTE As written: {e['raw']}")
        if e.get("raw")=="young": out.append(f"{lvl+1} NOTE Died young")
        return out if len(out)>1 or tag in ("DEAT",) else []
    for p in people.values():
        L.append(f"0 @{p.id}@ INDI")
        given,sur=split_name(p.name)
        L.append(f"1 NAME {given} /{sur}/".replace("  "," "))
        if p.sex: L.append(f"1 SEX {p.sex}")
        if p.id in living:
            L.append("1 _LIVING Y")
        else:
            if p.title: L.append(f"1 TITL {p.title}")
            L+=ev("BIRT",p.birth); L+=ev("DEAT",p.death); L+=ev("BURI",p.burial)
            if p.note_parents: L+=ged_lines(1,"NOTE",f"Parents: {p.note_parents}")
            story="\n".join(t for k,t in p.story if k=="p")
            if story: L+=ged_lines(1,"NOTE",story)
            for k,t in p.story:
                if k=="ref": L+=ged_lines(1,"NOTE","References: "+re.sub(r'^References?\s*:\s*','',t))
            if p.ordinances: L+=ged_lines(1,"NOTE","LDS ordinances as recorded in the book: "+"; ".join(p.ordinances))
        L.append("1 SOUR @S1@"); L.append(f"2 PAGE {', '.join(str(x) for x in sorted(p.pages))}")
        if p.famc: L.append(f"1 FAMC @{p.famc}@")
        for fid in p.fams: L.append(f"1 FAMS @{fid}@")
    for f in fams.values():
        L.append(f"0 @{f.id}@ FAM")
        if f.husb: L.append(f"1 HUSB @{f.husb}@")
        if f.wife: L.append(f"1 WIFE @{f.wife}@")
        if f.marr and not ({f.husb,f.wife}&living):
            L+=ev("MARR",f.marr)
        for c in f.children: L.append(f"1 CHIL @{c}@")
    L+=["0 @S1@ SOUR","1 TITL Ancestry and Descendants of William Henrie, 1799-1883","1 AUTH Manetta (Prince) Henrie",
        "1 PUBL Provo, Utah, 1954. Electronic edition revised by Ryan Henrie, 7 Mar 2002.","0 TRLR"]
    open(path,"w",encoding="utf-8").write("\n".join(L)+"\n")

def split_name(n):
    n=re.sub(r"\s+"," ",n).strip()
    w=n.split(" ")
    suffix=""
    if w and w[-1].rstrip(".").lower() in ("jr","sr","ii","iii"): suffix=" "+w.pop()
    if len(w)==1: return w[0]+suffix,""
    return " ".join(w[:-1]), w[-1]+suffix if not suffix else w[-1]

if __name__=="__main__":
    run(*sys.argv[1:4])
