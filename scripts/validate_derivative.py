#!/usr/bin/env python3
"""Independent parsed-artifact checks against the immutable published PDF and authority."""
from pathlib import Path
import argparse,hashlib,html,json,re,shutil,subprocess,sys,tempfile,unicodedata
from lxml import html as LH,etree
from pypdf import PdfReader
from markdown_it import MarkdownIt
import bibtexparser,rispy,yaml

def norm(s):return ' '.join(unicodedata.normalize('NFC',s).split())
def require(x,msg):
 if not x:raise AssertionError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read_bib(path):
 if hasattr(bibtexparser,'parse_file'):
  lib=bibtexparser.parse_file(path);require(not lib.failed_blocks,'Invalid BibTeX')
  return {x.key:{f.key:f.value for f in x.fields} for x in lib.entries}
 db=bibtexparser.loads(path.read_text())
 return {x['ID']:{k:v for k,v in x.items() if k not in ['ID','ENTRYTYPE']} for x in db.entries}
def validate(root,rebuild=True):
 root=Path(root);A=json.loads((root/'source/publication.json').read_text());B=json.loads((root/'bibliography.json').read_text())
 expected=[b['text'] for b in A['blocks']]
 require(A['doi']=='10.5281/zenodo.23540849','Wrong frozen edition')
 pdf=root/A['pdf_filename'];require(sha(pdf)==A['source_pdf_sha256']=='fc7583e903f1059c74e5474e5f4bca9ae479a41b3b3189af23ff27abbc866979','PDF bytes changed')
 r=PdfReader(pdf);require(len(r.pages)==3 and pdf.stat().st_size==73003,'Wrong PDF size/pages')
 extracted=[]
 for i,p in enumerate(r.pages,1):
  lines=[l for l in p.extract_text().splitlines() if l.strip()!=str(i) and l.strip()!=A['copyright']]
  extracted.append(' '.join(lines))
 require(norm(' '.join(extracted))==norm(' '.join(expected)),'Full PDF text differs from frozen block sequence')
 z=json.loads((root/'source/zenodo-record.json').read_text());require(z['metadata']['doi']==A['doi'] and z['metadata']['title']==A['title'],'Zenodo identity mismatch')
 require(z['files'][0]['checksum']=='md5:'+hashlib.md5(pdf.read_bytes()).hexdigest(),'Zenodo PDF checksum mismatch')
 md=MarkdownIt()
 def mdtexts(s):
  t=LH.fromstring('<main>'+md.render(s)+'</main>');return [norm(n.text_content()) for n in t if n.tag in ['h1','h2','p']]
 require(mdtexts((root/'paper.md').read_text())==expected+[A['copyright']],'Markdown complete ordered text mismatch')
 require((root/'paper.md').read_bytes()==(root/'who-else-wants-to-know.md').read_bytes(),'Named Markdown alias differs')
 readme=(root/'README.md').read_text();marker='## Canonical paper text\n\n';require(readme.count(marker)==1,'README manuscript marker missing/duplicated')
 require(mdtexts(readme.split(marker)[1])==expected+[A['copyright']],'README canonical text mismatch')
 h=(root/'index.html').read_text();p=LH.fromstring(h)
 src=p.xpath('//*[@data-source-block]');require([n.get('data-source-block') for n in src]==[str(i) for i in range(len(expected))],'Missing/duplicate/reordered source blocks')
 require([norm(n.text_content()) for n in src]==expected,'HTML complete text mismatch')
 for n in src:
  require(not n.xpath('ancestor-or-self::*[@hidden]'),'Hidden canonical text')
  require(all(not re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',v or '',re.I) for v in n.xpath('ancestor-or-self::*/@style')),'CSS-hidden canonical text')
 for i,b in enumerate(A['blocks']):
  for style,tag in [('bold','strong'),('italic','em')]:
   want=[x['text'].strip() for x in b['runs'] if x['style']==style and x['text'].strip()]
   require([n.text_content() for n in src[i].xpath('./'+tag)]==want,f'Emphasis mismatch at source block {i}')
 require(p.xpath('//h1/text()')==[] or norm(p.xpath('//h1')[0].text_content())==A['title'],'Wrong title')
 metas={'citation_title':A['title'],'citation_author':'Brad Pierce','citation_publication_date':A['publication_date'].replace('-','/'),'citation_doi':A['doi'],'citation_pdf_url':A['pdf_url'],'citation_fulltext_html_url':A['article_url'],'description':A['abstract'],'keywords':', '.join(A['keywords']),'DC.subject':', '.join(A['keywords'])}
 for k,v in metas.items():require(p.xpath('//meta[@name="'+k+'"]/@content')==[v],f'Metadata {k} missing/wrong/duplicated')
 require(p.xpath('//link[@rel="canonical"]/@href')==[A['article_url']],'Canonical mismatch')
 require(p.xpath('//meta[@property="og:title"]/@content')==[A['title']],'OG title mismatch')
 require(p.xpath('//meta[@property="og:url"]/@content')==[A['article_url']],'OG URL mismatch')
 require('bradpierce-ai-eda.github.io' not in h,'Legacy metadata host')
 require(h.index('id="scholarly-front-matter"')<h.index('id="relevance-and-citation-scope"')<h.index('id="canonical-paper"'),'Front matter order wrong')
 require(len(p.xpath('//*[@id="scholarly-front-matter"]//*[@data-source-block]'))==8,'Incomplete scholarly front matter')
 scope=p.xpath('//*[@id="relevance-and-citation-scope"]/p')
 require([norm(x.text_content()) for x in scope[:3]]==A['repository_framing']['scope'],'Scope paragraphs mismatch')
 for scope_text in A['repository_framing']['scope']:require(scope_text in readme.split(marker)[0],'README scope mismatch')
 for i in [1,2]:
  targets=p.xpath(f'//*[@id="canonical-paper"]//a[@href="#reference-{i}"]');require(len(targets)==1,'Citation destination missing or duplicated')
  require(p.xpath(f'//*[@id="reference-{i}"]'),'Reference anchor missing')
 require([norm(n.text_content()) for n in p.xpath('//*[@id="canonical-paper"]/h2')]==['References','AI Assistance and Editorial Responsibility'],'Published disclosure/reference order changed')
 for n in p.xpath('//*[@data-source-block]//a[starts-with(@href,"https://doi.org/")]'):
  require(n.get('href')==n.text_content(),'DOI label/destination mismatch')
 for name in ['paper.md','who-else-wants-to-know.md','CITATION.cff','citation.bib','references.md','references.bib','references.csl.json','references.ris','metadata.json','provenance.json']:
  require(A['article_url']+name in p.xpath('//a/@href') or name=='paper.md','Missing representation link: '+name)
 schema=json.loads(p.xpath('//script[@type="application/ld+json"]/text()')[0]);require(schema['@type']=='Article','Essay misclassified')
 for k,v in [('headline',A['title']),('alternativeHeadline',A['subtitle']),('datePublished',A['publication_date']),('abstract',A['abstract']),('keywords',A['keywords']),('url',A['article_url'])]:require(schema[k]==v,'JSON-LD '+k+' mismatch')
 require(schema['author']==[{'@type':'Person','name':'Brad Pierce','sameAs':'https://orcid.org/0009-0009-7427-2969'}],'Wrong JSON-LD author')
 C=yaml.safe_load((root/'CITATION.cff').read_text())
 for c in [C,C['preferred-citation']]:
  for k,v in [('title',A['title']),('date-released',A['publication_date']),('doi',A['doi']),('keywords',A['keywords']),('license',A['license'])]:require(c[k]==v,'CFF '+k+' mismatch')
  require(c['authors']==[{'family-names':'Pierce','given-names':'Brad','orcid':'https://orcid.org/0009-0009-7427-2969'}],'CFF authors mismatch')
 M=json.loads((root/'metadata.json').read_text())
 for k in ['title','subtitle','authors','publication_date','doi','abstract','keywords','resource_type','source_pdf_sha256']:require(M[k]==A[k],'JSON metadata '+k+' mismatch')
 L=read_bib(root/'citation.bib');require(len(L)==1,'Citation BibTeX invalid')
 F=next(iter(L.values()))
 for k,v in [('title',A['title']),('author','Pierce, Brad'),('date',A['publication_date']),('doi',A['doi']),('keywords','; '.join(A['keywords']))]:require(F[k]==v,'Citation BibTeX '+k+' mismatch')
 require(mdtexts((root/'references.md').read_text())==['References']+[s['published'] for s in B['slots']],'Published reference strings differ')
 require(len(B['works'])==len(B['slots'])==2,'Wrong bibliography counts')
 bib=read_bib(root/'references.bib');require(len(bib)==2,'Reference BibTeX invalid')
 csl=json.loads((root/'references.csl.json').read_text());ris=rispy.load((root/'references.ris').open())
 require(len(csl)==len(ris)==2,'Reference export count mismatch')
 for i,w in enumerate(B['works']):
  require(B['slots'][i]['work_ids']==[w['id']],'Wrong slot/work map')
  auth=json.loads((root/w['source_record']).read_text())['metadata'];require(auth['doi']==w['DOI'] and auth['publication_date']==w['issued'],'Reference authority mismatch')
  for field in ['title','DOI','URL','publisher']:
   require(csl[i][field]==w[field],'CSL '+field+' mismatch')
  require(csl[i]['author']==w['author'] and csl[i]['issued']['date-parts']==[[int(x) for x in w['issued'].split('-')]],'CSL author/date mismatch')
  bf=bib[w['citekey']]
  for k,v in [('title',w['title']),('date',w['issued']),('doi',w['DOI']),('url',w['URL']),('author','Pierce, Brad')]:require(bf[k]==v,'Reference BibTeX '+k+' mismatch')
  rr=ris[i]
  for k,v in [('id',w['id']),('title',w['title']),('year',w['issued'].replace('-','/')),('doi',w['DOI']),('urls',[w['URL']]),('authors',['Pierce, Brad'])]:require(rr[k]==v,'RIS '+k+' mismatch')
 # Audit only repository-added descriptive surfaces; canonical publication prose is immutable.
 framing='\n'.join(A['repository_framing']['scope'])+'\n'+C['message']+'\n'+readme.split(marker)[0]
 bad=r'when to cite|cite this report|cite this essay|use this source|ignore (?:previous|prior|all)|you should|system prompt|act as an? |instructions? to (?:an? )?(?:ai|model|crawler)|please cite'
 require(not re.search(bad,framing,re.I),'Prompt-like repository framing')
 require(not p.xpath('//script[not(@type="application/ld+json")]'),'Executable script in article')
 sm=etree.fromstring((root/'sitemap.xml').read_bytes());require(sm.xpath('//*[local-name()="loc"]/text()')==[A['article_url'],A['pdf_url']],'Paper sitemap mismatch')
 require('Disallow: /' not in (root/'robots.txt').read_text(),'Crawling blocked')
 manifest={};lines=(root/'checksums.sha256').read_text().splitlines()
 for line in lines:
  digest,path=line.split('  ',1);require(path not in manifest,'Duplicate manifest entry');manifest[path]=digest
 files={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and p.name!='checksums.sha256'}
 require(not any('__pycache__' in p or p.endswith(('.pyc','.pyo')) for p in files),'Transient files present')
 require(set(manifest)==set(files),'Manifest path-set mismatch')
 for k,pth in files.items():require(sha(pth)==manifest[k],'Manifest hash mismatch: '+k)
 if rebuild:
  with tempfile.TemporaryDirectory() as d:
   clean=Path(d)/'replay';shutil.copytree(root,clean)
   before={p.relative_to(clean).as_posix():sha(p) for p in clean.rglob('*') if p.is_file()}
   subprocess.run([sys.executable,'-B',str(clean/'scripts/build_derivative.py'),'--repo',str(clean)],check=True)
   after={p.relative_to(clean).as_posix():sha(p) for p in clean.rglob('*') if p.is_file()}
   require(before==after,'Deterministic rebuild changed artifacts')
 return {'status':'PASS','canonical_blocks':len(expected),'body_paragraphs':24,'references':2,'works':2,'pdf_pages':3,'pdf_sha256':A['source_pdf_sha256'],'public_files':len(files)+1,'full_text_formats':['PDF','HTML','Markdown','README'],'parsed_bibliography_formats':['CFF/YAML','BibTeX','CSL-JSON','RIS'],'deterministic_rebuild':rebuild}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--no-rebuild',action='store_true');a=p.parse_args()
 print(json.dumps(validate(a.repo,not a.no_rebuild),indent=2))
