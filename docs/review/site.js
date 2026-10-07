// The public review site's data adapter: the review page (review.html) asks BLITZ_API for the
// puzzle list, a puzzle, and to save a decision; here those come from Supabase (who checked what)
// and from the packet files in storage (R2). Settings are in config.js (window.BLITZ_SITE).
(function () {
  const cfg = window.BLITZ_SITE;
  const sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
  let user = null, rows = {}, onAuth = () => {};
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
  const base = x => (rows[x] && rows[x].base_url) || `${cfg.filesBase}/${x.replace(/\d.*/, '')}/${x}`;
  const getJSON = async url => { const r = await fetch(url, {cache: 'no-cache'}); if (!r.ok) throw new Error(url); return r.json(); };

  async function decisionsOf(x) {  // this helper's decisions on one puzzle, in the page's shape
    const d = {items: {}, notes: {}, verdict: '', note: '', reports: {}};
    if (!user) return d;
    const [dec, ver, rep] = await Promise.all([
      sb.from('decisions').select('item,decision,note').eq('xdid', x),
      sb.from('verdicts').select('verdict,note').eq('xdid', x),
      sb.from('reports').select('target,text').eq('xdid', x)]);
    for (const r of dec.data || []) { d.items[r.item] = r.decision; if (r.note) d.notes[r.item] = r.note; }
    if ((ver.data || [])[0]) { d.verdict = ver.data[0].verdict; d.note = ver.data[0].note; }
    for (const r of rep.data || []) d.reports[r.target] = r.text;
    return d;
  }

  function signInForm(el, why) {
    el.innerHTML = `<form class="signin" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap">
      <span class="muted" style="font-size:13px">${esc(why || 'Sign in to record what you check:')}</span>
      <input type="email" required placeholder="your email" style="font:inherit;font-size:13px;padding:3px 6px;border:1px solid var(--line);border-radius:5px;background:var(--panel);color:var(--ink)">
      <button style="font:inherit;font-size:13px;padding:3px 10px;border:1px solid var(--accent);border-radius:5px;background:var(--panel);color:var(--ink);cursor:pointer">Email me a sign-in link</button></form>`;
    el.querySelector('form').onsubmit = async e => {
      e.preventDefault();
      const email = el.querySelector('input').value.trim();
      const {error} = await sb.auth.signInWithOtp({email, options: {emailRedirectTo: location.href.split('#')[0]}});
      el.innerHTML = error ? `<span style="color:var(--bad)">Couldn't send the link: ${esc(error.message)}</span>`
        : `<span class="muted">Check your email for the sign-in link (${esc(email)}).</span>`;
    };
  }

  async function profileForm(el) {
    const {data} = await sb.from('profiles').select('display_name,on_leaderboard').eq('user_id', user.id).maybeSingle();
    const p = data || {display_name: '', on_leaderboard: false};
    el.innerHTML = `<span style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:13px">
      <input data-name placeholder="name for the leaderboard" value="${esc(p.display_name)}" maxlength="40" style="font:inherit;font-size:13px;padding:2px 6px;border:1px solid var(--line);border-radius:5px;background:var(--panel);color:var(--ink);width:180px">
      <label><input type="checkbox" data-lb ${p.on_leaderboard ? 'checked' : ''}> show me on the leaderboard</label>
      <span class="muted">${esc(user.email || '')}</span> <a href="#" data-out>sign out</a></span>`;
    const save = () => sb.from('profiles').upsert({user_id: user.id, display_name: el.querySelector('[data-name]').value.trim(),
                                                   on_leaderboard: el.querySelector('[data-lb]').checked});
    el.querySelector('[data-name]').onchange = save;
    el.querySelector('[data-lb]').onchange = save;
    el.querySelector('[data-out]').onclick = async e => { e.preventDefault(); await sb.auth.signOut(); };
  }

  window.BLITZ_API = {
    mode: 'site', pollMs: 60000,
    title: cfg.title || 'Help check old crosswords',
    howto: cfg.howto || '',

    async state() {
      const [pz, prog] = await Promise.all([
        sb.from('puzzles').select('xdid,pub,title,base_url,files,review_status').eq('open', true).order('xdid'),
        sb.from('puzzle_progress').select('xdid,eyes')]);
      const eyes = Object.fromEntries((prog.data || []).map(r => [r.xdid, r.eyes]));
      let mine = {}, rejected = {};
      if (user) {
        const [v, d] = await Promise.all([sb.from('verdicts').select('xdid,verdict'),
                                          sb.from('decisions').select('xdid,decision').eq('decision', 'reject')]);
        mine = Object.fromEntries((v.data || []).map(r => [r.xdid, r.verdict]));
        for (const r of d.data || []) rejected[r.xdid] = (rejected[r.xdid] || 0) + 1;
      }
      rows = Object.fromEntries((pz.data || []).map(r => [r.xdid, r]));
      return {root: cfg.name || 'blitz', now: Date.now() / 1000, puzzles: (pz.data || []).map(r => ({
        xdid: r.xdid, status: r.review_status, updated: 0, eyes: eyes[r.xdid] || 0,
        verdict: mine[r.xdid] || '', rejected: rejected[r.xdid] || 0}))};
    },

    async puzzle(x) {
      const b = base(x), files = (rows[x] && rows[x].files) || {};
      const [ocr, review, shown, decisions] = await Promise.all([
        getJSON(`${b}/ocr.json`), getJSON(`${b}/review.json`),
        files['sheets/shown.json'] ? getJSON(`${b}/sheets/shown.json`).catch(() => ({})) : Promise.resolve({}),
        decisionsOf(x)]);
      return {xdid: x, status: (rows[x] || {}).review_status || 'ready', updated: 0, ocr, review,
              shown: shown.shown || [], events: [], decisions,
              has: Object.fromEntries(['page.jpg', 'clue_page.jpg', 'grid.png', 'answers.png'].map(n => [n, !!files[n]])),
              src: Object.fromEntries(['page.jpg', 'clue_page.jpg'].map(n => [n, !!files['_src/' + n]]))};
    },

    async decide(x, p) {
      if (!user) { signInForm(document.getElementById('auth'), 'Sign in to record that:'); return null; }
      let res;
      if ('item' in p) {
        res = await sb.from('decisions').upsert({xdid: x, item: p.item, decision: p.decision === 'reject' ? 'reject' : 'accept',
                                                 note: p.note || '', user_id: user.id, at: new Date().toISOString()});
      } else if ('report' in p) {
        res = (p.text || '').trim()
          ? await sb.from('reports').upsert({xdid: x, target: p.report, text: p.text.trim(), user_id: user.id, at: new Date().toISOString()})
          : await sb.from('reports').delete().eq('xdid', x).eq('target', p.report);
      } else if ('verdict' in p) {
        res = p.verdict
          ? await sb.from('verdicts').upsert({xdid: x, verdict: p.verdict, note: p.note || '', user_id: user.id, at: new Date().toISOString()})
          : await sb.from('verdicts').delete().eq('xdid', x);
      }
      if (res && res.error) { alertBar(`Couldn't save: ${res.error.message}`); return null; }
      return decisionsOf(x);
    },

    file: (x, path) => `${base(x)}/${path}`,
    renderAuth(el) { onAuth = () => (user ? profileForm(el) : signInForm(el)); onAuth(); },
  };

  function alertBar(msg) {
    const el = document.getElementById('auth');
    if (el) el.insertAdjacentHTML('afterbegin', `<span style="color:var(--bad);margin-right:8px">${esc(msg)}</span>`);
  }

  sb.auth.getSession().then(({data}) => { user = data.session ? data.session.user : null; onAuth(); });
  sb.auth.onAuthStateChange((_e, session) => {
    const was = user && user.id;
    user = session ? session.user : null;
    onAuth();
    if ((user && user.id) !== was) window.dispatchEvent(new Event('blitz-refresh'));
  });
})();
