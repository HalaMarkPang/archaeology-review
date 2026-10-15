(function(){
  const buttons=[...document.querySelectorAll('[data-filter]')];
  const search=document.querySelector('[data-record-search]');
  const cards=[...document.querySelectorAll('[data-record]')];
  const empty=document.querySelector('[data-empty]');
  let current='全部';
  function apply(){
    const q=(search?.value||'').trim().toLocaleLowerCase();let n=0;
    for(const card of cards){
      const yes=(current==='全部'||card.dataset.period===current)&&(!q||card.textContent.toLocaleLowerCase().includes(q));
      card.classList.toggle('hidden',!yes);if(yes)n++;
    }
    for(const section of document.querySelectorAll('[data-genre]')){
      const visible=[...section.querySelectorAll('[data-record]')].some(card=>!card.classList.contains('hidden'));
      section.classList.toggle('hidden',!visible);
    }
    if(empty)empty.style.display=n?'none':'block';
    const el=document.querySelector('[data-count]');if(el)el.textContent=String(n);
  }
  for(const b of buttons)b.addEventListener('click',()=>{current=b.dataset.filter;for(const x of buttons){x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b))}apply()});
  if(search)search.addEventListener('input',apply);
  const toc=document.querySelector('.toc');
  const layout=document.querySelector('.issue-layout');
  if(toc&&layout){
    let lock=0;
    const doc=document.scrollingElement;
    function span(){
      const start=Math.max(0,layout.offsetTop-76);
      const end=Math.max(start,layout.offsetTop+layout.offsetHeight-doc.clientHeight);
      return {start,end};
    }
    toc.addEventListener('scroll',()=>{
      if(lock)return;
      const room=toc.scrollHeight-toc.clientHeight;
      if(room<=0)return;
      const {start,end}=span();
      lock=1;
      doc.scrollTop=start+(end-start)*(toc.scrollTop/room);
      lock=0;
    },{passive:true});
    document.addEventListener('scroll',()=>{
      if(lock)return;
      const room=toc.scrollHeight-toc.clientHeight;
      if(room<=0)return;
      const {start,end}=span();
      const ratio=end===start?0:(doc.scrollTop-start)/(end-start);
      lock=1;
      toc.scrollTop=Math.min(1,Math.max(0,ratio))*room;
      lock=0;
    },{passive:true});
  }
})();
