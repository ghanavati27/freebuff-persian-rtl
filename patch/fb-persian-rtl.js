/* ============================================================================
   Freebuff Desktop - Persian / RTL support patch  (runtime half)
   ----------------------------------------------------------------------------
   Local patch. NOT part of the shipped bundle. Re-applied after app updates.

   Why a script and not CSS: CSS cannot ask "is this element's content RTL?", so
   it can never move a checkbox to the right for Persian while leaving an English
   row untouched. The script decides an element's direction and sets it as an
   attribute, which fixes the text order, the alignment AND the flex-row
   direction (so [icon][text] rows mirror correctly).

   WHY NOT dir="auto": `dir="auto"` resolves direction from the element's FIRST
   STRONG CHARACTER (HTML spec). A Persian paragraph that happens to begin with a
   URL, a file path or a variable name therefore resolved to LTR - the whole
   block left-aligned and every line's bidi order computed against the wrong base
   direction. Measured on the real markup: a paragraph of
   "http://127.0.0.1:3000 با توضیح در همان فایل ..." laid out with its ink at the
   box's LEFT edge under `auto`, and at the RIGHT edge under this rule.

   So direction is decided from the DOMINANT SCRIPT instead: count the Arabic-
   block letters and the Latin letters in the element's text and take the
   majority. Ties go to Persian (this is a Persian-language patch, and a tie
   means the text is genuinely mixed). An element with no letters at all - only
   digits, punctuation or symbols - keeps `dir="auto"`, exactly what it had
   before.

   Guarantee for LTR users: Latin-dominant content gets `dir="ltr"`, which is
   precisely the shipped layout - the same value `dir="auto"` resolved to for it.
   No attribute value, alignment or row order changes. Verified by a pixel diff
   of the control vs patched render of a Latin-only page.

   STREAMING: replies arrive token by token, so a paragraph can start Latin-
   dominant (a URL) and become Persian-dominant a moment later. Direction is
   therefore recomputed on text changes too, not only on insertion - debounced,
   so a stream does not turn into a re-layout per token.

   The companion stylesheet only adds the Persian font (scoped to Arabic-script
   code points) plus a couple of rules keyed on :dir(rtl), so nothing it does
   can reach an LTR element.

   This file has a second, unrelated job: auto-continuing the sponsored break
   (see the block at the end of the IIFE). That one is not RTL-gated either, and
   is documented as an exception in AGENTS.md section 11.
   ========================================================================== */
