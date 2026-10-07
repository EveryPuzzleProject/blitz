// The public review site's data adapter: the review page (review.html) asks BLITZ_API for the
// puzzle list, a puzzle, and to save a decision; here those come from Supabase (who checked what)
// and from the packet files in storage (R2). Settings are in config.js (window.BLITZ_SITE).
//
// No sign-up: a helper's first decision signs them in as a guest (Supabase anonymous sign-in, kept
// in their browser), so their work hangs together and counts once. Anyone can also sign in with
// Google or GitHub (new or returning, on any device); a guest's work moves to the account they sign
// in to (a claim ticket from schema-2-sign-in.sql, kept in this browser across the sign-in).
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

  const box = 'font:inherit;font-size:13px;padding:2px 6px;border:1px solid var(--line);border-radius:5px;background:var(--panel);color:var(--ink)';

  async function ensureUser() {  // a guest identity on the first decision: nothing to fill in
    if (user) return user;
    const {data, error} = await sb.auth.signInAnonymously();
    if (error) { alertBar(`Couldn't save: ${error.message}`); return null; }
    user = data.user;
    return user;
  }

  const PROVIDERS = (cfg.providers || ['google', 'github']).map(p => [p, {google: 'Google', github: 'GitHub'}[p] || p]);
  const CLAIM = 'blitz-guest-claim';

  async function signIn(provider) {
    if (user && user.is_anonymous) {  // keep the guest's work: a ticket to hand in after signing in
      const {data, error} = await sb.rpc('start_guest_claim');
      if (!error && data) { try { localStorage.setItem(CLAIM, data); } catch (e) {} }
    }
    const {error} = await sb.auth.signInWithOAuth({provider, options: {redirectTo: location.href.split('#')[0]}});
    if (error) alertBar(`Couldn't sign in: ${error.message}`);
  }

  async function finishClaim() {  // back from signing in: the guest's work moves to this account
    let t = null;
    try { t = localStorage.getItem(CLAIM); } catch (e) {}
    if (!t || !user || user.is_anonymous) return;
    try { localStorage.removeItem(CLAIM); } catch (e) {}
    const {error} = await sb.rpc('finish_guest_claim', {t});
    if (error) alertBar(`Couldn't move your guest work: ${error.message}`);
    window.dispatchEvent(new Event('blitz-refresh'));
  }

  const signInLinks = () => PROVIDERS.map(([p, name]) => `<a href="#" data-signin="${p}">${esc(name)}</a>`).join(' · ');
  function bindSignIn(el) {
    el.querySelectorAll('[data-signin]').forEach(a => a.onclick = e => { e.preventDefault(); signIn(a.dataset.signin); });
  }

  function welcome(el) {
    el.innerHTML = `<span class="muted" style="font-size:13px">No sign-up needed: just start checking.
      Or sign in with ${signInLinks()}</span>`;
    bindSignIn(el);
  }

  async function profileForm(el) {
    const {data} = await sb.from('profiles').select('display_name,on_leaderboard').eq('user_id', user.id).maybeSingle();
    const meta = user.user_metadata || {};
    const p = data || {display_name: '', on_leaderboard: false};
    const guest = user.is_anonymous;
    const who = meta.full_name || meta.name || meta.user_name || user.email || '';
    el.innerHTML = `<span style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:13px">
      <input data-name placeholder="${esc(guest ? 'your name (optional)' : who || 'your name')}" value="${esc(p.display_name)}" maxlength="40" style="${box};width:170px" title="the name shown on the leaderboard">
      <label><input type="checkbox" data-lb ${p.on_leaderboard ? 'checked' : ''}> on the leaderboard</label>
      ${guest ? `<span class="muted" title="Your progress is saved in this browser. Sign in to keep it on any device.">keep my progress: ${signInLinks()}</span>`
              : `<span class="muted">${esc(who)}</span> <a href="#" data-out>sign out</a>`}</span>`;
    const save = () => sb.from('profiles').upsert({user_id: user.id, display_name: el.querySelector('[data-name]').value.trim(),
                                                   on_leaderboard: el.querySelector('[data-lb]').checked});
    el.querySelector('[data-name]').onchange = save;
    el.querySelector('[data-lb]').onchange = save;
    if (el.querySelector('[data-out]')) el.querySelector('[data-out]').onclick = async e => { e.preventDefault(); await sb.auth.signOut(); };
    bindSignIn(el);
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
      if (!(await ensureUser())) return null;
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
    renderAuth(el) { onAuth = () => (user ? profileForm(el) : welcome(el)); onAuth(); },
  };

  function alertBar(msg) {
    const el = document.getElementById('auth');
    if (el) el.insertAdjacentHTML('afterbegin', `<span style="color:var(--bad);margin-right:8px">${esc(msg)}</span>`);
  }

  sb.auth.getSession().then(({data}) => { user = data.session ? data.session.user : null; onAuth(); finishClaim(); });
  sb.auth.onAuthStateChange((_e, session) => {
    const was = user && user.id;
    user = session ? session.user : null;
    onAuth();
    finishClaim();
    if ((user && user.id) !== was) window.dispatchEvent(new Event('blitz-refresh'));
  });
})();
