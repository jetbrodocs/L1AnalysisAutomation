/* ===========================================================================
   L1 Memo Reader — prototype interactions
   Vanilla JS. No framework, no build step, no CDN. Works from file://.

   Everything here is MOCKED. Nothing reaches a server. The only persistence
   is localStorage (theme + the answers you type in this session), and every
   surface that would normally hit an API renders a visible "prototype"
   state so an analyst can never believe they submitted something.

   Sections:
     1. Theme toggle
     2. Section navigation (routing + not-in-prototype state)
     3. Evidence drawer (the two-click rule, spec §5)
     4. Open-question answering, routed by kind (spec §6)
     5. Filtering (§11)
     6. Expand / collapse  (§11 never collapsed by default)
   =========================================================================== */
(function () {
  'use strict';

  var LS_THEME = 'l1proto.theme';
  var LS_ANSWERS = 'l1proto.answers';

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  /* =========================================================================
     1. THEME
     The pages already respond to prefers-color-scheme. This adds an explicit
     override stamped as data-theme on <html>, persisted in localStorage.
     ========================================================================= */
  var Theme = (function () {
    var root = document.documentElement;

    function systemTheme() {
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark' : 'light';
    }
    function current() {
      return root.getAttribute('data-theme') || systemTheme();
    }
    function apply(t, persist) {
      root.setAttribute('data-theme', t);
      if (persist) {
        try { localStorage.setItem(LS_THEME, t); } catch (e) { /* file:// or private mode */ }
      }
      $$('.theme-toggle').forEach(function (btn) {
        btn.setAttribute('aria-pressed', String(t === 'dark'));
        var label = t === 'dark' ? 'Dark' : 'Light';
        btn.textContent = label;
        btn.setAttribute('aria-label', 'Theme: ' + label + '. Switch to ' +
          (t === 'dark' ? 'light' : 'dark') + '.');
        btn.title = 'Switch to ' + (t === 'dark' ? 'light' : 'dark') + ' theme';
      });
    }

    function init() {
      var stored = null;
      try { stored = localStorage.getItem(LS_THEME); } catch (e) {}
      apply(stored === 'dark' || stored === 'light' ? stored : systemTheme(), false);

      $$('.theme-toggle').forEach(function (btn) {
        btn.addEventListener('click', function () {
          apply(current() === 'dark' ? 'light' : 'dark', true);
        });
      });
    }
    return { init: init };
  })();

  /* =========================================================================
     2. SECTION NAVIGATION
     12 sections in the rail; three exist as real files. Rather than a dead
     "#" link or a 404, an unbuilt section opens a dialog saying so — and
     names what IS built, so the reader is one click from somewhere real.
     ========================================================================= */
  var BUILT = {
    '00': 'index.html',
    '04': 'section.html',
    '11': 'open-questions.html'
  };

  var SECTION_NAMES = {
    '01': 'Recommendation', '02': 'Rationale', '03': 'Fund Facts',
    '05': 'Supporting Factors', '06': 'Fees and Terms', '07': 'Team',
    '08': 'Track Record', '09': 'Contested Findings', '10': 'Asks',
    '12': 'Sources'
  };

  var Nav = (function () {
    function numberFrom(a) {
      var n = $('.rail__num', a) || $('.section-index__num', a);
      return n ? n.textContent.trim() : null;
    }

    function markUnbuilt(a) {
      var num = numberFrom(a);
      if (!num || BUILT[num]) return;
      a.classList.add('is-unbuilt');
      a.setAttribute('href', '#');
      a.dataset.section = num;
      a.dataset.sectionName = SECTION_NAMES[num] || '';
      // A link that does not lead anywhere yet should say so to a screen
      // reader too, not just to the eye.
      a.setAttribute('aria-describedby', 'unbuilt-hint');
      a.addEventListener('click', function (ev) {
        ev.preventDefault();
        showUnbuilt(num, a.dataset.sectionName, a);
      });
    }

    function showUnbuilt(num, name, trigger) {
      Drawer.open({
        kind: 'notice',
        title: '§' + num + ' ' + name,
        eyebrow: 'not in this prototype',
        trigger: trigger,
        build: function (body) {
          var p = el('p', 'drawer__lede');
          p.innerHTML = '<strong>This section is not built in the prototype.</strong> ' +
            'The engine writes all twelve section files for every run — ' +
            '<code>' + num + '-' + (name || '').toLowerCase().replace(/ /g, '-') + '.md</code> ' +
            'exists in the artifact. Three of the twelve are rendered here, chosen because ' +
            'they carry the interactions worth demonstrating.';
          body.appendChild(p);

          var h = el('h4', 'drawer__subhead', 'Built in this prototype');
          body.appendChild(h);

          var ul = el('ul', 'drawer__links');
          [
            ['index.html', '00 · Index', 'recommendation, scorecard, veto statement, question routing'],
            ['section.html', '04 · Risk Factors', 'findings, evidence, citations, the contested split'],
            ['open-questions.html', '11 · Open Questions', '59 items across three kinds — the answering flows']
          ].forEach(function (row) {
            var li = el('li');
            var a = el('a');
            a.href = row[0];
            a.appendChild(el('strong', null, row[1]));
            a.appendChild(el('span', 'drawer__links-desc', row[2]));
            li.appendChild(a);
            ul.appendChild(li);
          });
          body.appendChild(ul);

          var note = el('p', 'drawer__foot',
            'Prototype boundary — nothing is broken. In the product every section routes.');
          body.appendChild(note);
        }
      });
    }

    function init() {
      $$('.rail__item, .section-index__item').forEach(markUnbuilt);

      // Screen-reader hint target, referenced by aria-describedby above.
      if (!$('#unbuilt-hint')) {
        var hint = el('span', 'visually-hidden', 'Not built in this prototype.');
        hint.id = 'unbuilt-hint';
        document.body.appendChild(hint);
      }

      // Other placeholder links across the pages ("What this means",
      // "Open source page", …). Rather than silently doing nothing, they
      // say they are placeholders.
      $$('a[href="#"]').forEach(function (a) {
        if (a.classList.contains('is-unbuilt')) return;
        if (a.closest('.cite')) return;
        if (a.dataset.wired) return;
        a.dataset.wired = '1';
        a.addEventListener('click', function (ev) {
          if (ev.defaultPrevented) return;
          ev.preventDefault();
          Toast.show('“' + a.textContent.trim().replace(/\s+/g, ' ') +
            '” is not wired in this prototype.');
        });
      });
    }
    return { init: init, showUnbuilt: showUnbuilt };
  })();

  /* =========================================================================
     3. EVIDENCE DRAWER — the two-click rule (spec §5)
     Click 1: a citation chip. The drawer slides over the body showing the
     cited page text with the quote highlighted, the verdict, and every other
     citation on the same page. It never navigates away, so the reader keeps
     their scroll position in the memo. Escape closes; focus returns to the
     citation that opened it.

     Click 2 would be "Open full page" — the full-screen source viewer. That
     needs the rendered page images from 00-pages/, which the prototype does
     not load, so it renders a labelled placeholder rather than a fake image.
     ========================================================================= */

  /* Extracted page text for the pages this prototype cites. Real text from
     the run's extraction artifact, trimmed to the region around each quote.
     The drawer finds the quote inside it and wraps it in a <mark>. */
  var PAGE_TEXT = {
    '13': 'NIIOF-I — PORTFOLIO SNAPSHOT\n\nFund fully committed – 6 investments across roads, ' +
      'solar and transmission. Tracking gross IRR of ~21% better than underwriting across the ' +
      'portfolio, from deals that are yet to be exited.\n\nAll figures as at 31-Mar-2026 unless ' +
      'otherwise stated.',
    '14': 'INVESTMENT PHILOSOPHY\n\nNIIOF-I targeted gross IRR of ~18-20% p.a.; well on its path ' +
      'to achieving target IRRs.\n\nCounterparties: NHAI, NTPC, MORTH, SECI. Sovereign and ' +
      'quasi-sovereign offtake across the operating portfolio.',
    '17': 'OPERATING ASSET FOCUS\n\nRobust, operating, cash generating infra projects tracking ' +
      'gross IRR of ~21%\n\n*As per market price as on 18-02-2026\n\nNo construction or ' +
      'greenfield exposure at entry.',
    '20': 'NIIOF-II — TARGET PORTFOLIO CONSTRUCTION\n\nStrategy aligned to NIIOF-I and targeting ' +
      'aggregate portfolio gross IRR of ~18-20% p.a.\n\nOperating Solar and Road   20%   InvITs ' +
      'and others – 20%   Transmission 30%   Other operating infrastructure 30%',
    '23': 'PORTFOLIO DISCIPLINE\n\nRetain strategic focus : Atleast 80% of Fund corpus to be ' +
      'deployed in operating infrastructure assets, concentrated within roads and solar where the ' +
      'team has the deepest operating history.',
    '25': 'PIPELINE\n\nAsset A — Valuation agreed with Seller. DD to commence.\n' +
      'Asset B — Valuation being discussed.\nAsset C — Term sheet stage.',
    '37': "NIIOF-II : Terms\n Category SEBI registered Category II AIF\n\n Structure Close ended\n Fund Size ~ INR 5,000 crores\n Expected IRR ~ 18-20% p.a.\n 7 years from first close\n Fund Structure Fund Term Investment / Reinvestment Period Balance Exit Period\n Initial\n Close\n 4.5 Years 2.5 Years\n\n Return Profile Coupon Distribution + Capital Appreciation\n Drawdowns 6\n Estimated Number of Fund\n 20 to 22\n Investments\n Sector Focus Road & Renewables\n Investment Manager Neo Asset Management Private Limited\n\n Particulars Description\n\n Fund Auditors EY\n\n Key Service Fund Legal Counsel Trilegal\n Tax Advisors PWC\n Providers\n Custodian ICICI Bank\n Registrar and Transfer Agent Kfintech\n*For more details refer PPM\n © Neo Asset Management. Private & Confidential. All Rights Reserved. | 37",
    '38': "Fee Structure & Drawdown Schedule\n\n Class of Management Carry without catch-up\n Contribution\n Units Fees p.a. (Hurdle Rate 10%) Drawdown\n Notice Issued\n\n A1 1-2.99 Crs 2.00% 20.0%\n\n 15 5 days\n Business grace\n A2 3-9.99 Crs 1.75% 15.0% days to period to\n contribute contribute\n\n A3 10-24.99 Crs 1.50% 12.5%\n\n Fund\n makes\n A4 25 Crs & above 1.25% 10.0%\n investment\n\n*For more details refer PPM\n © Neo Asset Management. Private & Confidential. All Rights Reserved. | 38",
    '21': "Primary Investment Strategy – ~80% of the Fund\nOperating solar and road assets\n\n Neo Infra has\n Pipeline of ~25% of\n Large Opportunity competitive edge and\n Fund already in shape\n proven track record\n ❖ 9 roads worth Rs 1900\n ❖ Team's exemplary track\n ❖ >100 operating NHAI HAM roads crore already in advanced\n record\n of Rs 25,000 crore equity value stages/ signed deals\n available for sale\n ❖ Deals of more than Rs 2800\n o Expected deployment in 3-4\n crore signed in 2 years\n ❖ Solar and renewable assets of Rs months\n 2 lakh crore available for sale\n ❖ Unmatched connect and\n ❖ Additionally, active\n network\n discussions ongoing for Rs\n 3000+ crore\n ❖ Extraordinary operating\n experience\n\n Targeting gross returns of ~20-21% from this strategy\n\n © Neo Asset Management. Private & Confidential. All Rights Reserved. | 21",
    '41': 'GOVERNANCE\n\n❖ Detailed review with IC sub-committee on performance, comparison ' +
      'against underwriting, and remedial actions where required.\n\n❖ Quarterly reporting to ' +
      'contributors.\n\n❖ Annual audited accounts.',
    '52': 'IMPORTANT DISCLOSURES\n\nAs used throughout this presentation, and unless otherwise ' +
      'indicated, all returns are presented on a “gross” basis. Gross IRRs and gross multiples of ' +
      'invested capital (i.e., the total combined value divided by the invested amount) do not ' +
      'reflect management fees, “carried interest,” taxes, transaction costs and other expenses to ' +
      'be borne by investors, which will reduce returns and in the aggregate are expected to be ' +
      'substantial.'
  };

  var VERDICT = {
    exact: {
      glyph: '✓', label: 'Verified exact', tone: 'green',
      note: 'Found character-for-character on the cited page. The highlight below marks the ' +
            'matched region in the extracted page text.'
    },
    layout: {
      glyph: '▨', label: 'Layout-normalised', tone: 'amber',
      note: 'The words are on the page; the line breaks are not reproducible. The engine ' +
            'normalised whitespace before matching, so the highlight marks the words but not ' +
            'their original arrangement.'
    },
    unverified: {
      glyph: '○', label: 'Not confirmed', tone: 'slate',
      note: 'The engine could not locate this string in the extracted text of the cited page. ' +
            'No highlight is drawn — drawing one the engine could not locate would be a ' +
            'fabrication. Read the page image yourself before relying on this quote.'
    }
  };

  var Drawer = (function () {
    var root = null, panel = null, titleEl = null, eyebrowEl = null, bodyEl = null,
        closeBtn = null, lastTrigger = null, isOpen = false;

    function build() {
      root = el('div', 'drawer');
      root.id = 'evidenceDrawer';
      root.hidden = true;

      var scrim = el('div', 'drawer__scrim');
      scrim.addEventListener('click', close);
      root.appendChild(scrim);

      panel = el('aside', 'drawer__panel');
      panel.setAttribute('role', 'dialog');
      panel.setAttribute('aria-modal', 'true');
      panel.setAttribute('aria-labelledby', 'drawerTitle');
      panel.tabIndex = -1;

      var head = el('div', 'drawer__head');
      var headText = el('div', 'drawer__head-text');
      eyebrowEl = el('p', 'drawer__eyebrow');
      titleEl = el('h2', 'drawer__title');
      titleEl.id = 'drawerTitle';
      headText.appendChild(eyebrowEl);
      headText.appendChild(titleEl);
      head.appendChild(headText);

      closeBtn = el('button', 'drawer__close');
      closeBtn.type = 'button';
      closeBtn.setAttribute('aria-label', 'Close');
      closeBtn.innerHTML = '<span aria-hidden="true">✕</span>';
      closeBtn.addEventListener('click', close);
      head.appendChild(closeBtn);
      panel.appendChild(head);

      bodyEl = el('div', 'drawer__body');
      panel.appendChild(bodyEl);

      root.appendChild(panel);
      document.body.appendChild(root);

      document.addEventListener('keydown', onKeydown, true);
    }

    function focusables() {
      return $$('a[href], button:not([disabled]), input:not([disabled]), ' +
        'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])', panel)
        .filter(function (n) { return n.offsetParent !== null || n === closeBtn; });
    }

    function onKeydown(ev) {
      if (!isOpen) return;
      if (ev.key === 'Escape') { ev.preventDefault(); close(); return; }
      if (ev.key !== 'Tab') return;

      var list = focusables();
      if (!list.length) { ev.preventDefault(); panel.focus(); return; }
      var first = list[0], last = list[list.length - 1];
      if (ev.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
        ev.preventDefault(); last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault(); first.focus();
      }
    }

    function open(opts) {
      if (!root) build();
      lastTrigger = opts.trigger || document.activeElement;

      eyebrowEl.textContent = opts.eyebrow || '';
      eyebrowEl.hidden = !opts.eyebrow;
      titleEl.textContent = opts.title || '';
      bodyEl.innerHTML = '';
      panel.className = 'drawer__panel' + (opts.kind ? ' drawer__panel--' + opts.kind : '');
      if (opts.build) opts.build(bodyEl);

      root.hidden = false;
      document.body.classList.add('has-drawer');
      isOpen = true;
      // Force a reflow so the transition runs from the closed state, then
      // open synchronously. rAF is throttled in background tabs, and a
      // drawer that stays off-screen because a frame never fired is worse
      // than one that appears without a slide.
      void root.offsetWidth;
      root.classList.add('is-open');
      panel.focus();
    }

    function close() {
      if (!isOpen) return;
      isOpen = false;
      root.classList.remove('is-open');
      document.body.classList.remove('has-drawer');
      var t = lastTrigger;
      window.setTimeout(function () {
        if (!isOpen) root.hidden = true;
      }, 200);
      // Focus returns to whatever opened the drawer. If that element is no
      // longer focusable (filtered out, removed), focus must still land
      // somewhere real — never nowhere.
      if (t && typeof t.focus === 'function' && document.contains(t) && t.offsetParent !== null) {
        t.focus();
      } else {
        var fallback = document.querySelector('main') || document.body;
        if (!fallback.hasAttribute('tabindex')) fallback.setAttribute('tabindex', '-1');
        fallback.focus();
      }
    }

    return { open: open, close: close, isOpen: function () { return isOpen; } };
  })();

  var Evidence = (function () {
    function verdictOf(cite) {
      if (cite.classList.contains('cite--exact')) return 'exact';
      if (cite.classList.contains('cite--layout')) return 'layout';
      return 'unverified';
    }

    function pageOf(cite) {
      var p = $('.cite__page', cite);
      return p ? p.textContent.trim().replace(/^p\./, '') : null;
    }

    function quoteOf(cite) {
      var q = $('.cite__quote', cite);
      if (!q) return '';
      var clone = q.cloneNode(true);
      $$('.visually-hidden', clone).forEach(function (n) { n.remove(); });
      return clone.textContent.replace(/\s+/g, ' ').trim().replace(/^"|"$/g, '');
    }

    /* Whitespace-insensitive search, so a quote that spans a line break in
       the source still matches. Returns [start, end] into the ORIGINAL
       string, or null. */
    function locate(haystack, needle) {
      var norm = function (s) { return s.replace(/[“”]/g, '"').replace(/\s+/g, ' '); };
      var map = [];
      var flat = '';
      var prevSpace = false;
      for (var i = 0; i < haystack.length; i++) {
        var ch = haystack[i];
        if (/\s/.test(ch)) {
          if (prevSpace) continue;
          prevSpace = true;
          flat += ' '; map.push(i);
        } else {
          prevSpace = false;
          flat += ch === '“' || ch === '”' ? '"' : ch;
          map.push(i);
        }
      }
      var n = norm(needle).trim();
      if (!n) return null;
      var idx = flat.toLowerCase().indexOf(n.toLowerCase());
      if (idx === -1) return null;
      return [map[idx], map[Math.min(idx + n.length - 1, map.length - 1)] + 1];
    }

    /* Every other citation on the same page, so a reader on p.37 sees all
       the findings that cite it. (Spec §5.) */
    function citationsOnPage(page, exclude) {
      return $$('.cite').filter(function (c) {
        return c !== exclude && pageOf(c) === page;
      });
    }

    function findingOf(node) {
      var f = node.closest('.finding');
      if (!f) return null;
      var title = f.id;
      var t = $('.finding__title', f);
      if (t) {
        // The collapse toggle lives inside the title; it is chrome, not text.
        var clone = t.cloneNode(true);
        $$('.finding__toggle', clone).forEach(function (n) { n.remove(); });
        title = clone.textContent.replace(/\s+/g, ' ').trim();
      }
      return { id: f.id, title: title };
    }

    function openFor(cite) {
      var page = pageOf(cite);
      var quote = quoteOf(cite);
      var v = verdictOf(cite);
      var meta = VERDICT[v];
      var owner = findingOf(cite);

      Drawer.open({
        kind: 'evidence',
        eyebrow: 'Evidence · page ' + page,
        title: owner ? owner.title : 'Cited quote',
        trigger: cite,
        build: function (body) {
          /* --- verdict badge ------------------------------------------- */
          var badge = el('p', 'drawer-verdict drawer-verdict--' + meta.tone);
          var g = el('span', 'drawer-verdict__glyph', meta.glyph);
          g.setAttribute('aria-hidden', 'true');
          badge.appendChild(g);
          badge.appendChild(el('strong', null, meta.label));
          body.appendChild(badge);

          /* --- the quote ------------------------------------------------ */
          var qb = el('blockquote', 'drawer-quote');
          qb.textContent = '“' + quote + '”';
          body.appendChild(qb);

          var note = el('p', 'drawer__note', meta.note);
          body.appendChild(note);

          /* --- the page text with the quote highlighted ----------------- */
          body.appendChild(el('h4', 'drawer__subhead', 'Extracted text of page ' + page));

          var textWrap = el('div', 'drawer-page');
          var raw = PAGE_TEXT[page];

          if (!raw) {
            textWrap.appendChild(el('p', 'drawer__foot',
              'The extracted text for page ' + page + ' is not bundled in this prototype. ' +
              'In the product the drawer renders the page image from 00-pages/ with the ' +
              'matched region highlighted.'));
          } else {
            var pre = el('pre', 'drawer-page__text');
            var span = v === 'unverified' ? null : locate(raw, quote);
            if (span) {
              pre.appendChild(document.createTextNode(raw.slice(0, span[0])));
              var mk = el('mark', 'drawer-page__hit', raw.slice(span[0], span[1]));
              pre.appendChild(mk);
              pre.appendChild(document.createTextNode(raw.slice(span[1])));
            } else {
              pre.appendChild(document.createTextNode(raw));
              if (v !== 'unverified') {
                // Honest about our own limits: the excerpt is trimmed, so a
                // real quote may sit outside it. Say so rather than imply a
                // verification failure.
                textWrap.appendChild(el('p', 'drawer__foot',
                  'The quote sits outside the excerpt bundled here, so no highlight is drawn. ' +
                  'The verdict above is the engine’s, over the full page text.'));
              }
            }
            textWrap.appendChild(pre);
          }
          body.appendChild(textWrap);

          /* --- other citations on this page ----------------------------- */
          var others = citationsOnPage(page, cite);
          if (others.length) {
            body.appendChild(el('h4', 'drawer__subhead',
              'Also cited from page ' + page + ' — ' + others.length));
            var ul = el('ul', 'drawer-others');
            others.forEach(function (o) {
              var li = el('li');
              var btn = el('button', 'drawer-others__item');
              btn.type = 'button';
              var f = findingOf(o);
              var head = el('span', 'drawer-others__finding', f ? f.title : 'Elsewhere in this memo');
              var q = el('span', 'drawer-others__quote', '“' + quoteOf(o) + '”');
              btn.appendChild(head);
              btn.appendChild(q);
              btn.addEventListener('click', function () { openFor(o); });
              li.appendChild(btn);
              ul.appendChild(li);
            });
            body.appendChild(ul);
          }

          /* --- used by --------------------------------------------------- */
          if (owner) {
            body.appendChild(el('h4', 'drawer__subhead', 'Used by'));
            var used = el('p', 'drawer-usedby');
            used.appendChild(el('code', null, owner.id));
            used.appendChild(document.createTextNode(' ' + owner.title.replace(owner.id, '').trim()));
            body.appendChild(used);
          }

          /* --- actions --------------------------------------------------- */
          var actions = el('div', 'drawer__actions');
          [
            ['Open full page', 'The full-screen source viewer needs the rendered page images from 00-pages/, which this prototype does not load.'],
            ['Next citation', null],
            ['Copy quote with citation', null],
            ['Flag this citation', 'Flagging writes to the run record. Nothing is written in the prototype.']
          ].forEach(function (row, i) {
            var b = el('button', 'btn' + (i === 0 ? ' btn--primary' : ''), row[0]);
            b.type = 'button';
            b.addEventListener('click', function () {
              if (row[0] === 'Next citation') {
                var all = $$('.cite');
                var here = all.indexOf(cite);
                if (here > -1 && all.length > 1) { openFor(all[(here + 1) % all.length]); return; }
              }
              if (row[0] === 'Copy quote with citation') {
                var payload = '“' + quote + '” — p.' + page +
                  (owner ? ', cited by ' + owner.id : '');
                if (navigator.clipboard && navigator.clipboard.writeText) {
                  navigator.clipboard.writeText(payload).then(
                    function () { Toast.show('Quote and citation copied.'); },
                    function () { Toast.show('Copy is blocked in this context. Prototype.'); }
                  );
                } else {
                  Toast.show('Clipboard is unavailable from file://. Prototype.');
                }
                return;
              }
              Toast.show(row[1] || (row[0] + ' is mocked in this prototype.'));
            });
            actions.appendChild(b);
          });
          body.appendChild(actions);

          body.appendChild(el('p', 'drawer__mock',
            'Prototype — the page image, the full-screen viewer and the flag queue are mocked. ' +
            'Nothing here is written anywhere.'));
        }
      });
    }

    function init() {
      $$('.cite').forEach(function (cite) {
        // Citations are <a href="#"> in the markup; make them real triggers
        // without changing the element (the visual language is settled).
        if (cite.tagName === 'A') {
          cite.setAttribute('href', '#evidenceDrawer');
          cite.setAttribute('role', 'button');
        } else {
          cite.tabIndex = 0;
          cite.setAttribute('role', 'button');
        }
        cite.setAttribute('aria-haspopup', 'dialog');
        cite.classList.add('cite--interactive');

        cite.addEventListener('click', function (ev) {
          ev.preventDefault();
          openFor(cite);
        });
        cite.addEventListener('keydown', function (ev) {
          if (ev.key === 'Enter' || ev.key === ' ') {
            ev.preventDefault();
            openFor(cite);
          }
        });
      });
    }

    return { init: init };
  })();

  /* =========================================================================
     4. OPEN-QUESTION ANSWERING, ROUTED BY KIND (spec §6)
     The three kinds are structurally different because the difference between
     them IS structural:
       .q--doc      → upload affordance (mock picker, filename, queued state)
       .q--analyst  → attestation form with a REQUIRED, VALIDATED source
       .q--blocked  → NO answer affordance. Not a disabled one. None.
     ========================================================================= */

  var Answers = (function () {
    var store = {};
    try { store = JSON.parse(localStorage.getItem(LS_ANSWERS) || '{}'); } catch (e) { store = {}; }

    function save() {
      try { localStorage.setItem(LS_ANSWERS, JSON.stringify(store)); } catch (e) {}
    }
    return {
      get: function (k) { return store[k]; },
      set: function (k, v) { store[k] = v; save(); Filters.refresh(); },
      clear: function (k) { delete store[k]; save(); Filters.refresh(); },
      all: function () { return store; }
    };
  })();

  /* --- Source validation (V3 / V4, tightened) -----------------------------
     Empty rejected. Under 20 characters rejected. And a stoplist of the
     phrases that look like a source but are not one. */
  var SOURCE_MIN = 20;
  var SOURCE_STOPLIST = [
    'confirmed', 'yes', 'known', 'n/a', 'na', 'as discussed', 'per management',
    'none', 'unknown', '-', '—'
  ];

  function validateSource(raw) {
    var v = (raw || '').trim();
    if (!v) {
      return 'Where did this come from? A call, an email, a document and page — anything, but ' +
        'something. Attested answers without a source are not accepted.';
    }
    var bare = v.toLowerCase().replace(/[.\s]+$/, '');
    if (SOURCE_STOPLIST.indexOf(bare) > -1) {
      return '“' + v + '” isn’t a source. If you don’t have one, this stays an open question — ' +
        'which is a valid outcome.';
    }
    if (v.length < SOURCE_MIN) {
      return 'That is ' + v.length + ' characters. A source needs at least ' + SOURCE_MIN +
        ' — enough to name who or what it was and when. “Call with Rahul Sharma (IR), 18 Jul 2026” ' +
        'or “PPM p.14, received 12 Jul”.';
    }
    return null;
  }

  function validateAnswer(raw) {
    var v = (raw || '').trim();
    if (!v) return 'Enter your answer.';
    if (v.length < 3) return 'Enter your answer.';
    return null;
  }

  var Questions = (function () {

    function keyOf(q) {
      var k = $('.q__key', q);
      return k ? k.textContent.trim() : q.id;
    }

    function panelFor(q) {
      var p = $('.q__panel', q);
      if (p) return p;
      p = el('div', 'q__panel');
      p.hidden = true;
      var aff = $('.q__affordance', q);
      if (aff) aff.parentNode.insertBefore(p, aff.nextSibling);
      else q.appendChild(p);
      return p;
    }

    function closePanel(q) {
      var p = $('.q__panel', q);
      if (p) { p.hidden = true; p.innerHTML = ''; }
      $$('.q__affordance .btn', q).forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
    }

    /* ---------- resolved-state rendering (spec §6.4) ----------------------
       Items never disappear on being answered. The record of what was once
       unknown is part of the audit story. */
    function renderResolved(q) {
      var rec = Answers.get(keyOf(q));
      var existing = $('.q__resolved', q);
      if (existing) existing.remove();
      q.classList.toggle('is-resolved', !!rec);
      if (!rec) return;

      var box = el('div', 'q__resolved q__resolved--' + rec.type);
      var head = el('p', 'q__resolved-head');
      head.appendChild(el('span', 'q__resolved-mark', rec.type === 'upload' ? '📄' : rec.type === 'na' ? '—' : '✎'));
      head.appendChild(el('strong', null,
        rec.type === 'upload' ? 'Document queued'
          : rec.type === 'na' ? 'Marked not applicable'
          : 'Analyst-attested'));
      head.appendChild(el('span', 'q__resolved-when', ' · ' + rec.at));
      box.appendChild(head);

      if (rec.type === 'upload') {
        var f = el('p', 'q__resolved-line');
        f.appendChild(el('code', null, rec.filename));
        f.appendChild(document.createTextNode(' — ' + (rec.size || 'size unknown')));
        box.appendChild(f);
      }
      if (rec.answer) {
        box.appendChild(el('p', 'q__resolved-line', rec.answer));
      }
      if (rec.source) {
        var s = el('p', 'q__resolved-line q__resolved-source');
        s.appendChild(el('span', 'q__resolved-label', 'Source '));
        s.appendChild(document.createTextNode(rec.source));
        box.appendChild(s);
      }
      if (rec.reason) {
        var r = el('p', 'q__resolved-line q__resolved-source');
        r.appendChild(el('span', 'q__resolved-label', 'Reason '));
        r.appendChild(document.createTextNode(rec.reason));
        box.appendChild(r);
      }

      box.appendChild(el('p', 'q__resolved-pending',
        'Answered — will apply on re-run. This is a prototype: nothing was sent anywhere, ' +
        'and the record lives only in this browser.'));

      var undo = el('button', 'btn btn--small', 'Undo');
      undo.type = 'button';
      undo.addEventListener('click', function () {
        Answers.clear(keyOf(q));
        renderResolved(q);
        var first = $('.q__affordance .btn', q);
        if (first) first.focus();
      });
      box.appendChild(undo);

      var aff = $('.q__affordance', q);
      if (aff) aff.parentNode.insertBefore(box, aff);
      else q.appendChild(box);
    }

    /* ---------- 6.1 document_answerable — upload ------------------------- */
    function buildUpload(q, trigger) {
      var p = panelFor(q);
      p.hidden = false;
      p.innerHTML = '';
      trigger.setAttribute('aria-expanded', 'true');

      var form = el('form', 'ansform');
      form.noValidate = true;

      var h = el('h5', 'ansform__title', 'Upload a document');
      form.appendChild(h);

      var lede = el('p', 'ansform__lede');
      var route = $('.q__route strong', q);
      lede.innerHTML = 'The typical source is the <strong>' +
        (route ? route.textContent : 'requested document') + '</strong>. ' +
        'On upload the document is classified and promoted, then this question is re-evaluated ' +
        'on the next run — it is not answered by the upload itself.';
      form.appendChild(lede);

      /* A real <input type="file"> so the picker behaves as it should, but
         the file is never read and never leaves the page. */
      var fieldId = 'file-' + Math.random().toString(36).slice(2, 8);
      var lab = el('label', 'ansform__label', 'Choose a PDF');
      lab.htmlFor = fieldId;
      form.appendChild(lab);

      var file = document.createElement('input');
      file.type = 'file';
      file.id = fieldId;
      file.accept = 'application/pdf,.pdf';
      file.className = 'ansform__file';
      form.appendChild(file);

      var chosen = el('p', 'ansform__chosen');
      chosen.hidden = true;
      form.appendChild(chosen);

      var err = el('p', 'ansform__error');
      err.setAttribute('role', 'alert');
      err.hidden = true;
      form.appendChild(err);

      var picked = null;
      file.addEventListener('change', function () {
        picked = file.files && file.files[0] ? file.files[0] : null;
        err.hidden = true;
        if (!picked) { chosen.hidden = true; return; }
        chosen.hidden = false;
        chosen.innerHTML = '';
        chosen.appendChild(el('span', 'ansform__chosen-mark', '📄'));
        chosen.appendChild(el('code', null, picked.name));
        chosen.appendChild(el('span', 'ansform__chosen-size',
          ' · ' + Math.max(1, Math.round(picked.size / 1024)) + ' KB'));
      });

      var mock = el('p', 'ansform__mock',
        'Prototype — the file is not read, not uploaded and not stored. Only its name is shown.');
      form.appendChild(mock);

      var row = el('div', 'ansform__actions');
      var submit = el('button', 'btn btn--primary', 'Queue for the next run');
      submit.type = 'submit';
      var cancel = el('button', 'btn', 'Cancel');
      cancel.type = 'button';
      cancel.addEventListener('click', function () { closePanel(q); trigger.focus(); });
      row.appendChild(submit);
      row.appendChild(cancel);
      form.appendChild(row);

      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        if (!picked) {
          err.hidden = false;
          err.textContent = 'Choose a file first. Nothing is uploaded — the prototype only reads the name.';
          file.focus();
          return;
        }
        // V12 — only PDFs can be analysed.
        var isPdf = /\.pdf$/i.test(picked.name) || picked.type === 'application/pdf';
        if (!isPdf) {
          err.hidden = false;
          err.textContent = 'Only PDFs can be analysed. This file is ' +
            (picked.type || 'of an unrecognised type') + '.';
          file.focus();
          return;
        }
        Answers.set(keyOf(q), {
          type: 'upload',
          filename: picked.name,
          size: Math.max(1, Math.round(picked.size / 1024)) + ' KB',
          at: today()
        });
        closePanel(q);
        renderResolved(q);
        Toast.show('Queued (mock) — ' + picked.name + '. Nothing was uploaded.');
      });

      p.appendChild(form);
      file.focus();
    }

    /* ---------- 6.2 analyst_answerable — attestation --------------------- */
    function buildAttest(q, trigger, opts) {
      var p = panelFor(q);
      p.hidden = false;
      p.innerHTML = '';
      trigger.setAttribute('aria-expanded', 'true');

      var form = el('form', 'ansform');
      form.noValidate = true;

      form.appendChild(el('h5', 'ansform__title',
        opts && opts.downgraded ? 'Answer this yourself' : 'Answer with a source'));

      if (opts && opts.downgraded) {
        form.appendChild(el('p', 'ansform__lede',
          'You are answering a question whose typical source is a document. Your answer is ' +
          'recorded as ATTESTED, not document-grounded — which is a different and weaker ' +
          'provenance, carried through the memo, the PDF and the version diff.'));
      }

      var uid = Math.random().toString(36).slice(2, 8);

      /* answer */
      var aLab = el('label', 'ansform__label', 'Your answer');
      aLab.htmlFor = 'ans-' + uid;
      form.appendChild(aLab);
      var ans = document.createElement('textarea');
      ans.id = 'ans-' + uid;
      ans.className = 'ansform__input';
      ans.rows = 3;
      form.appendChild(ans);
      var ansErr = el('p', 'ansform__error');
      ansErr.setAttribute('role', 'alert');
      ansErr.hidden = true;
      ansErr.id = 'ans-err-' + uid;
      form.appendChild(ansErr);

      /* source — the load-bearing field */
      var sLab = el('label', 'ansform__label ansform__label--required');
      sLab.htmlFor = 'src-' + uid;
      sLab.appendChild(document.createTextNode('Source '));
      sLab.appendChild(el('span', 'ansform__req', '*'));
      sLab.appendChild(el('span', 'ansform__hint', ' required — where did this come from?'));
      form.appendChild(sLab);

      var src = document.createElement('input');
      src.type = 'text';
      src.id = 'src-' + uid;
      src.className = 'ansform__input';
      src.placeholder = 'e.g. “Call with Rahul Sharma (IR), 18 Jul 2026” or “PPM p.14”';
      src.setAttribute('aria-describedby', 'src-err-' + uid);
      form.appendChild(src);

      var srcErr = el('p', 'ansform__error');
      srcErr.setAttribute('role', 'alert');
      srcErr.hidden = true;
      srcErr.id = 'src-err-' + uid;
      form.appendChild(srcErr);

      /* the standing warning */
      var warn = el('p', 'ansform__attest');
      warn.innerHTML = '<span aria-hidden="true">ⓘ</span> This will be recorded as ' +
        '<strong>ANALYST-ATTESTED</strong>, not document-grounded. It appears in the memo ' +
        'attributed to you, with your source and today’s date. It is not treated as evidence ' +
        'from the deck, and it is never scored.';
      form.appendChild(warn);

      form.appendChild(el('p', 'ansform__mock',
        'Prototype — “Save” writes to this browser only. No attestation is recorded anywhere.'));

      var row = el('div', 'ansform__actions');
      var save = el('button', 'btn btn--primary', 'Save attestation');
      save.type = 'submit';
      var cancel = el('button', 'btn', 'Cancel');
      cancel.type = 'button';
      cancel.addEventListener('click', function () { closePanel(q); trigger.focus(); });
      row.appendChild(save);
      row.appendChild(cancel);
      form.appendChild(row);

      function clearErr(input, node) {
        input.addEventListener('input', function () {
          node.hidden = true;
          input.removeAttribute('aria-invalid');
          input.classList.remove('is-invalid');
        });
      }
      clearErr(ans, ansErr);
      clearErr(src, srcErr);

      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        var aMsg = validateAnswer(ans.value);
        var sMsg = validateSource(src.value);

        ansErr.hidden = !aMsg;
        if (aMsg) { ansErr.textContent = aMsg; ans.setAttribute('aria-invalid', 'true'); ans.classList.add('is-invalid'); }
        srcErr.hidden = !sMsg;
        if (sMsg) { srcErr.textContent = sMsg; src.setAttribute('aria-invalid', 'true'); src.classList.add('is-invalid'); }

        if (aMsg) { ans.focus(); return; }
        if (sMsg) { src.focus(); return; }

        Answers.set(keyOf(q), {
          type: 'attest',
          answer: ans.value.trim(),
          source: src.value.trim(),
          at: today()
        });
        closePanel(q);
        renderResolved(q);
        Toast.show('Attestation saved locally (mock). Nothing was submitted.');
      });

      p.appendChild(form);
      ans.focus();
    }

    /* ---------- Not applicable (V7 — requires a reason) ------------------- */
    function buildNA(q, trigger) {
      var p = panelFor(q);
      p.hidden = false;
      p.innerHTML = '';
      trigger.setAttribute('aria-expanded', 'true');

      var form = el('form', 'ansform');
      form.noValidate = true;
      form.appendChild(el('h5', 'ansform__title', 'Not applicable'));

      var uid = Math.random().toString(36).slice(2, 8);
      var lab = el('label', 'ansform__label ansform__label--required');
      lab.htmlFor = 'na-' + uid;
      lab.appendChild(document.createTextNode('Why does this not apply? '));
      lab.appendChild(el('span', 'ansform__req', '*'));
      form.appendChild(lab);

      var input = document.createElement('textarea');
      input.id = 'na-' + uid;
      input.className = 'ansform__input';
      input.rows = 2;
      form.appendChild(input);

      var err = el('p', 'ansform__error');
      err.setAttribute('role', 'alert');
      err.hidden = true;
      form.appendChild(err);

      form.appendChild(el('p', 'ansform__mock',
        'Prototype — recorded in this browser only.'));

      var row = el('div', 'ansform__actions');
      var save = el('button', 'btn btn--primary', 'Mark not applicable');
      save.type = 'submit';
      var cancel = el('button', 'btn', 'Cancel');
      cancel.type = 'button';
      cancel.addEventListener('click', function () { closePanel(q); trigger.focus(); });
      row.appendChild(save); row.appendChild(cancel);
      form.appendChild(row);

      input.addEventListener('input', function () { err.hidden = true; input.classList.remove('is-invalid'); });

      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        if (input.value.trim().length < 3) {
          err.hidden = false;
          err.textContent = 'Why does this not apply? An item dismissed without a reason is ' +
            'indistinguishable from one nobody read.';
          input.classList.add('is-invalid');
          input.focus();
          return;
        }
        Answers.set(keyOf(q), { type: 'na', reason: input.value.trim(), at: today() });
        closePanel(q);
        renderResolved(q);
        Toast.show('Marked not applicable (mock).');
      });

      p.appendChild(form);
      input.focus();
    }

    /* ---------- 6.3 externally_blocked — NO answer affordance -------------
       Deliberately no form, no field, no disabled button. Clicking the card
       (or its route line) explains the block and names the owner. There is
       nothing here to type into, and that absence is the design. */
    function openBlocked(q, trigger) {
      var key = keyOf(q);
      var route = $('.q__route', q);
      var owner = $('.owner', q);
      var affects = $('.affects', q);
      var reason = $('.blocked-notice', q);
      var unblock = $('.unblock-list', q);

      Drawer.open({
        kind: 'blocked',
        eyebrow: 'externally blocked · no answer exists',
        title: key,
        trigger: trigger || q,
        build: function (body) {
          var lead = el('p', 'drawer-blocked__lead');
          lead.appendChild(el('span', 'drawer-blocked__glyph', '□'));
          lead.appendChild(el('strong', null,
            'This check could not be performed. Nothing you can type or upload will resolve it.'));
          body.appendChild(lead);

          body.appendChild(el('h4', 'drawer__subhead', 'Blocking reason'));
          var why = el('div', 'drawer-blocked__why');
          if (reason) {
            var ps = $$('p', reason);
            (ps.length ? ps : [reason]).forEach(function (n) {
              var t = n.textContent.replace(/\s+/g, ' ').trim();
              // The lead sentence is already the banner above; don't say it twice.
              if (/^This check could not be performed/i.test(t)) return;
              if (t) why.appendChild(el('p', null, t));
            });
          } else {
            why.appendChild(el('p', null, route ? route.textContent.replace(/\s+/g, ' ').trim() : ''));
          }
          body.appendChild(why);

          body.appendChild(el('h4', 'drawer__subhead', 'Unblock owner'));
          var ow = el('p', 'drawer-blocked__owner');
          ow.appendChild(el('code', null,
            owner ? owner.textContent.replace(/^owner:\s*/i, '').trim() : 'Unassigned'));
          ow.appendChild(document.createTextNode(
            ' — this routes to a person, never to a text field.'));
          body.appendChild(ow);

          if (affects) {
            var af = el('p', 'drawer-blocked__affects');
            af.textContent = affects.textContent.replace(/\s+/g, ' ').trim() +
              ' — reported as UNEVALUATED: neither fired nor clean.';
            body.appendChild(af);
          }

          if (unblock) {
            body.appendChild(el('h4', 'drawer__subhead', 'To unblock'));
            var ul = el('ul', 'drawer-blocked__routes');
            $$('li', unblock).forEach(function (li) {
              var clone = li.cloneNode(true);
              $$('a, button', clone).forEach(function (a) {
                var b = el('button', 'btn btn--small', a.textContent.trim());
                b.type = 'button';
                b.addEventListener('click', function () {
                  Toast.show('“' + b.textContent + '” routes to an owner in the product. Mocked here.');
                });
                a.parentNode.replaceChild(b, a);
              });
              ul.appendChild(clone);
            });
            body.appendChild(ul);
          }

          var absence = el('p', 'drawer-blocked__absence');
          absence.innerHTML = '<strong>Absence of a check is not a finding.</strong> This is not a ' +
            'finding of no adverse history — it is the absence of a search.';
          body.appendChild(absence);

          body.appendChild(el('p', 'drawer__mock',
            'There is no answer field here, and there is no disabled one either. Inviting an ' +
            'analyst to type an answer to a geo-fenced register check is a broken affordance — ' +
            'so the prototype demonstrates that it does not exist.'));
        }
      });
    }

    function today() {
      var d = new Date();
      return d.toISOString().slice(0, 10);
    }

    /* ---------- wiring ---------------------------------------------------- */
    function wireDoc(q) {
      $$('.q__affordance .btn', q).forEach(function (b) {
        var label = b.textContent.trim().toLowerCase();
        var btn = toButton(b);
        btn.setAttribute('aria-expanded', 'false');
        btn.addEventListener('click', function (ev) {
          ev.preventDefault();
          if (label.indexOf('upload') > -1) buildUpload(q, btn);
          else if (label.indexOf('myself') > -1) buildAttest(q, btn, { downgraded: true });
          else buildNA(q, btn);
        });
      });
    }

    function wireAnalyst(q) {
      $$('.q__affordance .btn', q).forEach(function (b) {
        var label = b.textContent.trim().toLowerCase();
        var btn = toButton(b);
        btn.setAttribute('aria-expanded', 'false');
        btn.addEventListener('click', function (ev) {
          ev.preventDefault();
          if (label.indexOf('source') > -1) buildAttest(q, btn);
          else buildNA(q, btn);
        });
      });
    }

    function wireBlocked(q) {
      /* No answer affordance is added. The card itself becomes the trigger
         for the explanation — the only thing there is to do here. */
      q.classList.add('q--clickable');
      q.setAttribute('tabindex', '0');
      q.setAttribute('role', 'button');
      q.setAttribute('aria-haspopup', 'dialog');
      var key = $('.q__key', q);
      if (key) {
        q.setAttribute('aria-label',
          key.textContent.trim() + ' — externally blocked. Show the blocking reason and unblock owner.');
      }

      function go(ev) {
        // Let the routing buttons inside the card act for themselves.
        if (ev.target.closest('.btn, a')) return;
        openBlocked(q, q);
      }
      q.addEventListener('click', go);
      q.addEventListener('keydown', function (ev) {
        if (ev.target !== q) return;
        if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); openBlocked(q, q); }
      });

      // The existing routing links become real buttons that name their owner.
      $$('.unblock-list .btn, .q__affordance .btn', q).forEach(function (b) {
        var btn = toButton(b);
        btn.addEventListener('click', function (ev) {
          ev.preventDefault();
          ev.stopPropagation();
          Toast.show('“' + btn.textContent.trim() + '” routes to an owner. Mocked in the prototype.');
        });
      });

      var hint = el('p', 'q__blocked-hint',
        'No answer field, by design. Open this item for the blocking reason and the unblock owner.');
      var aff = $('.q__affordance', q);
      (aff || q).insertAdjacentElement(aff ? 'beforebegin' : 'beforeend', hint);
    }

    /* Turn a placeholder <a class="btn" href="#"> into a real <button>,
       preserving classes and text. Keeps the semantics honest: these do
       things, they do not navigate. */
    function toButton(a) {
      if (a.tagName === 'BUTTON') return a;
      var b = document.createElement('button');
      b.type = 'button';
      b.className = a.className;
      b.innerHTML = a.innerHTML;
      if (a.getAttribute('style')) b.setAttribute('style', a.getAttribute('style'));
      a.parentNode.replaceChild(b, a);
      return b;
    }

    function init() {
      $$('.q').forEach(function (q) {
        if (q.classList.contains('q--doc')) wireDoc(q);
        else if (q.classList.contains('q--analyst')) wireAnalyst(q);
        else if (q.classList.contains('q--blocked')) wireBlocked(q);
        renderResolved(q);
      });
    }

    return { init: init, keyOf: keyOf };
  })();

  /* =========================================================================
     5. FILTERING (§11) — 59 items is a lot.
     Filter by kind and by resolved/unresolved, with live counts. The filter
     bar is chrome: it is display:none in print, and it can never remove §11
     itself from the document.
     ========================================================================= */
  var Filters = (function () {
    var state = { kind: 'all', status: 'all' };
    var bar = null;

    function all() { return $$('.q'); }

    function kindOf(q) {
      if (q.classList.contains('q--doc')) return 'doc';
      if (q.classList.contains('q--analyst')) return 'analyst';
      if (q.classList.contains('q--blocked')) return 'blocked';
      return 'other';
    }

    function isResolved(q) { return q.classList.contains('is-resolved'); }

    function matches(q) {
      if (state.kind !== 'all' && kindOf(q) !== state.kind) return false;
      if (state.status === 'resolved' && !isResolved(q)) return false;
      if (state.status === 'unresolved' && isResolved(q)) return false;
      return true;
    }

    function counts() {
      var c = { all: 0, doc: 0, analyst: 0, blocked: 0, resolved: 0, unresolved: 0 };
      all().forEach(function (q) {
        c.all++;
        c[kindOf(q)]++;
        if (isResolved(q)) c.resolved++; else c.unresolved++;
      });
      return c;
    }

    function apply() {
      var shown = 0;
      all().forEach(function (q) {
        var ok = matches(q);
        q.classList.toggle('is-filtered-out', !ok);
        if (ok) shown++;
      });

      // Hide a band and its stage heads when nothing in it survives; an
      // empty band head reads as a bug.
      $$('.kind-band').forEach(function (band) {
        var qs = $$('.q', band);
        var any = qs.some(function (q) { return !q.classList.contains('is-filtered-out'); });
        band.classList.toggle('is-filtered-out', qs.length > 0 && !any);
      });
      $$('.stage-head').forEach(function (h) {
        var any = false, n = h.nextElementSibling;
        while (n && !n.classList.contains('stage-head')) {
          if (n.classList.contains('q') && !n.classList.contains('is-filtered-out')) { any = true; break; }
          n = n.nextElementSibling;
        }
        h.classList.toggle('is-filtered-out', !any);
      });

      var live = $('#filterLive');
      if (live) {
        live.textContent = shown === all().length
          ? 'Showing all ' + shown + ' questions.'
          : 'Showing ' + shown + ' of ' + all().length + ' questions.';
      }
      refreshCounts();
    }

    function refreshCounts() {
      var c = counts();
      $$('[data-count]', bar).forEach(function (n) {
        n.textContent = c[n.dataset.count];
      });
      $$('[data-filter]', bar).forEach(function (b) {
        var on = (b.dataset.filterGroup === 'kind' ? state.kind : state.status) === b.dataset.filter;
        b.setAttribute('aria-pressed', String(on));
        b.classList.toggle('is-on', on);
      });
    }

    function chip(group, value, label, countKey) {
      var b = el('button', 'fchip');
      b.type = 'button';
      b.dataset.filterGroup = group;
      b.dataset.filter = value;
      b.appendChild(el('span', 'fchip__label', label));
      var n = el('span', 'fchip__count');
      n.dataset.count = countKey;
      b.appendChild(n);
      b.addEventListener('click', function () {
        state[group === 'kind' ? 'kind' : 'status'] = value;
        apply();
      });
      return b;
    }

    function init() {
      if (!$('.kind-band')) return;         // not the open-questions page
      var anchor = $('.kind-jump');
      if (!anchor) return;

      bar = el('div', 'filterbar');
      bar.setAttribute('role', 'group');
      bar.setAttribute('aria-label', 'Filter open questions');

      var g1 = el('div', 'filterbar__group');
      g1.appendChild(el('span', 'filterbar__legend', 'Kind'));
      g1.appendChild(chip('kind', 'all', 'All', 'all'));
      g1.appendChild(chip('kind', 'doc', 'Document', 'doc'));
      g1.appendChild(chip('kind', 'analyst', 'Analyst', 'analyst'));
      g1.appendChild(chip('kind', 'blocked', 'Blocked', 'blocked'));
      bar.appendChild(g1);

      var g2 = el('div', 'filterbar__group');
      g2.appendChild(el('span', 'filterbar__legend', 'Status'));
      g2.appendChild(chip('status', 'all', 'All', 'all'));
      g2.appendChild(chip('status', 'unresolved', 'Unresolved', 'unresolved'));
      g2.appendChild(chip('status', 'resolved', 'Answered', 'resolved'));
      bar.appendChild(g2);

      var live = el('p', 'filterbar__live');
      live.id = 'filterLive';
      live.setAttribute('role', 'status');
      live.setAttribute('aria-live', 'polite');
      bar.appendChild(live);

      // The counts here are over the items rendered individually on this
      // page, which is fewer than the band totals (36 / 5 / 18) because the
      // prototype summarises some in a disclosure. Saying so prevents the
      // filter counts from reading as a contradiction of the band heads.
      var note = el('p', 'filterbar__note');
      note.innerHTML = 'Counts are over the items <strong>rendered individually on this page</strong> — ' +
        'fewer than the band totals (36 · 5 · 18), because the prototype summarises some in a ' +
        'disclosure. Filtering is a reading aid only: §11 is never abridged, and every export ' +
        'carries every item.';
      bar.appendChild(note);

      anchor.parentNode.insertBefore(bar, anchor.nextSibling);
      apply();
    }

    return { init: init, refresh: function () { if (bar) apply(); } };
  })();

  /* =========================================================================
     6. EXPAND / COLLAPSE
     The disclosures are already native <details>. What is added here:
       · an expand-all / collapse-all control per section, so a reader can
         open every search record at once;
       · collapsible EVIDENCE blocks on findings — but open by default,
         because evidence hidden by default defeats the two-click rule;
       · a hard guard that §11's kind-bands can never be collapsed.
     ========================================================================= */
  var Collapse = (function () {

    function wireEvidence() {
      $$('.evidence').forEach(function (ev) {
        var head = $('.evidence__head', ev);
        if (!head) return;
        var cites = $$('.cite', ev);
        if (!cites.length) return;

        var wrap = el('div', 'evidence__list');
        cites.forEach(function (c) { wrap.appendChild(c); });
        ev.appendChild(wrap);

        var btn = el('button', 'evidence__toggle');
        btn.type = 'button';
        btn.setAttribute('aria-expanded', 'true');   // open by default — §5
        btn.setAttribute('aria-controls', wrap.id = 'ev-' + Math.random().toString(36).slice(2, 8));
        function paint() {
          var open = btn.getAttribute('aria-expanded') === 'true';
          btn.textContent = open ? 'Collapse' : 'Expand · ' + cites.length + ' quotes';
          ev.classList.toggle('is-collapsed', !open);
        }
        btn.addEventListener('click', function () {
          btn.setAttribute('aria-expanded',
            btn.getAttribute('aria-expanded') === 'true' ? 'false' : 'true');
          paint();
        });
        head.appendChild(btn);
        paint();
      });
    }

    function wireFindings() {
      $$('.finding').forEach(function (f) {
        var title = $('.finding__title', f);
        var body = $('.finding__body', f);
        if (!title || !body) return;

        var btn = el('button', 'finding__toggle');
        btn.type = 'button';
        btn.setAttribute('aria-expanded', 'true');
        btn.setAttribute('aria-label', 'Collapse this finding');
        btn.innerHTML = '<span aria-hidden="true">▾</span>';
        function paint() {
          var open = btn.getAttribute('aria-expanded') === 'true';
          f.classList.toggle('is-collapsed', !open);
          btn.setAttribute('aria-label', (open ? 'Collapse' : 'Expand') + ' this finding');
          btn.innerHTML = '<span aria-hidden="true">' + (open ? '▾' : '▸') + '</span>';
        }
        btn.addEventListener('click', function () {
          btn.setAttribute('aria-expanded',
            btn.getAttribute('aria-expanded') === 'true' ? 'false' : 'true');
          paint();
        });
        title.insertBefore(btn, title.firstChild);
      });
    }

    function wireExpandAll() {
      var groups = [];
      $$('.doc').forEach(function (main) {
        if ($$('details.disclosure', main).length >= 2) groups.push(main);
      });
      groups.forEach(function (main) {
        var host = $('.doc__lede', main) || main.firstElementChild;
        if (!host) return;
        var bar = el('div', 'expandall');
        var open = el('button', 'btn btn--small', 'Expand every search record');
        open.type = 'button';
        var shut = el('button', 'btn btn--small', 'Collapse them');
        shut.type = 'button';
        open.addEventListener('click', function () {
          $$('details.disclosure', main).forEach(function (d) { d.open = true; });
        });
        shut.addEventListener('click', function () {
          $$('details.disclosure', main).forEach(function (d) { d.open = false; });
        });
        bar.appendChild(open);
        bar.appendChild(shut);
        host.parentNode.insertBefore(bar, host.nextSibling);
      });
    }

    /* §11 must never be collapsed by default — and here, never at all.
       The rule is load-bearing: a memo that can hide what it could not
       establish presents partial analysis as complete. Nothing in the
       collapse machinery is allowed to touch a kind-band. */
    function guardSection11() {
      $$('.kind-band').forEach(function (band) {
        band.classList.add('print-required');
        band.removeAttribute('hidden');
        // If anything ever tries to collapse a band, undo it.
        new MutationObserver(function () {
          if (band.hasAttribute('hidden')) band.removeAttribute('hidden');
          if (band.classList.contains('is-collapsed')) band.classList.remove('is-collapsed');
        }).observe(band, { attributes: true, attributeFilter: ['hidden', 'class'] });
      });
      // Any disclosure inside §11 opens for print regardless (already in CSS);
      // and the band-level disclosures start open on screen too.
      $$('.kind-band > details.disclosure').forEach(function (d) { d.open = false; });
    }

    function init() {
      wireEvidence();
      wireFindings();
      wireExpandAll();
      guardSection11();
    }

    return { init: init };
  })();

  /* =========================================================================
     TOAST — the visible "this is a prototype" channel.
     Every mocked action lands here, so nothing ever appears to have been
     really submitted.
     ========================================================================= */
  var Toast = (function () {
    var host = null, timer = null;

    function ensure() {
      if (host) return;
      host = el('div', 'toast');
      host.setAttribute('role', 'status');
      host.setAttribute('aria-live', 'polite');
      document.body.appendChild(host);
    }

    function show(msg) {
      ensure();
      host.innerHTML = '';
      var tag = el('span', 'toast__tag', 'MOCK');
      host.appendChild(tag);
      host.appendChild(el('span', 'toast__msg', msg));
      host.classList.add('is-on');
      window.clearTimeout(timer);
      timer = window.setTimeout(function () { host.classList.remove('is-on'); }, 4200);
    }
    return { show: show };
  })();

  /* ========================================================================= */
  function boot() {
    Theme.init();
    Nav.init();
    Evidence.init();
    Questions.init();
    Filters.init();
    Collapse.init();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
