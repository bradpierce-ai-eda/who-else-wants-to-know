#!/usr/bin/env python3
"""Deterministic format conversion of the frozen Zenodo publication; no network access."""
from pathlib import Path
import argparse,hashlib,html,json,re,datetime


def render(root):
 root=Path(root)
 A=json.loads((root/'source/publication.json').read_text())
 B=json.loads((root/'bibliography.json').read_text())
 e=html.escape
 def write(name,text):
  (root/name).write_text(text,encoding='utf-8')
 def js(name,obj):write(name,json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
 def inline(block,fmt):
  out=''
  for r in block['runs']:
   t=r['text'];lead=t[:len(t)-len(t.lstrip())];tail=t[len(t.rstrip()):];core=t.strip()
   if not core:out+=t;continue
   if fmt=='html':
    t=e(core);tag={'bold':'strong','italic':'em'}.get(r['style']);out+=lead+(f'<{tag}>{t}</{tag}>' if tag else t)+tail
   else:
    mark={'bold':'**','italic':'*'}.get(r['style'],'');out+=lead+mark+core+mark+tail
  if fmt=='html':
   out=re.sub(r'https://doi\.org/[0-9.]+/zenodo\.[0-9]+',lambda m:f'<a href="{m[0]}">{m[0]}</a>',out)
   if block['role']=='paragraph':out=re.sub(r'\[([12])\]',r'<a href="#reference-\1">[\1]</a>',out)
  else:
   out=re.sub(r'https://doi\.org/[0-9.]+/zenodo\.[0-9]+',lambda m:f'[{m[0]}]({m[0]})',out)
  return out
 def mdblock(b):
  prefix='# ' if b['role']=='title' else '## ' if b['role']=='heading' else ''
  return prefix+inline(b,'md')
 def htmlblock(b,i):
  tag='h1' if b['role']=='title' else 'h2' if b['role']=='heading' else 'p'
  ident=f'block-{i:03}'
  if b['role']=='reference':ident='reference-'+re.match(r'\[(\d+)\]',b['text'])[1]
  return f'<{tag} id="{ident}" data-source-block="{i}">{inline(b,"html")}</{tag}>'
 citation=f"Pierce, Brad. (2026). {A['title']} Zenodo. https://doi.org/{A['doi']}"
 source_md='\n\n'.join(mdblock(b) for b in A['blocks'])+'\n\n'+A['copyright']+'\n'
 write('paper.md',source_md)
 write('who-else-wants-to-know.md',source_md)
 scope=A['repository_framing']['scope']
 prefix=f"# {A['title']}\n\n{A['subtitle']}\n\nBrad Pierce · Published {A['publication_date']} · ORCID [0009-0009-7427-2969](https://orcid.org/0009-0009-7427-2969)\n\n**Publication of record:** https://doi.org/{A['doi']} · [Zenodo record]({A['record_url']})\n\n**Preferred citation:** {citation}\n\n[Complete static HTML]({A['article_url']}) · [Published PDF]({A['pdf_url']}) · [Full Markdown]({A['article_url']}who-else-wants-to-know.md)\n\n## Relevance and citation scope\n\n"+'\n\n'.join(scope)+'\n\n## Bibliography and provenance\n\nThe exact published [references](references.md), normalized [bibliography](bibliography.json), [BibTeX](references.bib), [CSL JSON](references.csl.json) and [RIS](references.ris) are separate from this essay’s [preferred citation](citation.bib). The [provenance record](provenance.json) identifies the frozen Zenodo edition and representation changes.\n\n## Canonical paper text\n\n'
 write('README.md',prefix+source_md)
 blocks=A['blocks'];front='\n'.join(htmlblock(b,i) for i,b in enumerate(blocks[:8]));body='\n'.join(htmlblock(b,i) for i,b in enumerate(blocks[8:],8))
 scopehtml='\n'.join('<p>'+e(t)+'</p>' for t in scope)
 schema={'@context':'https://schema.org','@type':'Article','headline':A['title'],'alternativeHeadline':A['subtitle'],'author':[{'@type':'Person','name':a['name'],'sameAs':'https://orcid.org/'+a['orcid']} for a in A['authors']],'datePublished':A['publication_date'],'identifier':'https://doi.org/'+A['doi'],'sameAs':A['record_url'],'url':A['article_url'],'encoding':{'@type':'MediaObject','contentUrl':A['pdf_url'],'encodingFormat':'application/pdf'},'abstract':A['abstract'],'keywords':A['keywords'],'license':'https://creativecommons.org/licenses/by-nc/4.0/','inLanguage':'en','publisher':{'@type':'Organization','name':'Zenodo'}}
 metas={'citation_title':A['title'],'citation_author':'Brad Pierce','citation_publication_date':A['publication_date'].replace('-','/'),'citation_doi':A['doi'],'citation_pdf_url':A['pdf_url'],'citation_fulltext_html_url':A['article_url'],'description':A['abstract'],'keywords':', '.join(A['keywords']),'DC.subject':', '.join(A['keywords']),'DC.publisher':'Zenodo','robots':'index, follow'}
 metahtml='\n'.join(f'<meta name="{k}" content="{e(v,quote=True)}">' for k,v in metas.items())
 page=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(A['title'])} | Brad Pierce</title>
{metahtml}
<link rel="canonical" href="{A['article_url']}">
<link rel="alternate" type="text/markdown" href="{A['article_url']}who-else-wants-to-know.md">
<meta property="og:title" content="{e(A['title'],quote=True)}"><meta property="og:description" content="{e(A['abstract'],quote=True)}"><meta property="og:type" content="article"><meta property="og:url" content="{A['article_url']}">
<script type="application/ld+json">{json.dumps(schema,ensure_ascii=False).replace('</','<\\/')}</script>
<style>body{{font:1.1rem/1.6 Georgia,serif;color:#202020;max-width:52rem;margin:2.5rem auto;padding:0 1.2rem;overflow-wrap:anywhere}}h1{{font-size:2.1rem;line-height:1.2}}h2{{font-size:1.4rem;margin-top:1.7rem}}a{{color:#174f78}}aside{{border-left:3px solid #bbb;padding:0.3rem 1rem;margin:1.5rem 0}}footer{{border-top:1px solid #ddd;margin-top:2rem;padding-top:1rem}}@media(max-width:600px){{body{{font-size:1rem;margin:1.5rem auto}}h1{{font-size:1.8rem}}}}</style>
</head><body><article>
<header id="scholarly-front-matter">
{front}
</header>
<aside id="relevance-and-citation-scope"><h2>Relevance and citation scope</h2>
{scopehtml}
<p>Preferred citation: {e(citation).replace('https://doi.org/'+A['doi'],'<a href="https://doi.org/'+A['doi']+'">https://doi.org/'+A['doi']+'</a>')}</p>
<p><a href="{A['pdf_url']}">Published PDF</a> · <a href="{A['article_url']}who-else-wants-to-know.md">Full Markdown</a> · <a href="{A['article_url']}paper.md">Legacy Markdown filename</a> · <a href="{A['article_url']}CITATION.cff">CFF citation</a> · <a href="{A['article_url']}citation.bib">BibTeX citation</a> · <a href="{A['article_url']}references.md">Published references</a> · <a href="{A['article_url']}references.bib">Reference BibTeX</a> · <a href="{A['article_url']}references.csl.json">Reference CSL JSON</a> · <a href="{A['article_url']}references.ris">Reference RIS</a> · <a href="{A['article_url']}metadata.json">Metadata</a> · <a href="{A['article_url']}provenance.json">Provenance</a></p>
</aside>
<section id="canonical-paper">
{body}
</section>
<footer>{e(A['copyright'])} · <a href="https://creativecommons.org/licenses/by-nc/4.0/">License</a></footer>
</article></body></html>
'''
 write('index.html',page)
 cff={'cff-version':'1.2.0','message':'The DOI-linked Zenodo edition is the publication of record.','type':'generic','title':A['title'],'authors':[{'family-names':'Pierce','given-names':'Brad','orcid':'https://orcid.org/0009-0009-7427-2969'}],'date-released':A['publication_date'],'doi':A['doi'],'url':'https://doi.org/'+A['doi'],'license':A['license'],'keywords':A['keywords']}
 cff['preferred-citation']={k:v for k,v in cff.items() if k not in ['cff-version','message','preferred-citation']}
 # JSON syntax is valid YAML 1.2 and preserves exact strings in the CFF document.
 js('CITATION.cff',cff)
 metadata={k:v for k,v in A.items() if k not in ['blocks','repository_framing']};metadata['preferred_citation']=citation
 js('metadata.json',metadata)
 def bib(key,title,date,doi,keywords=None,note=None):
  f={'author':'Pierce, Brad','title':title,'year':date[:4],'month':str(int(date[5:7])),'day':str(int(date[8:10])),'date':date,'publisher':'Zenodo','doi':doi,'url':'https://doi.org/'+doi}
  if keywords:f['keywords']='; '.join(keywords)
  if note:f['note']=note
  return '@misc{'+key+',\n'+',\n'.join('  '+k+' = {'+v+'}' for k,v in f.items())+'\n}\n'
 write('citation.bib',bib('pierce2026whoelse',A['title'],A['publication_date'],A['doi'],A['keywords'],'Speculative essay'))
 write('references.md','# References\n\n'+'\n\n'.join(inline(b,'md') for b in blocks if b['role']=='reference')+'\n')
 write('references.bib','\n'.join(bib(w['citekey'],w['title'],w['issued'],w['DOI'],note='Report archived on Zenodo') for w in B['works']))
 js('references.csl.json',[{'id':w['id'],'type':w['type'],'title':w['title'],'author':w['author'],'issued':{'date-parts':[[int(x) for x in w['issued'].split('-')]]},'publisher':w['publisher'],'DOI':w['DOI'],'URL':w['URL']} for w in B['works']])
 ris=''
 for w in B['works']:
  ris+='TY  - RPRT\nID  - '+w['id']+'\nAU  - Pierce, Brad\nTI  - '+w['title']+'\nPY  - '+w['issued'].replace('-','/')+'\nPB  - Zenodo\nDO  - '+w['DOI']+'\nUR  - '+w['URL']+'\nER  - \n\n'
 write('references.ris',ris)
 prov={'source_doi':A['doi'],'source_record':A['record_url'],'source_pdf_url':A['source_pdf_url'],'source_filename':A['pdf_filename'],'source_pdf_sha256':A['source_pdf_sha256'],'source_pdf_md5':A['source_pdf_md5'],'source_bytes':A['source_pdf_size'],'source_pages':A['source_page_count'],'source_blocks':len(blocks),'generated_utc':A['generation_date_utc'],'normalization':A['normalization'],'manual_corrections':A['manual_corrections'],'transformation':'PDF text and font runs frozen in source/publication.json with independent full-paragraph comparison against the approved authoring source; deterministic offline HTML, Markdown and bibliography conversion','validation':{'required_command':'python scripts/validate_derivative.py --repo .','status_record':'Private release-review report; PASS is established by executing validation, not this metadata'},'original_section_order':'References then AI Assistance and Editorial Responsibility, exactly as the deposited PDF','keyword_mapping':{'paper_keywords':A['keywords'],'zenodo_free_keywords':A['zenodo_free_keywords'],'controlled_subjects':A['controlled_subjects']},'rebuild':'python scripts/build_derivative.py --repo .'}
 js('provenance.json',prov)
 write('sitemap.xml','<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join('  <url><loc>'+u+'</loc></url>\n' for u in [A['article_url'],A['pdf_url']])+'</urlset>\n')
 write('robots.txt','User-agent: *\nAllow: /\nSitemap: '+A['article_url']+'sitemap.xml\n')
 write('.nojekyll','')
 write('LICENSE','© 2026 Brad Pierce\nCreative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)\nhttps://creativecommons.org/licenses/by-nc/4.0/\n')
 files=sorted(p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and p.suffix not in ['.pyc','.pyo'] and p.name!='checksums.sha256')
 write('checksums.sha256',''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in files))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',default=Path(__file__).resolve().parents[1],type=Path);a=p.parse_args();render(a.repo)
