/**
 * vertex.js  —  single-file library combining:
 *
 *   1. VQuery    — DOM layer (hn.js-inspired, jQuery surface-compatible)
 *   2. template  — full Mustache template engine + component loader (Vertex.template)
 *   3. Router    — Backbone-style hash router (class-based + singleton)
 *   4. Glue      — unified Vertex namespace
 *
 * This build deliberately has no React-style component layer (no virtual
 * DOM, no fiber reconciler, no hooks) — rendering is Mustache templates
 * only, Ractive.load-style: fetch a template, bind data, mount it.
 *
 * jQuery compatibility: if jQuery / $ already exist on the page they are
 * left completely untouched.  Use  Vertex.$v()  or  V$()  for the Vertex
 * DOM wrapper in that scenario.
 *
 * UMD-wrapped so it works as a plain script tag, CommonJS module, or AMD.
 */
(function (global, factory) {
  'use strict';
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory(global);
  } else if (typeof define === 'function' && define.amd) {
    define([], function () { return factory(global); });
  } else {
    factory(global);
  }
}(typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : this),
function (global) {
  'use strict';

  /* ── requestIdleCallback polyfill ──────────────────────────────────────── */
  var ric = (global.requestIdleCallback
    ? global.requestIdleCallback.bind(global)
    : function (cb) {
        var start = Date.now();
        return setTimeout(function () {
          cb({
            timeRemaining: function () { return Math.max(0, 50 - (Date.now() - start)); },
            didTimeout: false
          });
        }, 1);
      }
  );

  /* ═══════════════════════════════════════════════════════════════════════════
     §1  DOM LAYER  —  VQuery
         Covers: on/off, css, attr, val, ajax + chainable traversal helpers.
         jQuery compatible: global $ is only set if $ and jQuery are absent.
  ═══════════════════════════════════════════════════════════════════════════ */

  function VQuery(selector, context) {
    if (!(this instanceof VQuery)) return new VQuery(selector, context);
    this.elements = [];

    if (!selector) { this.length = 0; return; }

    /* document-ready shorthand: $(fn) */
    if (typeof selector === 'function') {
      if (typeof document !== 'undefined' && document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', selector);
      } else {
        selector();
      }
      this.length = 0;
      return;
    }

    if (selector instanceof VQuery) {
      this.elements = selector.elements.slice();
    } else if (Array.isArray(selector)) {
      this.elements = selector.filter(Boolean);
    } else if (selector && (selector.nodeType ||
               selector === global ||
               (typeof document !== 'undefined' && selector === document))) {
      this.elements = [selector];
    } else if (typeof selector === 'string') {
      if (/^\s*</.test(selector)) {
        /* HTML creation: $('<div class="foo">bar</div>') */
        var tmp = document.createElement('div');
        tmp.innerHTML = selector.trim();
        this.elements = Array.from(tmp.childNodes);
      } else {
        var ctx = context
          ? (typeof context === 'string' ? document.querySelector(context) : context)
          : document;
        try { this.elements = Array.from(ctx.querySelectorAll(selector)); }
        catch (_) { this.elements = []; }
      }
    }

    this.length = this.elements.length;
    for (var i = 0; i < this.elements.length; i++) this[i] = this.elements[i];
  }

  VQuery.prototype = {
    constructor: VQuery,

    /* ── iteration ───────────────────────────────────────────────────────── */

    each: function (fn) {
      this.elements.forEach(function (el, i) { fn.call(el, i, el); });
      return this;
    },

    /* ── events ──────────────────────────────────────────────────────────── */

    on: function (events, selector, fn) {
      if (typeof selector === 'function') { fn = selector; selector = null; }
      var evList = events.split(' ');
      this.elements.forEach(function (el) {
        el._vq = el._vq || [];
        evList.forEach(function (ev) {
          if (!ev) return;
          var handler = selector
            ? function (e) {
                /* event delegation — walk up from target */
                var node = e.target;
                while (node && node !== el) {
                  if (node.matches && node.matches(selector)) { fn.call(node, e); break; }
                  node = node.parentElement;
                }
              }
            : function (e) { fn.call(el, e); };
          el._vq.push({ ev: ev, handler: handler, orig: fn });
          el.addEventListener(ev, handler);
        });
      });
      return this;
    },

    off: function (events, fn) {
      var evList = events ? events.split(' ') : null;
      this.elements.forEach(function (el) {
        if (!el._vq) return;
        el._vq = el._vq.filter(function (h) {
          var matchEv = !evList || evList.indexOf(h.ev) > -1;
          var matchFn = !fn   || h.orig === fn;
          if (matchEv && matchFn) { el.removeEventListener(h.ev, h.handler); return false; }
          return true;
        });
      });
      return this;
    },

    trigger: function (event, detail) {
      this.elements.forEach(function (el) {
        el.dispatchEvent(new CustomEvent(event, { bubbles: true, cancelable: true, detail: detail }));
      });
      return this;
    },

    /* ── attributes & properties ─────────────────────────────────────────── */

    attr: function (name, val) {
      if (val === undefined) return this.elements[0] ? this.elements[0].getAttribute(name) : null;
      this.elements.forEach(function (el) { el.setAttribute(name, val); });
      return this;
    },

    removeAttr: function (name) {
      this.elements.forEach(function (el) { el.removeAttribute(name); });
      return this;
    },

    prop: function (name, val) {
      if (val === undefined) return this.elements[0] ? this.elements[0][name] : undefined;
      this.elements.forEach(function (el) { el[name] = val; });
      return this;
    },

    val: function (v) {
      if (v === undefined) return this.elements[0] ? this.elements[0].value : '';
      this.elements.forEach(function (el) { el.value = v; });
      return this;
    },

    data: function (key, val) {
      if (val === undefined) return this.elements[0] ? this.elements[0].dataset[key] : null;
      this.elements.forEach(function (el) { el.dataset[key] = val; });
      return this;
    },

    /* ── styles ──────────────────────────────────────────────────────────── */

    css: function (prop, val) {
      if (typeof prop === 'object') {
        this.elements.forEach(function (el) { Object.assign(el.style, prop); });
        return this;
      }
      if (val === undefined) {
        return this.elements[0]
          ? getComputedStyle(this.elements[0])[prop]
          : '';
      }
      this.elements.forEach(function (el) { el.style[prop] = val; });
      return this;
    },

    /* ── classes ─────────────────────────────────────────────────────────── */

    addClass: function (cls) {
      cls.split(' ').forEach(function (c) {
        if (!c) return;
        this.elements.forEach(function (el) { el.classList.add(c); });
      }, this);
      return this;
    },

    removeClass: function (cls) {
      cls.split(' ').forEach(function (c) {
        if (!c) return;
        this.elements.forEach(function (el) { el.classList.remove(c); });
      }, this);
      return this;
    },

    toggleClass: function (cls, state) {
      this.elements.forEach(function (el) {
        typeof state === 'boolean'
          ? el.classList.toggle(cls, state)
          : el.classList.toggle(cls);
      });
      return this;
    },

    hasClass: function (cls) {
      return this.elements.some(function (el) { return el.classList.contains(cls); });
    },

    /* ── content ─────────────────────────────────────────────────────────── */

    html: function (content) {
      if (content === undefined) return this.elements[0] ? this.elements[0].innerHTML : '';
      this.elements.forEach(function (el) { el.innerHTML = content; });
      return this;
    },

    text: function (content) {
      if (content === undefined) return this.elements[0] ? this.elements[0].textContent : '';
      this.elements.forEach(function (el) { el.textContent = content; });
      return this;
    },

    append: function (content) {
      this.elements.forEach(function (el) {
        if (typeof content === 'string') {
          el.insertAdjacentHTML('beforeend', content);
        } else if (content instanceof VQuery) {
          content.elements.forEach(function (c) { el.appendChild(c.cloneNode(true)); });
        } else if (content && content.nodeType) {
          el.appendChild(content);
        }
      });
      return this;
    },

    prepend: function (content) {
      this.elements.forEach(function (el) {
        if (typeof content === 'string') {
          el.insertAdjacentHTML('afterbegin', content);
        } else if (content instanceof VQuery) {
          content.elements.forEach(function (c) { el.insertBefore(c.cloneNode(true), el.firstChild); });
        } else if (content && content.nodeType) {
          el.insertBefore(content, el.firstChild);
        }
      });
      return this;
    },

    after: function (content) {
      this.elements.forEach(function (el) {
        if (typeof content === 'string') el.insertAdjacentHTML('afterend', content);
        else if (content && el.parentNode) el.parentNode.insertBefore(content, el.nextSibling);
      });
      return this;
    },

    before: function (content) {
      this.elements.forEach(function (el) {
        if (typeof content === 'string') el.insertAdjacentHTML('beforebegin', content);
        else if (content && el.parentNode) el.parentNode.insertBefore(content, el);
      });
      return this;
    },

    remove: function () {
      this.elements.forEach(function (el) { if (el.parentNode) el.parentNode.removeChild(el); });
      return this;
    },

    empty: function () {
      this.elements.forEach(function (el) { el.innerHTML = ''; });
      return this;
    },

    clone: function (deep) {
      return new VQuery(this.elements.map(function (el) {
        return el.cloneNode(deep !== false);
      }));
    },

    wrap: function (html) {
      this.elements.forEach(function (el) {
        var wrapper = document.createElement('div');
        wrapper.innerHTML = html;
        var w = wrapper.firstChild;
        el.parentNode.insertBefore(w, el);
        w.appendChild(el);
      });
      return this;
    },

    /* ── traversal ───────────────────────────────────────────────────────── */

    find: function (sel) {
      var found = [];
      this.elements.forEach(function (el) {
        found = found.concat(Array.from(el.querySelectorAll(sel)));
      });
      return new VQuery(found);
    },

    parent: function (sel) {
      var parents = this.elements.map(function (el) { return el.parentNode; }).filter(Boolean);
      if (sel) parents = parents.filter(function (p) { return p.matches && p.matches(sel); });
      return new VQuery(parents);
    },

    parents: function (sel) {
      var result = [];
      this.elements.forEach(function (el) {
        var n = el.parentElement;
        while (n) {
          if (!sel || (n.matches && n.matches(sel))) result.push(n);
          n = n.parentElement;
        }
      });
      return new VQuery(result);
    },

    closest: function (sel) {
      var result = [];
      this.elements.forEach(function (el) {
        var n = el;
        while (n) {
          if (n.matches && n.matches(sel)) { result.push(n); break; }
          n = n.parentElement;
        }
      });
      return new VQuery(result);
    },

    children: function (sel) {
      var found = [];
      this.elements.forEach(function (el) {
        var kids = Array.from(el.children);
        if (sel) kids = kids.filter(function (k) { return k.matches(sel); });
        found = found.concat(kids);
      });
      return new VQuery(found);
    },

    siblings: function (sel) {
      var result = [];
      this.elements.forEach(function (el) {
        if (!el.parentNode) return;
        var sibs = Array.from(el.parentNode.children).filter(function (s) { return s !== el; });
        if (sel) sibs = sibs.filter(function (s) { return s.matches(sel); });
        result = result.concat(sibs);
      });
      return new VQuery(result);
    },

    next: function (sel) {
      var res = this.elements.map(function (el) { return el.nextElementSibling; }).filter(Boolean);
      if (sel) res = res.filter(function (el) { return el.matches(sel); });
      return new VQuery(res);
    },

    prev: function (sel) {
      var res = this.elements.map(function (el) { return el.previousElementSibling; }).filter(Boolean);
      if (sel) res = res.filter(function (el) { return el.matches(sel); });
      return new VQuery(res);
    },

    first:  function () { return new VQuery(this.elements.slice(0, 1)); },
    last:   function () { return new VQuery(this.elements.slice(-1)); },
    eq:     function (i) { return new VQuery(this.elements[i] ? [this.elements[i]] : []); },
    get:    function (i) { return i === undefined ? this.elements.slice() : this.elements[i]; },

    index:  function () {
      var el = this.elements[0];
      if (!el || !el.parentNode) return -1;
      return Array.from(el.parentNode.children).indexOf(el);
    },

    is:     function (sel) {
      return this.elements.some(function (el) { return el.matches && el.matches(sel); });
    },

    not: function (sel) {
      if (typeof sel === 'function') {
        return new VQuery(this.elements.filter(function (el, i) { return !sel.call(el, i, el); }));
      }
      return new VQuery(this.elements.filter(function (el) { return !el.matches(sel); }));
    },

    filter: function (sel) {
      if (typeof sel === 'function') {
        return new VQuery(this.elements.filter(function (el, i) { return sel.call(el, i, el); }));
      }
      return new VQuery(this.elements.filter(function (el) { return el.matches(sel); }));
    },

    add: function (sel) {
      return new VQuery(this.elements.concat(new VQuery(sel).elements));
    },

    /* ── visibility ──────────────────────────────────────────────────────── */

    hide: function () { return this.css('display', 'none'); },

    show: function () {
      this.elements.forEach(function (el) {
        el.style.display = el._vWasDisplay || '';
      });
      return this;
    },

    toggle: function (show) {
      this.elements.forEach(function (el) {
        var hidden = el.style.display === 'none';
        var makeVisible = (show === undefined ? hidden : show);
        if (makeVisible) {
          el.style.display = el._vWasDisplay || '';
        } else {
          el._vWasDisplay = el.style.display;
          el.style.display = 'none';
        }
      });
      return this;
    },

    /* ── dimensions ──────────────────────────────────────────────────────── */

    width:    function () { return this.elements[0] ? this.elements[0].offsetWidth  : 0; },
    height:   function () { return this.elements[0] ? this.elements[0].offsetHeight : 0; },

    offset: function () {
      if (!this.elements[0]) return { top: 0, left: 0 };
      var r = this.elements[0].getBoundingClientRect();
      return {
        top:  r.top  + (global.pageYOffset || 0),
        left: r.left + (global.pageXOffset || 0)
      };
    },

    /* ── form helpers ────────────────────────────────────────────────────── */

    serialize: function () {
      var parts = [];
      this.elements.forEach(function (form) {
        Array.from(form.elements || []).forEach(function (el) {
          if (!el.name || el.disabled) return;
          if ((el.type === 'checkbox' || el.type === 'radio') && !el.checked) return;
          parts.push(encodeURIComponent(el.name) + '=' + encodeURIComponent(el.value));
        });
      });
      return parts.join('&');
    },

    focus:  function () { if (this.elements[0]) this.elements[0].focus();  return this; },
    blur:   function () { if (this.elements[0]) this.elements[0].blur();   return this; },
    submit: function () { if (this.elements[0]) this.elements[0].submit(); return this; },

    /* ── shorthand event binders ─────────────────────────────────────────── */
    click:    function (fn) { return fn ? this.on('click', fn)    : this.trigger('click'); },
    change:   function (fn) { return fn ? this.on('change', fn)   : this.trigger('change'); },
    submit:   function (fn) { return fn ? this.on('submit', fn)   : this.trigger('submit'); },
    keyup:    function (fn) { return this.on('keyup', fn); },
    keydown:  function (fn) { return this.on('keydown', fn); },
    mouseover:function (fn) { return this.on('mouseover', fn); },
    mouseout: function (fn) { return this.on('mouseout', fn); }
  };

  /* ── static methods (namespace-level, like jQuery static API) ─────────── */

  VQuery.ajax = function (options) {
    options = options || {};
    var method      = (options.method || options.type || 'GET').toUpperCase();
    var url         = options.url || '';
    var data        = options.data;
    var dataType    = options.dataType  || 'json';
    var contentType = (options.contentType !== undefined)
      ? options.contentType
      : 'application/x-www-form-urlencoded; charset=UTF-8';

    function serialize(obj) {
      if (typeof obj === 'string') return obj;
      return Object.keys(obj).map(function (k) {
        return encodeURIComponent(k) + '=' + encodeURIComponent(obj[k]);
      }).join('&');
    }

    /* GET: fold data into query string */
    if (data && method === 'GET') {
      url += (url.indexOf('?') > -1 ? '&' : '?') + serialize(data);
      data = null;
    }

    /* Build body for non-GET */
    var body = null;
    if (data) {
      if (typeof data === 'string') body = data;
      else if (contentType && contentType.indexOf('json') > -1) body = JSON.stringify(data);
      else body = serialize(data);
    }

    var headers = Object.assign({}, options.headers || {});
    if (body && contentType) headers['Content-Type'] = contentType;

    var promise = fetch(url, {
      method:  method,
      headers: headers,
      body:    body || undefined
    }).then(function (res) {
      if (!res.ok) {
        var err   = new Error('HTTP error ' + res.status);
        err.status = res.status;
        if (options.error) options.error(err, res.status, res.statusText);
        throw err;
      }
      if (dataType === 'text' || dataType === 'html') return res.text();
      if (dataType === 'xml') return res.text().then(function (t) {
        return new DOMParser().parseFromString(t, 'text/xml');
      });
      return res.json();
    }).then(function (result) {
      if (options.success) options.success(result);
      return result;
    });

    /* jQuery-style .done / .fail convenience on the returned promise */
    promise.done = function (fn) { promise.then(fn);   return promise; };
    promise.fail = function (fn) { promise.catch(fn);  return promise; };
    return promise;
  };

  VQuery.get = function (url, data, callback, dataType) {
    if (typeof data === 'function') { dataType = callback; callback = data; data = null; }
    return VQuery.ajax({ url: url, method: 'GET', data: data, success: callback, dataType: dataType || 'json' });
  };

  VQuery.post = function (url, data, callback, dataType) {
    return VQuery.ajax({ url: url, method: 'POST', data: data, success: callback, dataType: dataType || 'json' });
  };

  VQuery.each = function (obj, fn) {
    if (Array.isArray(obj)) obj.forEach(function (v, i) { fn.call(v, i, v); });
    else Object.keys(obj).forEach(function (k) { fn.call(obj[k], k, obj[k]); });
    return obj;
  };

  VQuery.extend = function (target) {
    Array.prototype.slice.call(arguments, 1).forEach(function (src) {
      if (src) Object.assign(target, src);
    });
    return target;
  };

  VQuery.isArray    = Array.isArray;
  VQuery.isFunction = function (v) { return typeof v === 'function'; };
  VQuery.type       = function (v) { return Object.prototype.toString.call(v).slice(8, -1).toLowerCase(); };
  VQuery.trim       = function (s) { return s.trim(); };
  VQuery.noop       = function () {};
  VQuery.now        = Date.now;

  VQuery.parseJSON  = function (s) { return JSON.parse(s); };

  /* ═══════════════════════════════════════════════════════════════════════════
     §2  TEMPLATE ENGINE  —  Vertex.template
         Full Mustache syntax: {{var}} (escaped), {{{var}}} / {{&var}}
         (unescaped), {{#name}}...{{/name}} sections (arrays loop; truthy
         objects/scalars push once; falsy/empty skip), {{^name}}...{{/name}}
         inverted sections, {{! comment }}, {{> partial}} (via the
         `partials` option), plus this engine's own {{#each}} (explicit,
         array-only loop) and {{#if}}...{{else}}...{{/if}}. Sections nest to
         any depth — inner blocks see outer-scope variables via per-key
         context fallback, the same way real Mustache's context stack works.
         Two-way data-bind, and Vertex.template.load(url) for remote
         template loading. Set Vertex.template.load.baseUri to avoid
         repeating the path prefix.
  ═══════════════════════════════════════════════════════════════════════════ */

  /* Single-pass HTML escape — one regex, one string allocation */
  var _escMap = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  var _escRe  = /[&<>"']/g;
  function escHtml(s) {
    return String(s).replace(_escRe, function (c) { return _escMap[c]; });
  }

  function resolvePath(obj, path) {
    /* "." is the implicit-iterator key (loop/section contexts wrap
       non-object values as {'.': value}) — treat it as a literal
       single-segment lookup. Feeding it to split('.') would otherwise
       produce ["", ""] and silently resolve to undefined. */
    if (path === '.') return obj != null ? obj['.'] : undefined;
    return path.split('.').reduce(function (o, k) {
      return o != null ? o[k] : undefined;
    }, obj);
  }

  /**
   * parseTemplate(tmpl, data, partials?) — render without new Function().
   *
   * This used to be an independent regex-replace chain, and it had a real
   * bug: a non-greedy /{{#each}}...{{/each}}/ match cannot handle nested
   * loops — the FIRST {{/each}} it finds closes the match, which for
   * {{#each o}}{{#each i}}...{{/each}}{{/each}} is the INNER loop's closer,
   * not the outer one's. It corrupted output on any nested loop.
   *
   * It's now a thin wrapper over the same tokenizeTemplate() AST the
   * compiled path uses (see compileTemplate below), walked directly by
   * renderNodes() instead of being turned into JS source. Both paths are
   * driven by one parser, so there is exactly one place nesting can break.
   */
  function parseTemplate(tmpl, data, partials) {
    return renderNodes(tokenizeTemplate(tmpl), data, partials);
  }

  /* ── Template compiler ──────────────────────────────────────────────────── */

  /*
   * tokenizeTemplate(src) → token AST
   *
   * Token types: text | var | raw | comment | each | if | section | inverted | partial
   *   each     → { type:'each',     key, children:[] }               — {{#each x}}...{{/each}}, array-only
   *   if       → { type:'if',       key, truthy:[], falsy:[] }        — {{#if x}}...{{else}}...{{/if}}
   *   section  → { type:'section',  key, children:[] }                — {{#x}}...{{/x}}, full Mustache section:
   *                                                                      array → loop; truthy object/scalar →
   *                                                                      single render with pushed context;
   *                                                                      falsy/empty array → skipped
   *   inverted → { type:'inverted', key, children:[] }                — {{^x}}...{{/x}}, renders only when
   *                                                                      x is falsy or an empty array
   *   partial  → { type:'partial',  key }                             — {{> name}}, resolved against the
   *                                                                      partials map passed to render
   *
   * `each` and `if` are kept as distinct node types (not folded into
   * `section`) so their existing narrower contracts don't change: `each`
   * is a silent no-op on anything that isn't an array, and `if` always
   * needs the boolean/else framing rather than a context push.
   *
   * Closing tags are resolved structurally (a stack), not by matching the
   * name in {{/name}} against the name in the corresponding {{#name}} —
   * {{#foo}}...{{/bar}} closes the same way {{#foo}}...{{/foo}} would.
   * This is deliberately more lenient than the Mustache spec.
   */
  function tokenizeTemplate(src) {
    var re = /\{\{\{([@\w.]+)\}\}\}|\{\{!\s*[\s\S]*?\s*\}\}|\{\{#each\s+([\w.]+)\s*\}\}|\{\{\/each\}\}|\{\{#if\s+([\w.]+)\s*\}\}|\{\{else\}\}|\{\{\/if\}\}|\{\{>\s*([\w.]+)\s*\}\}|\{\{\^\s*([\w.]+)\s*\}\}|\{\{#\s*([\w.]+)\s*\}\}|\{\{\/\s*([\w.]+)\s*\}\}|\{\{&\s*([@\w.]+)\s*\}\}|\{\{([@\w.]+)\}\}/g;
    var root  = [];
    var stack = [root];   /* stack of child arrays currently being appended to */
    var opens = [];       /* parallel stack of open {{#if}} nodes, for {{else}} */
    var last  = 0;
    var m;

    while ((m = re.exec(src)) !== null) {
      if (m.index > last) {
        stack[stack.length - 1].push({ type: 'text', value: src.slice(last, m.index) });
      }
      last = re.lastIndex;

      if (m[1] !== undefined) {                     /* {{{ raw }}} */
        stack[stack.length - 1].push({ type: 'raw', key: m[1] });
      } else if (m[0].lastIndexOf('{{!', 0) === 0) {  /* {{! comment }} */
        stack[stack.length - 1].push({ type: 'comment' });
      } else if (m[2] !== undefined) {                /* {{#each key}} */
        var eNode = { type: 'each', key: m[2], children: [] };
        stack[stack.length - 1].push(eNode);
        stack.push(eNode.children);
        opens.push(eNode);
      } else if (m[0] === '{{/each}}') {
        stack.pop(); opens.pop();
      } else if (m[3] !== undefined) {                /* {{#if key}} */
        var iNode = { type: 'if', key: m[3], truthy: [], falsy: [] };
        stack[stack.length - 1].push(iNode);
        stack.push(iNode.truthy);
        opens.push(iNode);
      } else if (m[0] === '{{else}}') {
        stack.pop();
        stack.push(opens[opens.length - 1].falsy);
      } else if (m[0] === '{{/if}}') {
        stack.pop(); opens.pop();
      } else if (m[4] !== undefined) {                /* {{> partial}} */
        stack[stack.length - 1].push({ type: 'partial', key: m[4] });
      } else if (m[5] !== undefined) {                /* {{^key}} inverted-open */
        var invNode = { type: 'inverted', key: m[5], children: [] };
        stack[stack.length - 1].push(invNode);
        stack.push(invNode.children);
        opens.push(invNode);
      } else if (m[6] !== undefined) {                /* {{#key}} section-open */
        var secNode = { type: 'section', key: m[6], children: [] };
        stack[stack.length - 1].push(secNode);
        stack.push(secNode.children);
        opens.push(secNode);
      } else if (m[7] !== undefined) {                /* {{/key}} generic close (section or inverted) */
        stack.pop(); opens.pop();
      } else if (m[8] !== undefined) {                /* {{&key}} unescaped alias */
        stack[stack.length - 1].push({ type: 'raw', key: m[8] });
      } else if (m[9] !== undefined) {                /* {{ escaped }} */
        stack[stack.length - 1].push({ type: 'var', key: m[9] });
      }
    }

    if (last < src.length) {
      stack[stack.length - 1].push({ type: 'text', value: src.slice(last) });
    }
    return root;
  }

  /*
   * renderNodes(nodes, data, partials?, depth?) → string
   *
   * Direct AST interpreter — used both as the CSP-safe fallback (in place
   * of the old regex-replace parseTemplate) and to render {{> partial}}
   * bodies from the compiled path, since partials aren't a hot enough path
   * to justify compiling them too. depth guards against a partial that
   * (directly or indirectly) includes itself.
   */
  function renderNodes(nodes, data, partials, depth) {
    depth = depth || 0;
    if (depth > 32) return '';
    var out = '';
    for (var i = 0; i < nodes.length; i++) {
      var n = nodes[i];
      if (n.type === 'text') {
        out += n.value;
      } else if (n.type === 'var') {
        /* != null (not !== undefined) so a JSON null -- e.g. an unset
           nullable field straight off the wire -- renders as empty, same
           as standard Mustache, instead of the literal string "null". */
        var v = resolvePath(data, n.key);
        out += v != null ? escHtml(v) : '';
      } else if (n.type === 'raw') {
        var rv = resolvePath(data, n.key);
        out += rv != null ? String(rv) : '';
      } else if (n.type === 'comment') {
        /* no output */
      } else if (n.type === 'each') {
        var arr = resolvePath(data, n.key);
        if (Array.isArray(arr)) {
          for (var j = 0; j < arr.length; j++) {
            out += renderNodes(n.children, mergeLoopContext(data, arr[j], j), partials, depth + 1);
          }
        }
      } else if (n.type === 'if') {
        var cond = resolvePath(data, n.key);
        out += renderNodes(cond ? n.truthy : n.falsy, data, partials, depth + 1);
      } else if (n.type === 'section') {
        var sv = resolvePath(data, n.key);
        if (Array.isArray(sv)) {
          for (var k = 0; k < sv.length; k++) {
            out += renderNodes(n.children, mergeLoopContext(data, sv[k], k), partials, depth + 1);
          }
        } else if (sv) {
          var pushed = (typeof sv === 'object') ? Object.assign({}, data, sv) : Object.assign({}, data, { '.': sv });
          out += renderNodes(n.children, pushed, partials, depth + 1);
        }
      } else if (n.type === 'inverted') {
        var iv = resolvePath(data, n.key);
        if (!iv || (Array.isArray(iv) && iv.length === 0)) {
          out += renderNodes(n.children, data, partials, depth + 1);
        }
      } else if (n.type === 'partial') {
        var partialSrc = partials && partials[n.key];
        if (typeof partialSrc === 'string') {
          out += renderNodes(tokenizeTemplate(partialSrc), data, partials, depth + 1);
        }
      }
    }
    return out;
  }

  /* Shared by 'each' and array-valued 'section': merge the parent context,
     the current item (or {'.':item} for non-object items), and @index. */
  function mergeLoopContext(parentData, item, idx) {
    var pushed = (typeof item === 'object' && item !== null) ? item : { '.': item };
    return Object.assign({}, parentData, pushed, { '@index': idx });
  }

  /*
   * codegenNodes(nodes, dataVar, counter) → JS source string
   *
   * counter is a single-element array [n] used as a mutable counter so
   * nested #each loops get unique variable names.
   *
   * For simple (non-dotted, non-@) keys the generated code uses direct
   * bracket access, avoiding a resolvePath() call and split() per token.
   */
  function codegenNodes(nodes, dataVar, ctr) {
    var NL   = '\n';   /* newline literal for generated code lines */
    var code = '';
    for (var ni = 0; ni < nodes.length; ni++) {
      var n   = nodes[ni];
      var uid = ctr[0]++;

      if (n.type === 'text') {
        code += '_o+=' + JSON.stringify(n.value) + ';' + NL;

      } else if (n.type === 'var') {
        var acc = (n.key.indexOf('.') < 0 && n.key.indexOf('@') < 0)
          ? (dataVar + '[' + JSON.stringify(n.key) + ']')
          : ('_rp(' + dataVar + ',' + JSON.stringify(n.key) + ')');
        /* != null (not !== undefined) -- see the matching renderNodes
           branch above for why (JSON null must render as empty, not the
           literal string "null"). */
        code += 'var _v' + uid + '=' + acc + ';_o+=_v' + uid + '!=null?_esc(_v' + uid + '):"";' + NL;

      } else if (n.type === 'raw') {
        var accR = (n.key.indexOf('.') < 0 && n.key.indexOf('@') < 0)
          ? (dataVar + '[' + JSON.stringify(n.key) + ']')
          : ('_rp(' + dataVar + ',' + JSON.stringify(n.key) + ')');
        code += 'var _r' + uid + '=' + accR + ';_o+=_r' + uid + '!=null?String(_r' + uid + '):"";' + NL;

      } else if (n.type === 'each') {
        var arrV = '_arr' + uid, itmV = '_itm' + uid, idxV = '_idx' + uid;
        code += 'var ' + arrV + '=_rp(' + dataVar + ',' + JSON.stringify(n.key) + ');' + NL;
        code += 'if(Array.isArray(' + arrV + ')){for(var ' + idxV + '=0;' + idxV + '<' + arrV + '.length;' + idxV + '++){' + NL;
        code += 'var ' + itmV + '=Object.assign({},' + dataVar + ',typeof ' + arrV + '[' + idxV + ']==="object"&&' + arrV + '[' + idxV + ']!==null?' + arrV + '[' + idxV + ']:{".":'+ arrV + '[' + idxV + ']},{"@index":' + idxV + '});' + NL;
        code += codegenNodes(n.children, itmV, ctr);
        code += '}}' + NL;

      } else if (n.type === 'if') {
        var condV = (n.key.indexOf('.') < 0 && n.key.indexOf('@') < 0)
          ? (dataVar + '[' + JSON.stringify(n.key) + ']')
          : ('_rp(' + dataVar + ',' + JSON.stringify(n.key) + ')');
        code += 'if(' + condV + '){' + NL;
        code += codegenNodes(n.truthy, dataVar, ctr);
        if (n.falsy && n.falsy.length) {
          code += '}else{' + NL;
          code += codegenNodes(n.falsy, dataVar, ctr);
        }
        code += '}' + NL;

      } else if (n.type === 'comment') {
        /* no output */

      } else if (n.type === 'section') {
        /* Array -> loop (identical shape to 'each'); truthy non-array ->
           single push (object's own keys, or {'.':value} for scalars);
           falsy or empty array -> nothing. The array branch covers empty
           arrays for free — a zero-length for-loop body just never runs. */
        var sArr = '_sarr' + uid, sItm = '_sitm' + uid, sIdx = '_sidx' + uid, sCtx = '_sctx' + uid;
        code += 'var ' + sArr + '=_rp(' + dataVar + ',' + JSON.stringify(n.key) + ');' + NL;
        code += 'if(Array.isArray(' + sArr + ')){for(var ' + sIdx + '=0;' + sIdx + '<' + sArr + '.length;' + sIdx + '++){' + NL;
        code += 'var ' + sItm + '=Object.assign({},' + dataVar + ',typeof ' + sArr + '[' + sIdx + ']==="object"&&' + sArr + '[' + sIdx + ']!==null?' + sArr + '[' + sIdx + ']:{".":' + sArr + '[' + sIdx + ']},{"@index":' + sIdx + '});' + NL;
        code += codegenNodes(n.children, sItm, ctr);
        code += '}}else if(' + sArr + '){' + NL;
        code += 'var ' + sCtx + '=(typeof ' + sArr + '==="object")?Object.assign({},' + dataVar + ',' + sArr + '):Object.assign({},' + dataVar + ',{".":' + sArr + '});' + NL;
        code += codegenNodes(n.children, sCtx, ctr);
        code += '}' + NL;

      } else if (n.type === 'inverted') {
        var ivVal = '_ival' + uid;
        code += 'var ' + ivVal + '=_rp(' + dataVar + ',' + JSON.stringify(n.key) + ');' + NL;
        code += 'if(!' + ivVal + '||(Array.isArray(' + ivVal + ')&&' + ivVal + '.length===0)){' + NL;
        code += codegenNodes(n.children, dataVar, ctr);
        code += '}' + NL;

      } else if (n.type === 'partial') {
        code += '_o+=_partial(' + JSON.stringify(n.key) + ',' + dataVar + ');' + NL;
      }
    }
    return code;
  }

  /*
   * compileTemplate(src) → function(data, escFn, rpFn, partialFn) | null
   *
   * Returns null if new Function() is blocked (e.g. strict CSP).
   * The caller falls back to parseTemplate() (via renderNodes) in that case.
   */
  function compileTemplate(src) {
    try {
      var nodes = tokenizeTemplate(src);
      var NL    = '\n';
      var body  = '"use strict";var _o="";' + NL + codegenNodes(nodes, 'data', [0]) + 'return _o;';
      return new Function('data', '_esc', '_rp', '_partial', body); /* jshint ignore:line */
    } catch (_e) {
      return null;
    }
  }

  /* ── Template constructor ────────────────────────────────────────────────── */

  function Template(options) {
    this._el       = typeof options.el === 'string'
      ? document.querySelector(options.el)
      : (options.el || null);
    this._template = options.template || '';
    this._data     = Object.assign({}, options.data || {});
    this._partials = options.partials || {};
    this._handlers = {};

    /* Compile once at construction time */
    this._compiled = compileTemplate(this._template);

    if (options.computed) {
      var self = this;
      this._computed = options.computed;
      Object.keys(options.computed).forEach(function (key) {
        Object.defineProperty(self._data, key, {
          get: function () { return options.computed[key].call(self); },
          enumerable: true
        });
      });
    }

    this._render();
    if (typeof options.oncomplete === 'function') options.oncomplete.call(this);
  }

  Template.prototype = {
    constructor: Template,

    _render: function () {
      if (!this._el) return;

      /* If a range-type data-bind input inside this template is mid-drag,
         defer ALL rendering — not just renders that input's own event would
         trigger — until the drag ends. Any render right now, from any
         source, would detach-and-reattach that input and silently end its
         native drag. this._data itself is still live and up to date (see
         _setSilent above); only the DOM catch-up waits. The 'change' handler
         above clears _vDragging and calls .set(), which is what finally lets
         a render through once the user releases. */
      if (Array.prototype.some.call(
            this._el.querySelectorAll('input[type=range][data-bind]'),
            function (el) { return el._vDragging; })) {
        return;
      }

      /* ── Pull the actively-focused data-bind input out before replacing
         innerHTML, so a live drag or keystroke on it survives the render.
         A range input's drag (and a text input's IME composition) is
         mouse-capture/session state tied to that exact DOM node — even
         swapping in an attribute-identical clone silently ends the
         gesture, as if the user had released the mouse. Everything else
         under this._el still gets fully rebuilt below; this is a narrow,
         deliberate exception for the one node the user is mid-interaction
         with. */
      var preserved     = null;
      var preservedBind = null;
      var savedStart = 0;
      var savedEnd   = 0;
      var savedDir   = 'none';
      if (typeof document !== 'undefined' && document.activeElement &&
          this._el.contains(document.activeElement)) {
        var ae = document.activeElement;
        var bind = ae.getAttribute('data-bind');
        if (bind) {
          preserved     = ae;
          preservedBind = bind;
          try {
            savedStart = ae.selectionStart  || 0;
            savedEnd   = ae.selectionEnd    || 0;
            savedDir   = ae.selectionDirection || 'none';
          } catch (_) { /* non-text inputs throw on selectionStart access */ }
        }
      }

      /* {{> name}} always renders via the direct interpreter, even when the
         surrounding template is compiled — partials are for composition,
         not a hot enough path to justify compiling them too. */
      var partials = this._partials;
      var renderPartial = function (name, data) {
        var src = partials[name];
        return typeof src === 'string' ? renderNodes(tokenizeTemplate(src), data, partials) : '';
      };

      /* Use the pre-compiled function if available; fall back to the AST interpreter */
      var html = this._compiled
        ? this._compiled(this._data, escHtml, resolvePath, renderPartial)
        : renderNodes(tokenizeTemplate(this._template), this._data, partials);
      this._el.innerHTML = html;

      /* ── Swap the preserved live node in place of its freshly-parsed
         placeholder, instead of just re-focusing a new one ── */
      if (preserved) {
        var placeholder = this._el.querySelector('[data-bind="' + preservedBind + '"]');
        if (placeholder && placeholder.tagName === preserved.tagName) {
          placeholder.parentNode.replaceChild(preserved, placeholder);
          preserved.focus();
          try { preserved.setSelectionRange(savedStart, savedEnd, savedDir); } catch (_) {}
        }
      }

      this._bindInputs();
    },

    /* Two-way binding: <input data-bind="key.path"> */
    _bindInputs: function () {
      var self = this;
      Array.from(this._el.querySelectorAll('[data-bind]')).forEach(function (input) {
        if (input._vBound) return;   /* preserved node from _render — already wired */
        input._vBound = true;

        var key  = input.getAttribute('data-bind');
        var val  = resolvePath(self._data, key);
        if (val !== undefined) input.value = val;

        if (input.type === 'range') {
          /* A range input's drag is native pointer-capture state tied to
             that exact DOM node. Per spec, capture releases the instant the
             element leaves the document — even swapping the *same* node
             back in a moment later (see _render()'s preserve-on-focus path)
             is still one JS-visible detach, which is enough to end it. So
             while dragging, only the data model is kept live (.get() is
             always current) — no re-render, no DOM touched at all. The rest
             of the template (anything else bound to this key) catches up
             once the drag actually ends.

             input._vDragging also gates _render() itself (see below) — not
             just this input's own handler. Some *other* code entirely
             (e.g. a setInterval elsewhere in the app calling .update() on an
             unrelated key) can still trigger a render while this input is
             mid-drag, and that render would detach-and-reattach it exactly
             the same way, ending the drag just as surely. So the guard has
             to live in _render() itself, not just here.

             "The drag has ended" is detected by debounce — a short idle gap
             in 'input' events — rather than by listening for 'change'. Some
             browsers fire 'change' more than once per drag instead of
             exactly once at release; trusting it would mean occasionally
             committing (and rendering) mid-gesture anyway, right back to
             the same interrupted-drag failure. A debounce needs no
             assumption about any browser's 'change' semantics at all. */
          var commitTimer = null;
          input.addEventListener('input', function () {
            input._vDragging = true;
            self._setSilent(key, input.value);
            clearTimeout(commitTimer);
            commitTimer = setTimeout(function () {
              input._vDragging = false;
              self.set(key, input.value);
            }, 120);
          });
        } else {
          input.addEventListener('input', function () {
            self.set(key, input.value);
          });
        }
      });
    },

    /* Write a value into _data without triggering a re-render. */
    _setSilent: function (key, val) {
      var parts = key.split('.');
      var obj   = this._data;
      for (var i = 0; i < parts.length - 1; i++) {
        if (obj[parts[i]] == null || typeof obj[parts[i]] !== 'object') {
          obj[parts[i]] = {};
        }
        obj = obj[parts[i]];
      }
      obj[parts[parts.length - 1]] = val;
    },

    get: function (key) {
      return resolvePath(this._data, key);
    },

    set: function (key, val) {
      /* Support nested key paths: "user.name" */
      var parts = key.split('.');
      var obj   = this._data;
      for (var i = 0; i < parts.length - 1; i++) {
        if (obj[parts[i]] == null || typeof obj[parts[i]] !== 'object') {
          obj[parts[i]] = {};
        }
        obj = obj[parts[i]];
      }
      obj[parts[parts.length - 1]] = val;
      this._render();
      this._emit('change', { keypath: key, value: val });
      return this;
    },

    update: function (data) {
      Object.assign(this._data, data);
      this._render();
      return this;
    },

    on: function (event, fn) {
      (this._handlers[event] = this._handlers[event] || []).push(fn);
      return this;
    },

    off: function (event, fn) {
      if (!this._handlers[event]) return this;
      this._handlers[event] = fn
        ? this._handlers[event].filter(function (f) { return f !== fn; })
        : [];
      return this;
    },

    _emit: function (event) {
      var args = Array.prototype.slice.call(arguments, 1);
      (this._handlers[event] || []).forEach(function (fn) { fn.apply(null, args); });
    },

    teardown: function () {
      if (this._el) this._el.innerHTML = '';
      this._handlers = {};
    }
  };

  /**
   * Template.load(url, options) — fetch and mount a remote template file.
   *
   * baseUri  {string}  Optional base path prepended to relative URLs.
   *                    Set once:  Vertex.template.load.baseUri = '/static/templates/';
   *                    Then call: Vertex.template.load('user-card', options);
   *                    Resolves → '/static/templates/user-card'
   *
   *                    Absolute URLs (starting with http://, https://, or /)
   *                    and URLs that already start with the baseUri are used
   *                    as-is, so fully-qualified paths always work unchanged.
   */
  Template.load = function (url, options) {
    var base     = typeof Template.load.baseUri === 'string' ? Template.load.baseUri : '';
    var absolute = /^(https?:\/\/|\/)/.test(url);
    var resolved = (!absolute && base) ? (base.replace(/\/$/, '') + '/' + url.replace(/^\//, '')) : url;

    return fetch(resolved)
      .then(function (res) {
        if (!res.ok) throw new Error('Vertex.template.load: HTTP ' + res.status + ' — ' + resolved);
        return res.text();
      })
      .then(function (html) {
        var div    = document.createElement('div');
        div.innerHTML = html;
        var tmplEl = div.querySelector('template');
        return new Template(Object.assign({ template: tmplEl ? tmplEl.innerHTML : html }, options || {}));
      });
  };

  /** Default baseUri — set this to avoid repeating the path on every load() call. */
  Template.load.baseUri = '';

  /* ═══════════════════════════════════════════════════════════════════════════
     §3  HASH ROUTER  —  Backbone-style
         Singleton Router for direct use + RouterClass for class-based syntax.
  ═══════════════════════════════════════════════════════════════════════════ */

  var Router = (function () {
    var routes  = [];
    var running = false;

    /* Convert  /posts/:id/*rest  →  regex with numbered capture groups */
    function toRegex(pattern) {
      var src = pattern
        .replace(/[-[\]{}()+?.,\\^$|#\s]/g, '\\$&') /* escape special chars */
        .replace(/:(\w+)/g,  '([^/]+)')              /* :named param          */
        .replace(/\*(\w+)/g, '(.*)');                /* *splat                */
      return new RegExp('^' + src + '$');
    }

    /* Extract param names in the order they appear in the pattern */
    function paramNames(pattern) {
      var names = [];
      pattern.replace(/:(\w+)|\*(\w+)/g, function (_, a, b) { names.push(a || b); });
      return names;
    }

    function getFragment() {
      var hash = global.location ? global.location.hash.slice(1).replace(/^\//, '') : '';
      try { return decodeURIComponent(hash); } catch (_) { return hash; }
    }

    function dispatch() {
      var frag = getFragment();
      for (var i = 0; i < routes.length; i++) {
        var r = routes[i];
        var m = frag.match(r.re);
        if (m) {
          /* Build named params object */
          var params = {};
          r.names.forEach(function (name, idx) { params[name] = m[idx + 1]; });
          r.handler(params);
          return true;
        }
      }
      return false;
    }

    return {
      add: function (pattern, handler) {
        routes.push({
          pattern: pattern,
          re:      toRegex(pattern),
          names:   paramNames(pattern),
          handler: handler
        });
        return this;
      },

      remove: function (pattern) {
        routes = routes.filter(function (r) { return r.pattern !== pattern; });
        return this;
      },

      start: function (options) {
        if (running) return this;
        running = true;
        if (global.addEventListener) global.addEventListener('hashchange', dispatch);
        if (!options || !options.silent) dispatch();
        return this;
      },

      stop: function () {
        running = false;
        if (global.removeEventListener) global.removeEventListener('hashchange', dispatch);
        return this;
      },

      navigate: function (path, options) {
        if (global.location) {
          global.location.hash = '/' + path.replace(/^\//, '');
        }
        if (options && options.trigger) dispatch();
        return this;
      },

      dispatch: dispatch,

      reset: function () {
        this.stop();
        routes  = [];
        running = false;
        return this;
      }
    };
  }());

  /* Class-based router — Backbone.Router syntax */
  function RouterClass(definition) {
    var self     = this;
    definition   = definition || {};
    var routeMap = definition.routes || this.routes || {};

    Object.keys(routeMap).forEach(function (pattern) {
      var handlerName = routeMap[pattern];
      Router.add(pattern, function (params) {
        var fn = self[handlerName];
        if (typeof fn === 'function') fn.call(self, params);
      });
    });
  }

  RouterClass.prototype.navigate = function (path, options) {
    Router.navigate(path, options);
  };

  RouterClass.extend = function (proto) {
    function Sub(definition) {
      RouterClass.call(this, definition || proto);
    }
    Sub.prototype = Object.create(RouterClass.prototype);
    Object.assign(Sub.prototype, proto);
    Sub.prototype.constructor = Sub;
    Sub.extend = RouterClass.extend;
    return Sub;
  };

  /* ═══════════════════════════════════════════════════════════════════════════
     §4  PUBLIC API  —  Vertex namespace
  ═══════════════════════════════════════════════════════════════════════════ */

  var Vertex = {
    /* ── Template engine (Mustache, Ractive.load-style) ── */
    template:          Template,
    parseTemplate:     parseTemplate,

    /* ── Router (Backbone-style) ── */
    Router:            Router,
    RouterClass:       RouterClass,

    /* ── DOM layer (VQuery) ── */
    VQuery:            VQuery,

    /** Vertex DOM wrapper — always available, never conflicts with jQuery */
    $v: function (selector, context) { return new VQuery(selector, context); },

    /* ── AJAX shortcuts ── */
    ajax:  VQuery.ajax,
    get:   VQuery.get,
    post:  VQuery.post
  };

  /* Expose on global */
  global.Vertex = Vertex;

  /* V$ is always our shorthand */
  global.V$ = Vertex.$v;

  /* Set global $ ONLY when neither jQuery nor any other $ is already present.
     This ensures jQuery.noConflict() and similar patterns work correctly. */
  if (typeof global.jQuery === 'undefined' && typeof global.$ === 'undefined') {
    global.$ = Vertex.$v;
  }

  return Vertex;
}));
