/* ============================================================================
   Freebuff Desktop - Persian / RTL support patch  (runtime half)
   ----------------------------------------------------------------------------
   Local patch. NOT part of the shipped bundle. Re-applied after app updates.

   Why this exists: CSS cannot ask "is this element's content RTL?", so it can
   never move a checkbox to the right for Persian while leaving an English row
   untouched. `dir="auto"` can: the element derives its own direction from its
   first strong character, which fixes the text order, the alignment AND the
   flex-row direction (so [icon][text] rows mirror correctly).

   Guarantee for LTR users: `dir="auto"` on Latin content resolves to `ltr`,
   which is exactly the shipped layout - no attribute value, no alignment and
   no row order changes. Verified by a pixel diff of the control vs patched
   render of a Latin-only page.

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

  function mark(el) {
    if (el.getAttribute('dir') !== 'auto') el.setAttribute('dir', 'auto');
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

  function start() {
    new MutationObserver(function (records) {
      for (var r = 0; r < records.length; r++) {
        var added = records[r].addedNodes;
        for (var n = 0; n < added.length; n++) apply(added[n]);
      }
      watchSponsoredBreak();
    }).observe(document.documentElement, { childList: true, subtree: true });

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
