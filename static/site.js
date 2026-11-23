'use strict';
(() => {
  document.body.classList.add('js');
  const root = document.body.dataset.root || '';
  const reader = document.querySelector('[data-issue-reader]');
  const search = document.querySelector('[data-global-search]');
  const icon = name => {const img=document.createElement('img');img.className='icon';img.src=root+'static/icons/'+name+'.svg';img.alt='';img.setAttribute('aria-hidden','true');return img;};
  if (reader) {
    const articles=[...reader.querySelectorAll('[data-article]')];
    const toc=[...reader.querySelectorAll('[data-toc-id]')];
    const scroll=reader.querySelector('[data-reading-scroll]');
    const mobile=reader.querySelector('[data-mobile-toc]');
    const sidebar=reader.querySelector('.reader-toc');
    const filters=[...reader.querySelectorAll('[data-filter]')];
    const input=reader.querySelector('[data-record-search]');
    const progress=reader.querySelector('[data-reading-progress]');
    const top=reader.querySelector('[data-back-top]');
    const returnUrl=root+'archive/index.html';
    let active=0, period='全部';
    const closeToc=()=>{sidebar.classList.remove('toc-visible');mobile.setAttribute('aria-expanded','false');mobile.querySelector('span').textContent='本期目录';mobile.querySelector('img').src=root+'static/icons/list.svg';};
    function show(id,push=false){
      const next=articles.findIndex(a=>a.id===id);active=next>=0?next:0;
      articles.forEach((a,i)=>{a.hidden=i!==active;});
      toc.forEach(a=>{const selected=a.dataset.tocId===articles[active].id;a.classList.toggle('selected',selected);if(selected)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current');});
      if(push)history.pushState(null,'','#'+articles[active].id);
      scroll.scrollTop=0;progress.style.width='0%';top.hidden=true;closeToc();
      document.title=articles[active].querySelector('.article-title').textContent+' · 考古-周刊';
    }
    const hashId=()=>{try{return decodeURIComponent(location.hash.slice(1));}catch{return '';}};
    show(hashId());
    reader.querySelectorAll('[data-toc-id],[data-article-link]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();show(a.hash.slice(1),true);}));
    window.addEventListener('hashchange',()=>show(hashId()));window.addEventListener('popstate',()=>show(hashId()));
    reader.querySelector('[data-issue-select]').addEventListener('change',e=>{location.href=e.target.value;});
    function filterToc(){
      const q=(input.value||'').trim().toLowerCase();let count=0;
      toc.forEach(a=>{const article=articles.find(r=>r.id===a.dataset.tocId);const match=(period==='全部'||article.dataset.period===period)&&(!q||article.textContent.toLowerCase().includes(q));a.parentElement.hidden=!match;if(match)count++;});
      reader.querySelector('[data-toc-empty]').hidden=count>0;
    }
    filters.forEach(b=>b.addEventListener('click',()=>{period=b.dataset.filter;filters.forEach(f=>f.setAttribute('aria-pressed',String(f===b)));filterToc();}));
    input.addEventListener('input',filterToc);reader.querySelector('[data-toc-search-form]').addEventListener('submit',e=>e.preventDefault());
    mobile.addEventListener('click',()=>{const open=!sidebar.classList.contains('toc-visible');sidebar.classList.toggle('toc-visible',open);mobile.setAttribute('aria-expanded',String(open));mobile.querySelector('span').textContent=open?'收起目录':'本期目录';mobile.querySelector('img').src=root+'static/icons/'+(open?'x':'list')+'.svg';});
    scroll.addEventListener('scroll',()=>{const max=scroll.scrollHeight-scroll.clientHeight;const percent=max>0?Math.min(100,100*scroll.scrollTop/max):100;progress.style.width=percent+'%';top.hidden=percent<15;},{passive:true});
    top.addEventListener('click',()=>scroll.scrollTo({top:0,behavior:'smooth'}));
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape'){if(sidebar.classList.contains('toc-visible'))closeToc();else location.href=returnUrl;}
      if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();input.focus();}
      if(e.target.closest('input,select,textarea,summary'))return;
      if(e.key==='ArrowRight'&&active<articles.length-1){e.preventDefault();show(articles[active+1].id,true);}
      if(e.key==='ArrowLeft'&&active>0){e.preventDefault();show(articles[active-1].id,true);}
    });
  }
  if(search){
    const shelf=document.querySelector('[data-archive-shelf]'),panel=document.querySelector('[data-search-results]'),list=document.querySelector('[data-result-list]'),count=document.querySelector('[data-search-count]'),empty=document.querySelector('[data-search-empty]'),clear=document.querySelector('[data-search-clear]');
    let records,load,seq=0;
    const highlight=(target,text,term)=>{const raw=String(text||'');const at=raw.toLowerCase().indexOf(term.toLowerCase());if(at<0||!term){target.textContent=raw;return;}target.append(document.createTextNode(raw.slice(0,at)));const mark=document.createElement('mark');mark.textContent=raw.slice(at,at+term.length);target.append(mark,document.createTextNode(raw.slice(at+term.length)));};
    async function run(){
      const token=++seq,q=search.value.trim();clear.hidden=!q;shelf.hidden=!!q;panel.hidden=!q;list.replaceChildren();if(!q)return;
      empty.hidden=true;empty.querySelector('h3').textContent='没有匹配的文献';empty.querySelector('p').textContent='试试遗址、器物、作者或研究主题。';count.textContent='检索中…';
      try{
        if(!records){load=load||fetch(search.dataset.globalSearch).then(r=>{if(!r.ok)throw new Error('index');return r.json();}).catch(e=>{load=undefined;throw e;});records=await load;}
        if(token!==seq)return;
        const term=q.toLowerCase(),matches=records.filter(r=>[r.title,r.original_title,r.citation,r.body,r.period,r.kind].join(' ').toLowerCase().includes(term));count.textContent=matches.length+'篇';empty.hidden=matches.length>0;
        matches.forEach(r=>{const a=document.createElement('a');a.className='result-item';a.href=root+r.url;const date=document.createElement('span');date.className='result-date';date.textContent=r.issue_label||r.issue_id||'';const body=document.createElement('div');const meta=document.createElement('div');meta.className='result-meta';meta.textContent=[r.period,r.kind].filter(Boolean).join(' · ');const title=document.createElement('h3');highlight(title,r.title,q);const p=document.createElement('p');const full=String(r.body||'').replace(/\s+/g,' '),i=full.toLowerCase().indexOf(term),start=Math.max(0,i-35);highlight(p,(start?'…':'')+full.slice(start,start+130)+(full.length>start+130?'…':''),q);body.append(meta,title,p);a.append(date,body,icon('arrow-up-right'));list.append(a);});
      }catch{if(token!==seq)return;count.textContent='暂时无法检索';empty.hidden=false;empty.querySelector('h3').textContent='检索索引未能加载';empty.querySelector('p').textContent='请稍后重试，也可从刊期卡片进入阅读。';shelf.hidden=false;}
    }
    search.addEventListener('input',run);document.querySelector('[data-search-form]').addEventListener('submit',e=>{e.preventDefault();run();});
    const reset=()=>{search.value='';run();};clear.addEventListener('click',()=>{reset();search.focus();});document.querySelector('[data-search-close]').addEventListener('click',reset);
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){reset();search.blur();}if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();search.focus();}});
  }
})();
