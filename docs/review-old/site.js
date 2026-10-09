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

  async function reactionsOf(x) {  // how many people reacted with what, and which of those are mine
    const [all, mine] = await Promise.all([
      sb.from('puzzle_reactions').select('emoji,n').eq('xdid', x),
      user ? sb.from('reactions').select('emoji').eq('xdid', x) : Promise.resolve({data: []})]);
    if (all.error) return null;
    return {counts: Object.fromEntries((all.data || []).map(r => [r.emoji, r.n])), mine: (mine.data || []).map(r => r.emoji)};
  }

  const box = 'font:inherit;font-size:13px;padding:2px 6px;border:1px solid var(--line);border-radius:5px;background:var(--panel);color:var(--ink)';

  async function ensureUser() {  // a guest identity on the first decision: nothing to fill in
    if (user) return user;
    const {data, error} = await sb.auth.signInAnonymously();
    if (error) { alertBar(`Couldn't save: ${error.message}`); return null; }
    user = data.user;
    return user;
  }

  const PROVIDERS = (cfg.providers || ['google', 'github']).map(p => [p, {google: 'Google', github: 'GitHub', discord: 'Discord', apple: 'Apple'}[p] || p]);
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

  // The providers' own marks (as their sign-in guidelines ask), 18px, in the page's text size.
  const ICONS = {
    google: `<svg viewBox="0 0 48 48" width="18" height="18" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.6-.4-3.9z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z"/></svg>`,
    github: `<svg viewBox="0 0 16 16" width="18" height="18" aria-hidden="true" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>`,
    discord: `<svg viewBox="0 0 127.14 96.36" width="20" height="18" aria-hidden="true"><path fill="#5865F2" d="M107.7 8.07A105.15 105.15 0 0 0 81.47 0a72.06 72.06 0 0 0-3.36 6.83 97.68 97.68 0 0 0-29.11 0A72.37 72.37 0 0 0 45.64 0a105.89 105.89 0 0 0-26.25 8.09C2.79 32.65-1.71 56.6.54 80.21a105.73 105.73 0 0 0 32.17 16.15 77.7 77.7 0 0 0 6.89-11.11 68.42 68.42 0 0 1-10.85-5.18c.91-.66 1.8-1.34 2.66-2a75.57 75.57 0 0 0 64.32 0c.87.71 1.76 1.39 2.66 2a68.68 68.68 0 0 1-10.87 5.19 77 77 0 0 0 6.89 11.1 105.25 105.25 0 0 0 32.19-16.14c2.64-27.38-4.51-51.11-18.9-72.15zM42.45 65.69C36.18 65.69 31 60 31 53s5-12.74 11.43-12.74S54 46 53.89 53s-5.05 12.69-11.44 12.69zm42.24 0C78.41 65.69 73.25 60 73.25 53s5-12.74 11.44-12.74S96.23 46 96.12 53s-5.04 12.69-11.43 12.69z"/></svg>`,
  };
  const GSI = !!cfg.googleClientId;  // Google's own button when its client ID is configured
  let gsiReady = null, rawNonce = '';
  function loadGsi() {
    gsiReady = gsiReady || new Promise((ok, no) => {
      const sc = document.createElement('script');
      sc.src = 'https://accounts.google.com/gsi/client'; sc.async = true;
      sc.onload = () => ok(window.google); sc.onerror = no;
      document.head.appendChild(sc);
    });
    return gsiReady;
  }
  async function hashed(raw) {
    const d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
    return [...new Uint8Array(d)].map(b => b.toString(16).padStart(2, '0')).join('');
  }
  async function renderGoogle(el) {
    const slot = el.querySelector('[data-gsi]');
    if (!slot) return;
    const g = await loadGsi().catch(() => null);
    if (!g) { slot.outerHTML = `<a href="#" data-signin="google" title="Sign in with Google">${ICONS.google}</a>`; bindSignIn(el); return; }
    rawNonce = crypto.randomUUID() + crypto.randomUUID();
    g.accounts.id.initialize({
      client_id: cfg.googleClientId, nonce: await hashed(rawNonce), use_fedcm_for_prompt: true,
      callback: async ({credential}) => {
        if (user && user.is_anonymous) {  // keep the guest's work, as for the other providers
          const {data, error} = await sb.rpc('start_guest_claim');
          if (!error && data) { try { localStorage.setItem(CLAIM, data); } catch (e) {} }
        }
        const {error} = await sb.auth.signInWithIdToken({provider: 'google', token: credential, nonce: rawNonce});
        if (error) alertBar(`Couldn't sign in: ${error.message}`);
      },
    });
    g.accounts.id.renderButton(slot, {type: 'icon', size: 'medium', shape: 'square', theme: 'outline'});
  }

  const signInLinks = () => PROVIDERS.map(([p, name]) => p === 'google' && GSI ? `<span data-gsi title="Sign in with Google"></span>` :
    `<a href="#" data-signin="${p}" title="Sign in with ${esc(name)}" aria-label="Sign in with ${esc(name)}" style="display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--ink)">${ICONS[p] || esc(name)}</a>`).join('');
  const signInLine = () => `<span style="display:inline-flex;gap:6px;align-items:center;font-size:13px" class="muted">Sign in to save your progress ${signInLinks()}</span>`;
  function bindSignIn(el) {
    el.querySelectorAll('[data-signin]').forEach(a => a.onclick = e => { e.preventDefault(); signIn(a.dataset.signin); });
    if (GSI) renderGoogle(el);
  }

  function welcome(el) {
    el.innerHTML = signInLine();
    bindSignIn(el);
  }

  async function profileForm(el) {  // a guest: the sign-in line; signed in: the leaderboard setting and Sign out
    if (user.is_anonymous) { el.innerHTML = signInLine(); bindSignIn(el); return; }
    const {data} = await sb.from('profiles').select('display_name,on_leaderboard').eq('user_id', user.id).maybeSingle();
    const meta = user.user_metadata || {};
    const p = data || {display_name: '', on_leaderboard: false};
    const fromProvider = meta.full_name || meta.name || meta.user_name || '';
    const who = p.display_name || fromProvider || user.email || 'you';
    // "Show me on the leaderboard [ ]: [name]": the name is used only if they tick the box, and
    // starts as the name we got from Google / GitHub / Discord.
    el.innerHTML = `<span style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:13px">
      ${`<label style="display:inline-flex;gap:4px;align-items:center">Show me on the leaderboard <input type="checkbox" data-lb ${p.on_leaderboard ? 'checked' : ''}></label>:
        <input data-name value="${esc(p.display_name || fromProvider)}" placeholder="your name" maxlength="40" ${p.on_leaderboard ? '' : 'disabled'}
               style="${box};width:170px" title="the name shown on the leaderboard">`}
      <span class="muted">·</span> <a href="#" data-out>Sign out</a></span>`;
    {
      const name = el.querySelector('[data-name]'), lb = el.querySelector('[data-lb]');
      const save = () => sb.from('profiles').upsert({user_id: user.id, display_name: name.value.trim(), on_leaderboard: lb.checked});
      name.onchange = save;
      lb.onchange = () => {
        name.disabled = !lb.checked;
        if (lb.checked && !name.value.trim()) name.value = fromProvider;
        save();
      };
    }
    el.querySelector('[data-out]').onclick = async e => { e.preventDefault(); await sb.auth.signOut(); };
  }


  window.BLITZ_API = {
    mode: 'site', pollMs: 60000,
    title: cfg.title || 'Help check old crosswords',
    howto: cfg.howto || '',

    async state() {
      let [pz, prog] = await Promise.all([
        sb.from('puzzles').select('xdid,pub,title,base_url,files,review_status,checkup').eq('open', true).order('xdid'),
        sb.from('puzzle_progress').select('xdid,eyes')]);
      if (pz.error) pz = await sb.from('puzzles').select('xdid,pub,title,base_url,files,review_status').eq('open', true).order('xdid');  // no checkup column yet
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
        xdid: r.xdid, status: r.review_status, updated: 0, eyes: eyes[r.xdid] || 0, grade: (r.checkup || {}).grade || '',
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
      if ('item' in p && p.decision === 'noop') {
        res = null;
      } else if ('item' in p && p.decision === 'clear') {
        res = await sb.from('decisions').delete().eq('xdid', x).eq('item', p.item);
      } else if ('item' in p) {
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

    // Emoji reactions to a puzzle (schema-3-reactions.sql). null when that table isn't set up: the page then hides them.
    reactions: {
      get: reactionsOf,
      async toggle(x, emoji) {
        if (!(await ensureUser())) return null;
        const cur = await reactionsOf(x);
        if (!cur) return null;
        const res = cur.mine.includes(emoji)
          ? await sb.from('reactions').delete().eq('xdid', x).eq('emoji', emoji)
          : await sb.from('reactions').upsert({xdid: x, emoji, user_id: user.id, at: new Date().toISOString()});
        if (res && res.error) { alertBar(`Couldn't save: ${res.error.message}`); return null; }
        return reactionsOf(x);
      },
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