(function () {
  'use strict';

  /* Text-bearing elements of the app (class names read out of the shipped
     bundle). Rows are listed as the row, not the text node inside them, so the
     whole row mirrors. Code/terminal/editors are deliberately absent. */
  var SELECTOR = [
    /* chat transcript - model output */
    '.prose p', '.prose li', '.prose dt', '.prose dd',
    '.prose figcaption', '.prose h1', '.prose h2', '.prose h3', '.prose h4',
    '.prose h5', '.prose h6',
    /* Lists and blockquotes are deliberately NOT marked here: a dir="auto"
       element whose text lives entirely inside other dir="auto" descendants is
       skipped when its own ancestor's direction is resolved, so marking them
       would leave the list LTR and strand the marker. Their RTL geometry is set
       with :has() in the stylesheet instead. */
    /* Tables are marked as a whole, not per cell: a cell holding only a number
       or a Latin identifier has no strong character of its own and would flip
       back to LTR, leaving one column aligned differently from its neighbours. */
    '.prose table',
    '.run-answer',
    /* the user's own message */
    '.user-message-text',
    /* composer and every other field the user types into */
    '.composer-input', '.composer textarea', '.question-free', '.qedit',
    '.plan-feedback-input', '.thread-detail-steer-input',
    '.profile-survey-textarea', '.search-modal-input',
    /* agent question dock (question + answers)
       Mark the whole question card, not the rows: a per-row rule lets one
       Latin-first option stay LTR inside a Persian question, which then also
       leaves its Persian description left-aligned. */
    '.question', '.question-plan', '.plan-action',
    /* Freebuff 0.0.174: the "What went wrong?" verdict note is a user-typed
       textarea, so it needs the same dir="auto" treatment as the composer. */
    '.msg-verdict-note',
    /* Freebuff 0.0.174: sponsored intermission headline/subhead are the only
       new surface whose text is served from outside the app bundle. */
    '.intermission-headline', '.intermission-subhead',
    /* agent to-do dock.
       Mark the LIST, not each row: a list is one unit, so an item whose text
       starts with a Latin word would otherwise flip back to LTR and leave its
       checkbox on the left while its Persian neighbours have it on the right. */
    '.todo-dock-list',
    /* queued prompts */
    '.qbody', '.qprompt', '.qtitle', '.qnote', '.qitem',
    /* model reasoning and tool output */
    '.reasoning-text', '.reasoning-preview', '.tool-plan', '.tool-row-details',
    '.run-step-body', '.rpc-output', '.terminal-context-output',
    '.diff-comment-text', '.change-diff-note', '.file-view-note', '.tool-edit-note',
    /* generated titles and list rows */
    '.sidebar-thread-title', '.threads-row-title-text', '.threadbar-title',
    '.tab-title', '.thread-detail-title', '.search-result-text',
    '.search-result-title', '.message-search-match',
    /* other surfaces that carry generated or user text */
    '.intermission-text', '.fb-skeleton-answer', '.suggested-prompt-main',
    '.notice-body', '.crash-message', '.comment-chip-text',
    '.file-markdown-content', '.artifacts-message', '.artifact-resource-label',
    '.artifact-table-label', '.proposal-body', '.proposal-title',
    '.proposal-offer-text', '.proposal-step-text', '.onboarding-prompt-question',
    '.profile-survey-question', '.profile-survey-outcome-text',
    '.prompt-rail-preview', '.domain-explanation', '.mcp-tool-description',
    '.export-thread-body', '.edit-banner-text', '.agent-prompt', '.agent-body',
    '.composer-attachment-menu', '.composer-attachment-options',
    '.preview-context-text'
  ].join(',');

  /* ---------------------------------------------------------------------------
     Direction from the dominant script.

     Letters only. Digits, punctuation, spaces and the zero-width joiner are all
     script-neutral and must not vote - otherwise a paragraph of Persian prose
     carrying a long URL could be outvoted by the URL's own characters.
     --------------------------------------------------------------------------- */
  function isArabicLetter(c) {
    return (c >= 0x0600 && c <= 0x06ff) ||   /* Arabic                */
           (c >= 0x0750 && c <= 0x077f) ||   /* Arabic Supplement     */
           (c >= 0x08a0 && c <= 0x08ff) ||   /* Arabic Extended-A     */
           (c >= 0xfb50 && c <= 0xfdff) ||   /* Arabic Presentation A */
           (c >= 0xfe70 && c <= 0xfeff);     /* Arabic Presentation B */
  }

  function isLatinLetter(c) {
    return (c >= 0x41 && c <= 0x5a) ||       /* A-Z                    */
           (c >= 0x61 && c <= 0x7a) ||       /* a-z                    */
           (c >= 0x00c0 && c <= 0x024f);     /* Latin-1 + Extended A/B */
  }

  /* 'rtl', 'ltr', or null when the text holds no letters at all. */
  function dominantDir(text) {
    if (!text) return null;
    var arabic = 0, latin = 0;
    for (var i = 0; i < text.length; i++) {
      var c = text.charCodeAt(i);
      if (isArabicLetter(c)) arabic++;
      else if (isLatinLetter(c)) latin++;
    }
    if (!arabic && !latin) return null;
    return arabic >= latin ? 'rtl' : 'ltr';   /* ties go to Persian */
  }

  /* Elements this script has marked, so a changed text node can be traced back
     to the element whose direction has to be recomputed. A WeakSet, so nothing
     is retained. */
  var marked = new WeakSet();

  function mark(el) {
    if (!el || el.nodeType !== 1) return;
    var want = dominantDir(el.textContent) || 'auto';
    if (el.getAttribute('dir') !== want) el.setAttribute('dir', want);
    marked.add(el);
  }

  function apply(root) {
    if (!root || root.nodeType !== 1) return;
    try {
      if (root.matches(SELECTOR)) mark(root);
      var found = root.querySelectorAll(SELECTOR);
      for (var i = 0; i < found.length; i++) mark(found[i]);
    } catch (err) {
      /* A detached node or an unsupported selector must never break the app. */
    }
  }

  /* ---------------------------------------------------------------------------
     Streaming: recompute when text changes.

     A reply arrives token by token, and React replaces the text node rather than
     mutating it, so BOTH cases have to be handled - a childList record whose node
     is a Text node is not an element, and `apply()` would skip it, leaving the
     direction stale.

     Recomputing is debounced: without it a fast stream re-lays out the paragraph
     on every token. A paragraph is allowed to flip ltr -> rtl once enough Persian
     has arrived - that is the point of the change - and the debounce keeps it to
     a single flip instead of a flicker.
     --------------------------------------------------------------------------- */
  var DIR_DEBOUNCE_MS = 120;
  var dirty = [];
  var dirtyTimer = null;

  function nearestMarked(node) {
    var el = node;
    if (el && el.nodeType !== 1) el = el.parentElement;
    while (el) {
      if (marked.has(el)) return el;
      if (el.matches && el.matches(SELECTOR)) return el;
      el = el.parentElement;
    }
    return null;
  }

  function scheduleMark(el) {
    if (dirty.indexOf(el) === -1) dirty.push(el);
    if (dirtyTimer !== null) return;
    dirtyTimer = setTimeout(function () {
      dirtyTimer = null;
      var list = dirty;
      dirty = [];
      for (var i = 0; i < list.length; i++) {
        if (list[i].isConnected) mark(list[i]);
      }
    }, DIR_DEBOUNCE_MS);
  }

  function start() {
    new MutationObserver(function (records) {
      for (var r = 0; r < records.length; r++) {
        var rec = records[r];

        if (rec.type === 'characterData') {
          var host = nearestMarked(rec.target.parentNode);
          if (host) scheduleMark(host);
          continue;
        }

        var added = rec.addedNodes;
        for (var n = 0; n < added.length; n++) {
          var node = added[n];
          if (node.nodeType === 1) {
            apply(node);
          } else if (node.nodeType === 3) {
            var owner = nearestMarked(node.parentNode);
            if (owner) scheduleMark(owner);
          }
        }
      }
      watchSponsoredBreak();
    }).observe(document.documentElement, {
      childList: true, subtree: true, characterData: true
    });

    apply(document.documentElement);
    watchSponsoredBreak();
  }

  /* ---------------------------------------------------------------------------
     Sponsored break: auto-continue.  (NOT RTL-gated - see AGENTS.md 11.2.)

     `.sponsor-intermission` is a BLOCKING modal (role="dialog"
     aria-modal="true", aria-label="Sponsored break") and both of its exits are
     unavailable while its countdown runs: "Continue working"
     (.intermission-continue) is `disabled`, and "Close sponsor break"
     (.spotlight-close) is not rendered at all. So it cannot be hidden - the app
     would sit waiting on a click that can never happen. It is deliberately NOT
     in the stylesheet's hide list for exactly that reason.

     Instead, click "Continue working" the moment it becomes enabled. That is the
     same thing the user does (the same `nk("continue")` event), it leaves the
     break visible for its countdown instead of blanking the area, and it cannot
     strand the app.

     This is NOT an ad impression: the impression/click pixel lives in the ad's
     own click handler, not on render, so dismissing the break this way fires
     nothing extra.

     The countdown's length is not knowable from the bundle, so poll rather than
     guess a timeout - and only while a break is actually on screen, so the
     steady-state cost is zero.
     --------------------------------------------------------------------------- */
  var BREAK_POLL_MS = 500;
  var breakTimer = null;
  var continued = new WeakSet();

  function tickSponsoredBreak() {
    var dlg = document.querySelector('.sponsor-intermission');
    if (!dlg) {
      clearInterval(breakTimer);
      breakTimer = null;
      return;
    }
    if (continued.has(dlg)) return;               /* already clicked this one */
    var btn = dlg.querySelector('.intermission-continue');
    if (!btn) return;
    if (btn.disabled || btn.getAttribute('aria-disabled') === 'true') return;
    continued.add(dlg);
    try {
      btn.click();
    } catch (err) {
      /* A click must never be able to break the app. */
    }
  }

  function watchSponsoredBreak() {
    if (!document.querySelector('.sponsor-intermission')) {
      if (breakTimer !== null) {
        clearInterval(breakTimer);
        breakTimer = null;
      }
      return;
    }
    if (breakTimer !== null) return;
    breakTimer = setInterval(tickSponsoredBreak, BREAK_POLL_MS);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
