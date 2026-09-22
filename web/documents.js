// A deliberately limited Markdown reader. Raw HTML is always text, never executable.
(function(root){
'use strict';
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function destination(value,name,image=false){
 if(/[\x00-\x20\\]/.test(value))return null;
 let url;try{url=new URL(value,'https://sentinel.invalid/'+name)}catch{return null}
 if(url.origin!=='https://sentinel.invalid')return !image&&['http:','https:'].includes(url.protocol)&&!url.username&&!url.password?url.href:null;
 if(image)return /^\/docs\/screenshots\/[a-z0-9-]+\.png$/.test(url.pathname)?url.pathname:null;
 if(value.startsWith('#'))return url.hash;
 if(['/README.md','/FINAL_STATUS.md'].includes(url.pathname)||/^\/docs\/[a-z0-9-]+\.md$/.test(url.pathname))return '/documentation.html?doc='+encodeURIComponent(url.pathname.slice(1))+url.hash;
 if(url.pathname==='/portfolio/verification.json')return '/api/portfolio/verification';
 return null;
}
function inline(text,name,depth=0){
 if(depth>3)return escape(text);
 const tokens=/(`[^`\n]+`|!?\[[^\]\n]*\]\([^\s)]+\)|\*\*[^*\n]+\*\*)/g;let html='',offset=0;
 for(const m of text.matchAll(tokens)){
  html+=escape(text.slice(offset,m.index));const t=m[0];offset=m.index+t.length;
  if(t.startsWith('`'))html+='<code>'+escape(t.slice(1,-1))+'</code>';
  else if(t.startsWith('**'))html+='<strong>'+inline(t.slice(2,-2),name,depth+1)+'</strong>';
  else{const parts=/^(!?)\[([^\]]*)\]\(([^)]+)\)$/.exec(t),img=!!parts[1],url=destination(parts[3],name,img),label=escape(parts[2]);
   if(!url)html+=`<span title="Reference unavailable in the public reader">${label}</span>`;
   else if(img)html+=`<img src="${escape(url)}" alt="${label}" loading="lazy">`;
   else html+=`<a href="${escape(url)}"${url.startsWith('http')?' target="_blank" rel="noopener noreferrer"':''}>${inline(parts[2],name,depth+1)}</a>`;
  }
 }
 return html+escape(text.slice(offset));
}
function render(source,name='README.md'){
 const lines=String(source).replace(/\r\n?/g,'\n').split('\n'),out=[],headings=[],used=new Map();let i=0;
 const cells=line=>line.trim().replace(/^\||\|$/g,'').split('|').map(s=>s.trim());
 const divider=line=>/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line||'');
 const block=line=>/^\s*$|^#{1,6}\s|^```|^\s*[-*]\s|^\s*\d+\.\s|^>\s?|^---+$/.test(line||'');
 while(i<lines.length){
  const line=lines[i];if(!line.trim()){i++;continue}
  if(line.startsWith('```')){const language=line.slice(3).trim(),code=[];i++;while(i<lines.length&&!lines[i].startsWith('```'))code.push(lines[i++]);i++;out.push(`<pre><code data-language="${escape(language)}">${escape(code.join('\n'))}</code></pre>`);continue}
  const h=/^(#{1,6})\s+(.+)$/.exec(line);
  if(h){const label=h[2].replace(/[`*]/g,''),base=label.toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu,'').trim().replace(/\s+/g,'-')||'section',count=used.get(base)||0,id=base+(count?'-'+count:'');used.set(base,count+1);headings.push({level:h[1].length,label,id});out.push(`<h${h[1].length} id="${escape(id)}">${inline(h[2],name)}</h${h[1].length}>`);i++;continue}
  if(line.includes('|')&&divider(lines[i+1])){const header=cells(line),rows=[];i+=2;while(i<lines.length&&lines[i].includes('|')&&lines[i].trim())rows.push(cells(lines[i++]));out.push('<div class="table-wrap"><table><thead><tr>'+header.map(c=>'<th scope="col">'+inline(c,name)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+header.map((_,n)=>'<td>'+inline(row[n]||'',name)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>');continue}
  if(/^\s*[-*]\s/.test(line)||/^\s*\d+\.\s/.test(line)){const ordered=/^\s*\d+\.\s/.test(line),tag=ordered?'ol':'ul',pattern=ordered?/^\s*\d+\.\s+/:/^\s*[-*]\s+/,rows=[];while(i<lines.length&&pattern.test(lines[i]))rows.push(lines[i++].replace(pattern,''));out.push('<'+tag+'>'+rows.map(r=>'<li>'+inline(r,name)+'</li>').join('')+'</'+tag+'>');continue}
  if(/^>\s?/.test(line)){const rows=[];while(i<lines.length&&/^>/.test(lines[i]))rows.push(lines[i++].replace(/^>\s?/,''));out.push('<blockquote>'+inline(rows.join(' '),name)+'</blockquote>');continue}
  if(/^---+$/.test(line)){out.push('<hr>');i++;continue}
  const paragraph=[line];i++;while(i<lines.length&&!block(lines[i])&&!divider(lines[i+1]))paragraph.push(lines[i++]);out.push('<p>'+inline(paragraph.join(' '),name)+'</p>');
 }
 return {html:out.join('\n'),headings};
}
const api={render,destination};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.SentinelDocuments=api;
})(typeof globalThis!=='undefined'?globalThis:this);
