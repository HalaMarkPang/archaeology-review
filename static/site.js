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
