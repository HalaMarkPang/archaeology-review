'use strict';
(() => {
  document.body.classList.add('js');
  const root = document.body.dataset.root || '';
  const reader = document.querySelector('[data-issue-reader]');
  const search = document.querySelector('[data-global-search]');
  const archiveKey = 'archaeology:archive-position';
  const readArchive = () => {try {return JSON.parse(sessionStorage.getItem(archiveKey));} catch {return null;}};
  const saveArchive = state => {try {sessionStorage.setItem(archiveKey, JSON.stringify(state));} catch {}};
  const icon = name => {const img=document.createElement('img');img.className='icon';img.src=root+'static/icons/'+name+'.svg';img.alt='';img.setAttribute('aria-hidden','true');return img;};
  if (reader) {
    const articles = [...reader.querySelectorAll('[data-article]')];
    const searchTexts = articles.map(article=>[...article.querySelectorAll('.article-title,.article-byline,.core,.significance,.plate figcaption,.source-reference p')].map(node=>node.textContent).join(' ').toLowerCase());
    const toc = [...reader.querySelectorAll('[data-toc-id]')];
    const scroll = reader.querySelector('[data-reading-scroll]');
    const mobile = reader.querySelector('[data-mobile-toc]');
    const sidebar = reader.querySelector('.reader-toc');
    const filters = [...reader.querySelectorAll('[data-filter]')];
    const input = reader.querySelector('[data-record-search]');
    const clear = reader.querySelector('[data-record-clear]');
    const reset = reader.querySelector('[data-filter-reset]');
    const progress = reader.querySelector('[data-reading-progress]');
    const top = reader.querySelector('[data-back-top]');
    const picker = reader.querySelector('[data-issue-picker]');
    const trigger = reader.querySelector('[data-issue-trigger]');
    const options = [...picker.querySelectorAll('[data-issue-option]')];
    const nativePopover = typeof picker.showPopover === 'function';
    let active = 0, period = '全部', available = articles, pickerKeyboard = false;
    const closeToc = (focus=false) => {
      sidebar.classList.remove('toc-visible');mobile.setAttribute('aria-expanded','false');
      mobile.querySelector('span').textContent='本期目录';mobile.querySelector('img').src=root+'static/icons/list.svg';
      if(focus)mobile.focus();
    };
    const pickerOpen = () => nativePopover ? picker.matches(':popover-open') : picker.classList.contains('is-open');
    const positionPicker = () => {
      const rect=trigger.getBoundingClientRect(),width=Math.min(360,innerWidth-32);
      picker.style.setProperty('--picker-left',Math.max(16,Math.min(innerWidth-width-16,rect.left+rect.width/2-width/2))+'px');
      picker.style.setProperty('--picker-top',rect.bottom+12+'px');
    };
    const closePicker = (focus=false) => {
      if(nativePopover && pickerOpen())picker.hidePopover();
      else picker.classList.remove('is-open');
      trigger.setAttribute('aria-expanded','false');
      if(focus)trigger.focus({preventScroll:true});
    };
    const openPicker = (focus=false) => {
      closeToc();positionPicker();
      if(nativePopover)picker.showPopover();else picker.classList.add('is-open');
      trigger.setAttribute('aria-expanded','true');
      if(focus)(options.find(a=>a.hasAttribute('aria-current'))||options[0]).focus({preventScroll:true});
    };
    trigger.setAttribute('aria-expanded','false');
    if(nativePopover){
      picker.addEventListener('beforetoggle',e=>{if(e.newState==='open'){closeToc();positionPicker();}});
      picker.addEventListener('toggle',e=>{
        trigger.setAttribute('aria-expanded',String(e.newState==='open'));
        if(e.newState==='open'&&pickerKeyboard)(options.find(a=>a.hasAttribute('aria-current'))||options[0]).focus({preventScroll:true});
      });
    }else{
      trigger.addEventListener('click',e=>pickerOpen()?closePicker():openPicker(e.detail===0));
      document.addEventListener('pointerdown',e=>{if(!picker.contains(e.target)&&!trigger.contains(e.target))closePicker();});
    }
    trigger.addEventListener('click',e=>{pickerKeyboard=e.detail===0;});
    trigger.addEventListener('keydown',e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();e.stopPropagation();pickerKeyboard=true;openPicker(true);}});
    picker.querySelector('[data-picker-close]').addEventListener('click',e=>{e.preventDefault();closePicker(true);});
    picker.addEventListener('keydown',e=>{
      if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key)||!e.target.closest('[data-issue-option]'))return;
      e.preventDefault();e.stopPropagation();const at=options.indexOf(document.activeElement);
      const next=e.key==='Home'?0:e.key==='End'?options.length-1:(at+(e.key==='ArrowDown'?1:-1)+options.length)%options.length;
      options[next].focus();
    });
    options.forEach(a=>{if(a.hasAttribute('aria-current'))a.addEventListener('click',e=>{e.preventDefault();closePicker(true);});});
    document.addEventListener('focusin',e=>{if(pickerOpen()&&!picker.contains(e.target)&&!trigger.contains(e.target))closePicker();});
    window.addEventListener('resize',()=>{if(pickerOpen())positionPicker();});
    const remembered=readArchive(),archiveUrl=new URL(root+'archive/index.html',location.href);
    if(remembered && typeof remembered.url==='string'){
      try{
        const saved=new URL(remembered.url,location.origin);
        if(saved.origin===archiveUrl.origin&&saved.pathname===archiveUrl.pathname){
          reader.querySelectorAll('[data-archive-return]').forEach(a=>{
            a.href=saved.href;a.addEventListener('click',()=>saveArchive({...remembered,restore:true}));
          });
        }
      }catch{}
    }
    function updateNavigation(){
      const article=articles[active],list=available,index=list.indexOf(article);
      for(const [direction,offset] of [['prev',-1],['next',1]]){
        const next=list[index+offset],link=article.querySelector('[data-step="'+direction+'"]'),edge=article.querySelector('[data-nav-edge="'+direction+'"]');
        link.hidden=!next;edge.hidden=!!next;
        if(next){link.href='#'+next.id;link.querySelector('[data-nav-title]').textContent=next.querySelector('.article-title').textContent;}
        edge.textContent=!list.length?(direction==='prev'?'没有匹配条目':'清除筛选后继续阅读'):list.length===articles.length?(direction==='prev'?'已是本期第一篇':'已读至本期最后一篇'):(direction==='prev'?'已是筛选后的第一篇':'已读至筛选后的最后一篇');
      }
    }
    function show(id,{push=false,replace=false,focus=false,closeDirectory=false}={}){
      const next=articles.findIndex(a=>a.id===id);if(next<0)return;active=next;
      articles.forEach((a,i)=>{a.hidden=i!==active;});
      toc.forEach(a=>{const selected=a.dataset.tocId===id;a.classList.toggle('selected',selected);if(selected)a.setAttribute('aria-current','true');else a.removeAttribute('aria-current');});
      if(push)history.pushState(null,'','#'+id);else if(replace)history.replaceState(null,'','#'+id);
      scroll.scrollTop=0;progress.style.width='0%';top.hidden=true;
      if(closeDirectory)closeToc();
      updateNavigation();document.title=articles[active].querySelector('.article-title').textContent+' · 考古-周刊';
      if(focus)articles[active].querySelector('.article-title').focus({preventScroll:true});
    }
    const hashId=()=>{try{return decodeURIComponent(location.hash.slice(1));}catch{return '';}};
    show(articles.some(a=>a.id===hashId())?hashId():articles[0].id);
    reader.querySelectorAll('[data-toc-id],[data-article-link]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();show(a.hash.slice(1),{push:true,focus:true,closeDirectory:true});}));
    function filterToc(){
      const q=input.value.trim().toLowerCase();available=[];
      toc.forEach((a,i)=>{const article=articles[i],match=(period==='全部'||article.dataset.period===period)&&(!q||searchTexts[i].includes(q));a.parentElement.hidden=!match;if(match)available.push(article);});
      reader.querySelector('[data-toc-empty]').hidden=available.length>0;
      const narrowed=period!=='全部'||!!q;reset.hidden=!narrowed;clear.hidden=!q;
      reader.querySelector('[data-toc-count]').textContent=narrowed?available.length+' / '+articles.length+'篇':articles.length+'篇';
      if(available.length&&!available.includes(articles[active]))show(available[0].id,{replace:true});else updateNavigation();
    }
    function resetFilter(){period='全部';input.value='';filters.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter==='全部')));filterToc();}
    function syncHash(){const id=hashId();if(!articles.some(a=>a.id===id))return;if(!available.some(a=>a.id===id))resetFilter();show(id,{closeDirectory:true});}
    window.addEventListener('hashchange',syncHash);window.addEventListener('popstate',syncHash);
    filters.forEach(b=>b.addEventListener('click',()=>{period=b.dataset.filter;filters.forEach(f=>f.setAttribute('aria-pressed',String(f===b)));filterToc();}));
    input.addEventListener('input',filterToc);clear.addEventListener('click',()=>{input.value='';filterToc();input.focus();});reset.addEventListener('click',()=>{resetFilter();input.focus();});
    reader.querySelector('[data-toc-search-form]').addEventListener('submit',e=>e.preventDefault());
    mobile.addEventListener('click',()=>{
      const open=!sidebar.classList.contains('toc-visible');sidebar.classList.toggle('toc-visible',open);mobile.setAttribute('aria-expanded',String(open));
      mobile.querySelector('span').textContent=open?'收起目录':'本期目录';mobile.querySelector('img').src=root+'static/icons/'+(open?'x':'list')+'.svg';
      if(open)sidebar.querySelector('[aria-current]')?.scrollIntoView({block:'nearest'});
    });
    scroll.addEventListener('scroll',()=>{const max=scroll.scrollHeight-scroll.clientHeight,percent=max>0?Math.min(100,100*scroll.scrollTop/max):100;progress.style.width=percent+'%';top.hidden=percent<15;},{passive:true});
    top.addEventListener('click',()=>scroll.scrollTo({top:0,behavior:'smooth'}));
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape'){
        if(pickerOpen()){e.preventDefault();closePicker(true);}
        else if(sidebar.classList.contains('toc-visible')){e.preventDefault();closeToc(true);}
        else if(document.activeElement===input&&input.value){e.preventDefault();input.value='';filterToc();}
        return;
      }
      if(pickerOpen()||e.target.closest('[data-issue-picker]'))return;
      if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();if(matchMedia('(max-width:600px)').matches&&!sidebar.classList.contains('toc-visible'))mobile.click();input.focus();}
      if(e.target.closest('input,button,textarea,summary'))return;
      const current=articles[active],list=available,index=list.indexOf(current);
      if(e.key==='ArrowRight'&&list[index+1]){e.preventDefault();show(list[index+1].id,{push:true,focus:true,closeDirectory:true});}
      if(e.key==='ArrowLeft'&&list[index-1]){e.preventDefault();show(list[index-1].id,{push:true,focus:true,closeDirectory:true});}
    });
  }
  if(search){
    const shelf=document.querySelector('[data-archive-shelf]'),panel=document.querySelector('[data-search-results]'),list=document.querySelector('[data-result-list]'),count=document.querySelector('[data-search-count]'),empty=document.querySelector('[data-search-empty]'),clear=document.querySelector('[data-search-clear]');
    let records,load,seq=0;
    const highlight=(target,text,term)=>{const raw=String(text||''),at=raw.toLowerCase().indexOf(term.toLowerCase());if(at<0||!term){target.textContent=raw;return;}target.append(document.createTextNode(raw.slice(0,at)));const mark=document.createElement('mark');mark.textContent=raw.slice(at,at+term.length);target.append(mark,document.createTextNode(raw.slice(at+term.length)));};
    async function run(){
      const token=++seq,q=search.value.trim(),url=new URL(location.href);
      if(q)url.searchParams.set('q',q);else url.searchParams.delete('q');
      if(url.hash==='#site-search')url.hash='';history.replaceState(history.state,'',url.pathname+url.search+url.hash);
      clear.hidden=!q;shelf.hidden=!!q;panel.hidden=!q;list.replaceChildren();if(!q)return;
      empty.hidden=true;empty.querySelector('h3').textContent='没有匹配的文献';empty.querySelector('p').textContent='试试遗址、器物、作者或研究主题。';count.textContent='检索中…';
      try{
        if(!records){load=load||fetch(search.dataset.globalSearch).then(r=>{if(!r.ok)throw new Error('index');return r.json();}).catch(e=>{load=undefined;throw e;});records=await load;}
        if(token!==seq)return;
        const term=q.toLowerCase(),matches=records.filter(r=>[r.title,r.original_title,r.citation,r.body,r.period,r.kind].join(' ').toLowerCase().includes(term));count.textContent=matches.length+'篇';empty.hidden=matches.length>0;
        matches.forEach(r=>{const a=document.createElement('a');a.className='result-item';a.href=root+r.url;const date=document.createElement('span');date.className='result-date';date.textContent=r.issue_label||r.issue_id||'';const body=document.createElement('div'),meta=document.createElement('div');meta.className='result-meta';meta.textContent=[r.period,r.kind].filter(Boolean).join(' · ');const title=document.createElement('h3');highlight(title,r.title,q);const p=document.createElement('p'),full=String(r.body||'').replace(/\s+/g,' '),i=full.toLowerCase().indexOf(term),start=Math.max(0,i-35);highlight(p,(start?'…':'')+full.slice(start,start+130)+(full.length>start+130?'…':''),q);body.append(meta,title,p);a.append(date,body,icon('arrow-up-right'));list.append(a);});
      }catch{if(token!==seq)return;count.textContent='暂时无法检索';empty.hidden=false;empty.querySelector('h3').textContent='检索索引未能加载';empty.querySelector('p').textContent='请稍后重试，也可从刊期卡片进入阅读。';shelf.hidden=false;}
    }
    search.addEventListener('input',run);document.querySelector('[data-search-form]').addEventListener('submit',e=>{e.preventDefault();run();});
    const reset=()=>{search.value='';run();};clear.addEventListener('click',()=>{reset();search.focus();});document.querySelector('[data-search-close]').addEventListener('click',reset);
    document.addEventListener('keydown',e=>{if(e.key==='Escape'){reset();search.blur();}if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();search.focus();}});
    document.addEventListener('click',e=>{if(e.target.closest('[data-archive-shelf] a,[data-result-list] a'))saveArchive({url:location.pathname+location.search,scrollY:window.scrollY,restore:false});});
    const remembered=readArchive(),focusSearch=location.hash==='#site-search';
    search.value=new URLSearchParams(location.search).get('q')||'';
    const restore=remembered?.restore&&remembered.url===location.pathname+location.search;
    if(restore)saveArchive({...remembered,restore:false});
    run().then(()=>{if(focusSearch)search.focus();else if(restore)requestAnimationFrame(()=>window.scrollTo({top:remembered.scrollY||0,behavior:'instant'}));});
  }
})();
