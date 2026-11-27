(function () {
  "use strict";

  function safeJson(text) {
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch (e) {
      return null;
    }
  }

  function xhrRequest(method, url, body, callback) {
    var xhr = new XMLHttpRequest();
    var timedOut = false;
    var timer = setTimeout(function () {
      timedOut = true;
      xhr.abort();
      callback(new Error("Tiempo de espera agotado"));
    }, 15000);

    xhr.open(method, url, true);
    // El servidor rechaza órdenes sin esta cabecera (ver server/main.py).
    xhr.setRequestHeader("X-Requested-With", "ipad-monitor");
    if (body !== null && body !== undefined) {
      xhr.setRequestHeader("Content-Type", "application/json");
    }

    xhr.onreadystatechange = function () {
      if (xhr.readyState !== 4 || timedOut) return;
      clearTimeout(timer);

      if (xhr.status >= 200 && xhr.status < 300) {
        var data = safeJson(xhr.responseText);
        if (data === null && xhr.responseText && xhr.responseText.length > 0) {
          callback(new Error("Respuesta inválida del servidor"));
          return;
        }
        callback(null, data || {});
        return;
      }

      if (xhr.status === 401 && window.location.pathname !== "/login") {
        // Sin sesión: pedir el PIN y volver a esta página.
        window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
        return;
      }
      var detail = safeJson(xhr.responseText);
      callback(new Error(detail && detail.detail ? detail.detail : "HTTP " + xhr.status));
    };

    xhr.onerror = function () {
      if (timedOut) return;
      clearTimeout(timer);
      callback(new Error("Error de red"));
    };

    xhr.send(body !== null && body !== undefined ? JSON.stringify(body) : null);
  }

  window.MiniPad = {
    get: function (url, callback) {
      xhrRequest("GET", url, null, callback);
    },

    post: function (url, data, callback) {
      xhrRequest("POST", url, data || {}, callback || function () {});
    },

    showStatus: function (elementId, message, kind) {
      var el = document.getElementById(elementId);
      if (!el) return;
      el.textContent = message || "";
      el.className = "page-status" + (kind ? " page-status-" + kind : "");
      el.style.display = message ? "block" : "none";
    },

    toggleImmersive: function (body, topbar) {
      var on = body.className.indexOf("immersive") === -1;
      if (on) {
        body.className = (body.className + " immersive").replace(/^\s+/, "");
        if (topbar) topbar.className = "topbar hidden";
      } else {
        body.className = body.className.replace(" immersive", "");
        if (topbar) topbar.className = "topbar";
      }
      window.scrollTo(0, 1);
    },

    bindHelp: function (buttonId, panelId) {
      var button = document.getElementById(buttonId);
      var panel = document.getElementById(panelId);
      if (!button || !panel) return;

      button.onclick = function (e) {
        e.preventDefault();
        panel.className = panel.className.indexOf("hidden") >= 0 ? "help-panel" : "help-panel hidden";
      };

      var closeBtn = panel.getElementsByClassName("help-close")[0];
      if (closeBtn) {
        closeBtn.onclick = function () {
          panel.className = "help-panel hidden";
        };
      }
    },
  };
})();
