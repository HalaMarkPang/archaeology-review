(function () {
  if (!('IntersectionObserver' in window)) return;
  const masthead = document.querySelector('[data-masthead]');
  const hero = document.querySelector('.hero');
  const toTop = document.querySelector('[data-to-top]');
  const sentinel = document.createElement('div');
  sentinel.setAttribute('aria-hidden', 'true');
  sentinel.style.cssText = 'position:absolute;top:0;left:0;width:1px;height:1px;pointer-events:none';
  document.body.prepend(sentinel);
  new IntersectionObserver(([entry]) => masthead?.classList.toggle('scrolled', !entry.isIntersecting)).observe(sentinel);
  if (hero && toTop) new IntersectionObserver(([entry]) => toTop.classList.toggle('shown', !entry.isIntersecting)).observe(hero);

  const reveal = [...document.querySelectorAll('.genre-title, .record')];
  const revealer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) { entry.target.classList.add('in'); revealer.unobserve(entry.target); }
  }, { rootMargin: '0px 0px -4% 0px' });
  for (const el of reveal) { el.classList.add('reveal'); revealer.observe(el); }
  if (location.hash) document.getElementById(decodeURIComponent(location.hash.slice(1)))?.classList.add('in');

  const links = new Map([...document.querySelectorAll('[data-toc-id]')].map(a => [a.dataset.tocId, a]));
  if (links.size) {
    const spy = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        for (const a of links.values()) a.classList.remove('current');
        links.get(entry.target.id)?.classList.add('current');
      }
    }, { rootMargin: '-30% 0px -60% 0px' });
    for (const id of links.keys()) { const el = document.getElementById(id); if (el) spy.observe(el); }
  }
})();

(function () {
  const plates = document.querySelectorAll('.plate img');
  if (!plates.length || typeof HTMLDialogElement !== 'function') return;
  const dialog = document.createElement('dialog');
  dialog.className = 'lightbox';
  const close = document.createElement('button'); close.type = 'button'; close.setAttribute('aria-label', '关闭'); close.textContent = '×';
  const img = document.createElement('img');
  const caption = document.createElement('p');
  dialog.append(close, img, caption);
  document.body.append(dialog);
  dialog.addEventListener('click', () => dialog.close());
  for (const plate of plates) {
    const open = () => {
      img.src = plate.currentSrc || plate.src; img.alt = plate.alt;
      caption.textContent = plate.closest('figure')?.querySelector('figcaption')?.textContent || '';
      caption.hidden = !caption.textContent;
      dialog.showModal();
    };
    plate.tabIndex = 0;
    plate.setAttribute('role', 'button');
    plate.addEventListener('click', open);
    plate.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
  }
})();

(function () {
  const buttons = [...document.querySelectorAll('[data-filter]')];
  const search = document.querySelector('[data-record-search]');
  const cards = [...document.querySelectorAll('[data-record]')];
  const toc = [...document.querySelectorAll('[data-toc-id]')];
  let current = '全部';
  function apply() {
    const terms = (search?.value || '').trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    const visibleIds = new Set();
    for (const card of cards) {
      const visible = (current === '全部' || card.dataset.period === current) && terms.every(q => card.textContent.toLocaleLowerCase().includes(q));
      card.hidden = !visible;
      if (visible) visibleIds.add(card.id);
    }
    for (const link of toc) link.hidden = !visibleIds.has(link.dataset.tocId);
    for (const group of document.querySelectorAll('[data-genre]')) group.hidden = ![...group.querySelectorAll('[data-record]')].some(card => !card.hidden);
    for (const group of document.querySelectorAll('[data-toc-group]')) group.hidden = ![...group.querySelectorAll('[data-toc-id]')].some(link => !link.hidden);
    const empty = document.querySelector('[data-empty]');
    if (empty) empty.style.display = visibleIds.size ? 'none' : 'block';
    const count = document.querySelector('[data-count]');
    if (count) count.textContent = String(visibleIds.size);
  }
  for (const button of buttons) button.addEventListener('click', () => {
    current = button.dataset.filter;
    for (const other of buttons) { other.classList.toggle('active', other === button); other.setAttribute('aria-pressed', String(other === button)); }
    apply();
  });
  search?.addEventListener('input', apply);
  const global = document.querySelector('[data-global-search]');
  if (!global) return;
  const out = document.getElementById('global-results');
  let indexPromise;
  let serial = 0;
  global.addEventListener('input', async () => {
    const version = ++serial;
    const terms = global.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    out.replaceChildren();
    if (!terms.length) return;
    try {
      indexPromise ||= fetch(global.dataset.globalSearch).then(r => { if (!r.ok) throw new Error('search'); return r.json(); }).catch(e => { indexPromise = null; throw e; });
      const entries = await indexPromise;
      if (version !== serial) return;
      const matches = entries.filter(row => terms.every(term => [row.title, row.original_title, row.citation, row.body].join(' ').toLocaleLowerCase().includes(term)));
      const status = document.createElement('p'); status.className = 'meta'; status.textContent = matches.length ? `找到 ${matches.length} 篇文献` : '没有匹配的文献'; out.append(status);
      for (const row of matches.slice(0, 50)) {
        const a = document.createElement('a'); a.className = 'search-result';
        a.href = new URL('../' + row.url, location.href).href;
        const title = document.createElement('strong'); title.textContent = row.title;
        const citation = document.createElement('span'); citation.textContent = row.citation;
        a.append(title, citation); out.append(a);
      }
    } catch (e) { if (version === serial) out.textContent = '检索暂不可用，请稍后重试或按刊期浏览。'; }
  });
})();
