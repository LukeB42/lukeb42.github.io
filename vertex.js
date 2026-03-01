/**
 * vertex.js  —  single-file library combining:
 *
 *   1. VQuery    — DOM layer (hn.js-inspired, jQuery surface-compatible)
 *   2. Reconciler — Fiber-based React clone (pomb.us architecture + hooks)
 *   3. template  — Mustache template engine + component loader (Vertex.template)
 *   4. Router    — Backbone-style hash router (class-based + singleton)
 *   5. Glue      — useHash hook, unified Vertex namespace
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
     §2  FIBER RECONCILER  —  React clone
         Architecture: pomb.us  |  Hooks: useState, useReducer, useEffect,
         useMemo, useCallback, useRef, useContext, useHash
  ═══════════════════════════════════════════════════════════════════════════ */

  /* Effect tags */
  var PLACEMENT = 'P';
  var UPDATE    = 'U';
  var DELETION  = 'D';

  /* Scheduler state */
  var nextUnit       = null; /* next fiber unit of work             */
  var wipRoot        = null; /* work-in-progress root               */
  var curRoot        = null; /* last committed root                 */
  var deletions      = [];   /* fibers to delete in next commit     */
  var wipFiber       = null; /* currently rendering function fiber  */
  var hookIdx        = 0;    /* hook cursor for current fiber       */
  var pendingEffects = [];   /* effects deferred until after commit */

  /* ── scheduler ─────────────────────────────────────────────────────────── */

  var scheduled = false; /* dedup: at most one ric() in flight at a time */

  function scheduleWork() {
    if (scheduled) return;
    scheduled = true;
    ric(workLoop);
  }

  function workLoop(deadline) {
    scheduled = false;
    while (nextUnit && deadline.timeRemaining() > 1) {
      nextUnit = performUnit(nextUnit);
    }
    if (!nextUnit && wipRoot) commitRoot();
    if (nextUnit) scheduleWork();
  }

  /* ── per-fiber work ─────────────────────────────────────────────────────── */

  function performUnit(fiber) {
    if (typeof fiber.type === 'function') {
      updateFunctionComponent(fiber);
    } else {
      updateHostComponent(fiber);
    }
    /* Depth-first: child → sibling → uncle */
    if (fiber.child) return fiber.child;
    var next = fiber;
    while (next) {
      if (next.sibling) return next.sibling;
      next = next.parent;
    }
    return null;
  }

  function updateFunctionComponent(fiber) {
    wipFiber = fiber;
    hookIdx  = 0;
    wipFiber.hooks        = [];
    wipFiber._ctxProvide  = null; /* cleared; Provider component may set this */

    var output   = fiber.type(fiber.props);

    /* If the component was a Provider it will have tagged _ctxProvide.
       Build the new contextMap by layering its values over the parent's map.
       Children reconciled below will inherit this updated map. */
    if (fiber._ctxProvide) {
      fiber.contextMap = Object.assign({}, fiber.contextMap, fiber._ctxProvide);
      fiber._ctxProvide = null;
    }

    /* Support returning arrays (Fragment) or null */
    var children = flattenChildren(output);
    reconcileChildren(fiber, children);
  }

  function updateHostComponent(fiber) {
    if (!fiber.dom) fiber.dom = createDom(fiber);
    reconcileChildren(fiber, fiber.props.children || []);
  }

  function flattenChildren(output) {
    var arr = Array.isArray(output) ? output : [output];
    var result = [];
    for (var i = 0; i < arr.length; i++) {
      if (arr[i] === null || arr[i] === undefined || arr[i] === false) continue;
      if (Array.isArray(arr[i])) {
        var inner = flattenChildren(arr[i]);
        for (var j = 0; j < inner.length; j++) result.push(inner[j]);
      } else {
        result.push(arr[i]);
      }
    }
    return result;
  }

  /* ── DOM helpers ─────────────────────────────────────────────────────────── */

  function createDom(fiber) {
    var dom = fiber.type === 'TEXT_ELEMENT'
      ? document.createTextNode('')
      : document.createElement(fiber.type);
    patchDom(dom, {}, fiber.props);
    /* Wire ref immediately for newly-created DOM nodes */
    if (fiber.props && fiber.props.ref && fiber.props.ref !== null &&
        typeof fiber.props.ref === 'object') {
      fiber.props.ref.current = dom;
    }
    return dom;
  }

  /* 'on' prefix check without a function call — hot path */
  function isEventProp(k) {
    return k.charCodeAt(0) === 111 && k.charCodeAt(1) === 110 && k.length > 2;
  }

  /* Exclude 'ref' — it's handled in commitWork, not as a DOM property */
  function isRealProp(k) { return k !== 'children' && k !== 'ref' && !isEventProp(k); }

  /**
   * setStableListener — attach a proxy listener once; on updates just swap
   * the target function in place.  Eliminates removeEventListener /
   * addEventListener churn on every re-render (the single biggest DOM cost
   * for lists with inline callbacks).
   */
  function setStableListener(dom, evName, fn) {
    if (!dom._vxev) dom._vxev = {};
    if (evName in dom._vxev) {
      dom._vxev[evName] = fn;           /* update target — proxy stays attached */
    } else {
      dom._vxev[evName] = fn;
      /* IIFE captures evName so the closure is correct in loops */
      (function (name) {
        dom.addEventListener(name, function (e) {
          if (dom._vxev[name]) dom._vxev[name](e);
        });
      }(evName));
    }
  }

  function patchDom(dom, prev, next) {
    var k;
    /* Pass 1 — remove stale non-event props; null out dropped event targets */
    for (k in prev) {
      if (!isRealProp(k)) {
        if (isEventProp(k)) {
          if (!(k in next) && dom._vxev) dom._vxev[k.slice(2).toLowerCase()] = null;
        }
        continue;
      }
      if (!(k in next)) {
        if      (k === 'className') dom.className    = '';
        else if (k === 'style')     dom.style.cssText = '';
        else                         dom[k]           = '';
      }
    }
    /* Pass 2 — apply new / changed props; install or update event targets */
    for (k in next) {
      if (!isRealProp(k)) {
        if (isEventProp(k)) {
          setStableListener(dom, k.slice(2).toLowerCase(), next[k]);
        }
        continue;
      }
      if (prev[k] === next[k]) continue;
      if      (k === 'className')                            dom.className = next[k];
      else if (k === 'style' && typeof next[k] === 'object') Object.assign(dom.style, next[k]);
      else                                                    dom[k] = next[k];
    }
  }

  /* ── reconciliation ──────────────────────────────────────────────────────── */

  function reconcileChildren(fiber, elements) {
    /* Build lookup structures from old children in one pass */
    var oldFiber = fiber.alternate && fiber.alternate.child;
    var keyMap   = null;   /* key  → oldFiber (keyed children)    */
    var byPos    = [];     /* index → oldFiber (unkeyed children)  */
    var scan     = oldFiber;
    while (scan) {
      var sk = scan.props && scan.props.key;
      if (sk != null) {
        if (!keyMap) keyMap = {};
        keyMap[String(sk)] = scan;
      } else {
        byPos.push(scan);
      }
      scan = scan.sibling;
    }

    var posIdx = 0;
    var prev   = null;

    for (var i = 0; i < elements.length; i++) {
      var el    = elements[i];
      var elKey = el && el.props && el.props.key;
      var old   = null;

      if (elKey != null) {
        /* Keyed: O(1) hash lookup */
        var sKey = String(elKey);
        if (keyMap && keyMap[sKey]) { old = keyMap[sKey]; delete keyMap[sKey]; }
      } else {
        /* Unkeyed: consume next positional old fiber */
        old = byPos[posIdx++] || null;
      }

      var sameType = old && el && old.type === el.type;
      var newFiber;

      if (sameType) {
        newFiber = {
          type: old.type, props: el.props, dom: old.dom,
          parent: fiber, contextMap: fiber.contextMap || null,
          alternate: old, effectTag: UPDATE, hooks: []
        };
      } else {
        if (old) { old.effectTag = DELETION; deletions.push(old); }
        newFiber = {
          type: el.type, props: el.props, dom: null,
          parent: fiber, contextMap: fiber.contextMap || null,
          alternate: null, effectTag: PLACEMENT, hooks: []
        };
      }

      if (i === 0)  fiber.child   = newFiber;
      else if (prev) prev.sibling = newFiber;
      prev = newFiber;
    }

    /* Delete remaining unkeyed old fibers (list shrank) */
    for (; posIdx < byPos.length; posIdx++) {
      byPos[posIdx].effectTag = DELETION;
      deletions.push(byPos[posIdx]);
    }
    /* Delete remaining keyed old fibers (keys disappeared) */
    if (keyMap) {
      for (var mk in keyMap) {
        keyMap[mk].effectTag = DELETION;
        deletions.push(keyMap[mk]);
      }
    }

    if (prev) prev.sibling = null;
  }

  /* ── commit phase ─────────────────────────────────────────────────────────── */

  /* Walk up from fiber.parent to find the nearest ancestor with a real DOM node */
  function nearestDom(fiber) {
    var f = fiber.parent;
    while (f && !f.dom) f = f.parent;
    return f ? f.dom : null;
  }

  /* Move any effects accumulated on a fiber into the global pending list */
  function flushFiberEffects(fiber) {
    if (!fiber._pendingEffects) return;
    for (var _ei = 0; _ei < fiber._pendingEffects.length; _ei++) {
      pendingEffects.push(fiber._pendingEffects[_ei]);
    }
    delete fiber._pendingEffects;
  }

  function commitRoot() {
    /* Deletions need their own parent-DOM lookup since they may be detached */
    deletions.forEach(function (f) { commitWork(f, nearestDom(f)); });
    if (wipRoot.child) commitWork(wipRoot.child, wipRoot.dom);
    curRoot = wipRoot;
    wipRoot = null;

    /* Run all queued effects now that the DOM is fully updated */
    var toRun = pendingEffects.splice(0);
    for (var _ri = 0; _ri < toRun.length; _ri++) {
      var item = toRun[_ri];
      if (typeof item.oldCleanup === 'function') item.oldCleanup();
      var cleanup = item.effect();
      item.hook.cleanup = typeof cleanup === 'function' ? cleanup : null;
    }
  }

  /*
   * commitWork(startFiber, startParentDom)
   *
   * Iterative pre-order walk using an explicit stack.  Avoids call-stack
   * overflow on deep trees.  parentDom is carried per-frame so host vs
   * function-component fibers thread correctly without any upward walks.
   *
   * Stack frames: { fiber, parentDom }
   * Sibling pushed before child so child is popped (processed) first.
   */
  function commitWork(startFiber, startParentDom) {
    var stack = [{ f: startFiber, p: startParentDom }];
    while (stack.length) {
      var frame     = stack.pop();
      var fiber     = frame.f;
      var parentDom = frame.p;
      if (!fiber) continue;

      if (fiber.effectTag === PLACEMENT && fiber.dom && parentDom) {
        parentDom.appendChild(fiber.dom);
      } else if (fiber.effectTag === UPDATE && fiber.dom) {
        patchDom(fiber.dom, fiber.alternate.props, fiber.props);
        /* Re-wire ref on update in case the ref object itself changed */
        if (fiber.props && fiber.props.ref && typeof fiber.props.ref === 'object') {
          fiber.props.ref.current = fiber.dom;
        }
      } else if (fiber.effectTag === DELETION) {
        commitDeletion(fiber, parentDom);
        flushFiberEffects(fiber);
        continue; /* deleted subtree fully handled by commitDeletion */
      }

      flushFiberEffects(fiber);

      /* Children of a host fiber attach to fiber.dom;
         children of a function fiber inherit parentDom unchanged */
      var childParent = fiber.dom || parentDom;
      /* Push sibling first — LIFO means child is processed before sibling */
      if (fiber.sibling) stack.push({ f: fiber.sibling, p: parentDom  });
      if (fiber.child)   stack.push({ f: fiber.child,   p: childParent });
    }
  }

  function commitDeletion(fiber, parentDom) {
    removeFiberDom(fiber, parentDom);
    cleanupEffectTree(fiber);
  }

  /* Walk down the first-child chain to find and remove the first real DOM node */
  function removeFiberDom(fiber, parentDom) {
    var f = fiber;
    while (f) {
      if (f.dom) {
        if (parentDom) parentDom.removeChild(f.dom);
        return;
      }
      f = f.child;
    }
  }

  /* Walk down the first-child chain, running effect cleanups at each level.
     Siblings are NOT followed — each sibling deletion is a separate entry
     in the deletions array and will be visited by commitRoot independently. */
  function cleanupEffectTree(fiber) {
    var f = fiber;
    while (f) {
      var hooks = f.hooks;
      if (hooks) {
        for (var hi = 0; hi < hooks.length; hi++) {
          if (hooks[hi] && typeof hooks[hi].cleanup === 'function') {
            hooks[hi].cleanup();
          }
        }
      }
      f = f.child;
    }
  }

  /* ── trigger re-render ───────────────────────────────────────────────────── */

  function scheduleUpdate() {
    if (!curRoot) return;
    wipRoot   = { dom: curRoot.dom, props: curRoot.props, alternate: curRoot };
    nextUnit  = wipRoot;
    deletions = [];
    scheduleWork();
  }

  /* ── public createElement / render ──────────────────────────────────────── */

  /* Push items from arr into out, recursing into nested arrays, skipping nullish */
  function flatPush(out, arr) {
    for (var _i = 0; _i < arr.length; _i++) {
      var _c = arr[_i];
      if (_c === null || _c === undefined || _c === false) continue;
      if (Array.isArray(_c)) { flatPush(out, _c); continue; }
      out.push(typeof _c === 'object' ? _c : createTextElement(String(_c)));
    }
  }

  function createElement(type, props) {
    var children = [];
    for (var _a = 2; _a < arguments.length; _a++) {
      var _ch = arguments[_a];
      if (_ch === null || _ch === undefined || _ch === false) continue;
      if (Array.isArray(_ch)) { flatPush(children, _ch); continue; }
      children.push(typeof _ch === 'object' ? _ch : createTextElement(String(_ch)));
    }
    return { type: type, props: Object.assign({}, props, { children: children }) };
  }

  function createTextElement(text) {
    return { type: 'TEXT_ELEMENT', props: { nodeValue: text, children: [] } };
  }

  function render(element, container) {
    wipRoot   = { dom: container, props: { children: [element] }, alternate: curRoot };
    nextUnit  = wipRoot;
    deletions = [];
    scheduleWork();
  }

  /* ── hooks ───────────────────────────────────────────────────────────────── */

  function useState(initial) {
    return useReducer(
      function (state, action) {
        return typeof action === 'function' ? action(state) : action;
      },
      typeof initial === 'function' ? initial() : initial
    );
  }

  function useReducer(reducer, initial) {
    var oldHook = wipFiber.alternate && wipFiber.alternate.hooks[hookIdx];

    /* The "cell" is a stable object that survives across renders.
       It holds the pending action queue and the dispatch function so
       dispatch has a stable identity — passing it as a prop won't
       trigger unnecessary child re-renders. */
    var cell = oldHook ? oldHook._cell : { queue: [] };

    var state = oldHook
      ? oldHook.state
      : (typeof initial === 'function' ? initial() : initial);

    /* Drain all actions queued since the last render */
    for (var _qi = 0; _qi < cell.queue.length; _qi++) {
      state = reducer(state, cell.queue[_qi]);
    }
    cell.queue = [];

    /* Create dispatch once per hook lifetime; it closes over the stable cell */
    if (!cell.dispatch) {
      cell.dispatch = function (action) {
        cell.queue.push(action);
        scheduleUpdate();
      };
    }

    var hook = { state: state, _cell: cell };
    wipFiber.hooks[hookIdx++] = hook;
    return [hook.state, cell.dispatch];
  }

  function useEffect(effect, deps) {
    var oldHook     = wipFiber.alternate && wipFiber.alternate.hooks[hookIdx];
    var depsChanged = !oldHook
      || !deps
      || deps.some(function (d, i) { return d !== (oldHook.deps && oldHook.deps[i]); });

    var hook = { deps: deps, cleanup: oldHook ? oldHook.cleanup : null };

    if (depsChanged) {
      wipFiber._pendingEffects = wipFiber._pendingEffects || [];
      wipFiber._pendingEffects.push({
        effect:     effect,
        oldCleanup: oldHook ? oldHook.cleanup : null,
        hook:       hook  /* commitRoot writes the new cleanup back here */
      });
    }

    wipFiber.hooks[hookIdx++] = hook;
  }

  function useMemo(factory, deps) {
    var oldHook     = wipFiber.alternate && wipFiber.alternate.hooks[hookIdx];
    var depsChanged = !oldHook
      || !deps
      || deps.some(function (d, i) { return d !== (oldHook.deps && oldHook.deps[i]); });

    var hook = {
      value: depsChanged ? factory() : oldHook.value,
      deps:  deps
    };
    wipFiber.hooks[hookIdx++] = hook;
    return hook.value;
  }

  function useCallback(fn, deps) {
    /* eslint-disable-next-line no-unused-vars */
    return useMemo(function () { return fn; }, deps);
  }

  function useRef(initial) {
    var oldHook = wipFiber.alternate && wipFiber.alternate.hooks[hookIdx];
    /* Ref object is stable across renders — same object reference always returned */
    var hook    = oldHook || { current: typeof initial === 'function' ? initial() : initial };
    wipFiber.hooks[hookIdx++] = hook;
    return hook;
  }

  /* Context — per-fiber propagation via contextMap
   *
   * Each fiber carries a contextMap (plain object: ctx._id → value).
   * Providers inject their value into this map; the map is inherited by
   * all descendant fibers so nested and parallel contexts work correctly.
   *
   * Two Providers of the same context in different subtrees are completely
   * independent. Nested Providers of the same context shadow correctly.
   */
  var _ctxIdCounter = 0;

  function createContext(defaultValue) {
    var id  = _ctxIdCounter++;
    var ctx = { _id: id, _defaultValue: defaultValue };

    /* Provider — a function component that marks the current fiber so
       updateFunctionComponent can write id→value into the contextMap
       before reconciling children. */
    ctx.Provider = function ProviderComponent(props) {
      /* Tag this fiber for post-render contextMap update */
      if (wipFiber) {
        wipFiber._ctxProvide      = wipFiber._ctxProvide || {};
        wipFiber._ctxProvide[id]  = props.value;
      }
      var children = props.children;
      return Array.isArray(children) ? (children[0] || null) : (children || null);
    };
    ctx.Provider._vxCtxId = id; /* marker so devtools can identify it */

    ctx.Consumer = function ConsumerComponent(props) {
      var fn  = Array.isArray(props.children) ? props.children[0] : props.children;
      var val = useContext(ctx);
      return typeof fn === 'function' ? fn(val) : null;
    };

    return ctx;
  }

  function useContext(ctx) {
    if (wipFiber && wipFiber.contextMap && ctx._id in wipFiber.contextMap) {
      return wipFiber.contextMap[ctx._id];
    }
    return ctx._defaultValue;
  }

  /* Fragment: returns children to the reconciler as a flat array */
  function Fragment(props) { return props.children; }

  /* lazy: throws a Promise (Suspense protocol) until module resolves.
     The single thenable is stored and re-thrown on each render attempt so
     factory() is called exactly once regardless of how many times the
     component tries to render before the module arrives. */
  function lazy(factory) {
    var status   = 'pending';
    var Component;
    var thenable = factory().then(function (mod) {
      status    = 'resolved';
      Component = mod.default || mod;
    });
    return function LazyWrapper(props) {
      if (status === 'resolved') return createElement(Component, props);
      throw thenable; /* re-throw the same promise — no second fetch */
    };
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     §3  TEMPLATE ENGINE  —  Vertex.template
         Mustache {{ }}, {{{ unescaped }}}, {{#if}}, {{#each}}, two-way
         data-bind, and Vertex.template.load(url) for remote template loading.
         Set Vertex.template.load.baseUri to avoid repeating the path prefix.
  ═══════════════════════════════════════════════════════════════════════════ */

  /* Single-pass HTML escape — one regex, one string allocation */
  var _escMap = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  var _escRe  = /[&<>"']/g;
  function escHtml(s) {
    return String(s).replace(_escRe, function (c) { return _escMap[c]; });
  }

  function resolvePath(obj, path) {
    return path.split('.').reduce(function (o, k) {
      return o != null ? o[k] : undefined;
    }, obj);
  }

  function parseTemplate(tmpl, data) {
    /* {{#each keyPath}} ... {{/each}} */
    tmpl = tmpl.replace(
      /\{\{#each\s+([\w.]+)\s*\}\}([\s\S]*?)\{\{\/each\}\}/g,
      function (_, key, inner) {
        var arr = resolvePath(data, key);
        if (!Array.isArray(arr)) return '';
        return arr.map(function (item, idx) {
          var ctx = Object.assign(
            {},
            data,
            typeof item === 'object' && item !== null ? item : { '.': item },
            { '@index': idx }
          );
          return parseTemplate(inner, ctx);
        }).join('');
      }
    );

    /* {{#if keyPath}} ... {{else}} ... {{/if}} */
    tmpl = tmpl.replace(
      /\{\{#if\s+([\w.]+)\s*\}\}([\s\S]*?)(?:\{\{else\}\}([\s\S]*?))?\{\{\/if\}\}/g,
      function (_, key, truthy, falsy) {
        return resolvePath(data, key)
          ? parseTemplate(truthy, data)
          : parseTemplate(falsy || '', data);
      }
    );

    /* {{{ unescaped }}} — @ allowed for @index, @key, etc. */
    tmpl = tmpl.replace(/\{\{\{([@\w.]+)\}\}\}/g, function (_, key) {
      var v = resolvePath(data, key);
      return v !== undefined ? String(v) : '';
    });

    /* {{ escaped }} */
    tmpl = tmpl.replace(/\{\{([@\w.]+)\}\}/g, function (_, key) {
      var v = resolvePath(data, key);
      return v !== undefined ? escHtml(v) : '';
    });

    return tmpl;
  }

  /* ── Template compiler ──────────────────────────────────────────────────── */

  /*
   * tokenizeTemplate(src) → token AST
   *
   * Token types: text | var | raw | each | if
   *   each → { type:'each', key, children:[] }
   *   if   → { type:'if',   key, truthy:[], falsy:[] }
   */
  function tokenizeTemplate(src) {
    var re = /\{\{\{([@\w.]+)\}\}\}|\{\{#each\s+([\w.]+)\s*\}\}|\{\{\/each\}\}|\{\{#if\s+([\w.]+)\s*\}\}|\{\{else\}\}|\{\{\/if\}\}|\{\{([@\w.]+)\}\}/g;
    var root    = [];
    var stack   = [root];   /* stack of child arrays */
    var ifStack = [];       /* stack of current {{#if}} nodes */
    var last    = 0;
    var m;

    while ((m = re.exec(src)) !== null) {
      if (m.index > last) {
        stack[stack.length - 1].push({ type: 'text', value: src.slice(last, m.index) });
      }
      last = re.lastIndex;

      if (m[1]) {                         /* {{{ raw }}} */
        stack[stack.length - 1].push({ type: 'raw', key: m[1] });
      } else if (m[2]) {                  /* {{#each key}} */
        var eNode = { type: 'each', key: m[2], children: [] };
        stack[stack.length - 1].push(eNode);
        stack.push(eNode.children);
      } else if (m[0] === '{{/each}}') {
        stack.pop();
      } else if (m[3]) {                  /* {{#if key}} */
        var iNode = { type: 'if', key: m[3], truthy: [], falsy: [] };
        stack[stack.length - 1].push(iNode);
        ifStack.push(iNode);
        stack.push(iNode.truthy);
      } else if (m[0] === '{{else}}') {
        stack.pop();
        stack.push(ifStack[ifStack.length - 1].falsy);
      } else if (m[0] === '{{/if}}') {
        stack.pop();
        ifStack.pop();
      } else if (m[4]) {                  /* {{ escaped }} */
        stack[stack.length - 1].push({ type: 'var', key: m[4] });
      }
    }

    if (last < src.length) {
      stack[stack.length - 1].push({ type: 'text', value: src.slice(last) });
    }
    return root;
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
        code += 'var _v' + uid + '=' + acc + ';_o+=_v' + uid + '!==undefined?_esc(_v' + uid + '):"";' + NL;

      } else if (n.type === 'raw') {
        var accR = (n.key.indexOf('.') < 0 && n.key.indexOf('@') < 0)
          ? (dataVar + '[' + JSON.stringify(n.key) + ']')
          : ('_rp(' + dataVar + ',' + JSON.stringify(n.key) + ')');
        code += 'var _r' + uid + '=' + accR + ';_o+=_r' + uid + '!==undefined?String(_r' + uid + '):"";' + NL;

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
      }
    }
    return code;
  }

  /*
   * compileTemplate(src) → function(data, escFn, rpFn) | null
   *
   * Returns null if new Function() is blocked (e.g. strict CSP).
   * The caller falls back to parseTemplate() in that case.
   */
  function compileTemplate(src) {
    try {
      var nodes = tokenizeTemplate(src);
      var NL    = '\n';
      var body  = '"use strict";var _o="";' + NL + codegenNodes(nodes, 'data', [0]) + 'return _o;';
      return new Function('data', '_esc', '_rp', body); /* jshint ignore:line */
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

      /* ── Save focus / cursor state before replacing innerHTML ── */
      var savedBind  = null;
      var savedStart = 0;
      var savedEnd   = 0;
      var savedDir   = 'none';
      if (typeof document !== 'undefined' && document.activeElement &&
          this._el.contains(document.activeElement)) {
        var ae = document.activeElement;
        savedBind  = ae.getAttribute('data-bind');
        try {
          savedStart = ae.selectionStart  || 0;
          savedEnd   = ae.selectionEnd    || 0;
          savedDir   = ae.selectionDirection || 'none';
        } catch (_) { /* non-text inputs throw on selectionStart access */ }
      }

      /* Use the pre-compiled function if available; fall back to regex parser */
      var html = this._compiled
        ? this._compiled(this._data, escHtml, resolvePath)
        : parseTemplate(this._template, this._data);
      this._el.innerHTML = html;
      this._bindInputs();

      /* ── Restore focus and cursor position ── */
      if (savedBind) {
        var target = this._el.querySelector('[data-bind="' + savedBind + '"]');
        if (target) {
          target.focus();
          try { target.setSelectionRange(savedStart, savedEnd, savedDir); } catch (_) {}
        }
      }
    },

    /* Two-way binding: <input data-bind="key.path"> */
    _bindInputs: function () {
      var self = this;
      Array.from(this._el.querySelectorAll('[data-bind]')).forEach(function (input) {
        var key  = input.getAttribute('data-bind');
        var val  = resolvePath(self._data, key);
        if (val !== undefined) input.value = val;

        input.addEventListener('input', function () {
          self.set(key, input.value);
        });
      });
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
     §4  HASH ROUTER  —  Backbone-style
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
     §5  INTEGRATION GLUE
  ═══════════════════════════════════════════════════════════════════════════ */

  /**
   * useHash()  —  returns the current URL hash fragment and re-renders the
   * component whenever it changes.  Use inside any Vertex function component.
   */
  function useHash() {
    function getHash() {
      return global.location ? global.location.hash.slice(1) : '';
    }

    var pair   = useState(getHash);
    var hash   = pair[0];
    var setHash = pair[1];

    useEffect(function () {
      function onHashChange() { setHash(getHash()); }
      if (global.addEventListener) global.addEventListener('hashchange', onHashChange);
      return function () {
        if (global.removeEventListener) global.removeEventListener('hashchange', onHashChange);
      };
    }, []);

    return hash;
  }

  /* ═══════════════════════════════════════════════════════════════════════════
     §6  PUBLIC API  —  Vertex namespace
  ═══════════════════════════════════════════════════════════════════════════ */

  var Vertex = {
    /* ── React-compatible surface ── */
    createElement:     createElement,
    createTextElement: createTextElement,
    render:            render,
    Fragment:          Fragment,
    lazy:              lazy,
    createContext:     createContext,

    /* ── Hooks ── */
    useState:          useState,
    useReducer:        useReducer,
    useEffect:         useEffect,
    useMemo:           useMemo,
    useCallback:       useCallback,
    useRef:            useRef,
    useContext:        useContext,
    useHash:           useHash,

    /* ── Template engine ── */
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
