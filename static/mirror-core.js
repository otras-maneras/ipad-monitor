(function () {
  "use strict";

  var FIT_BADGE_LABELS = {
    fit: "Ver todo",
    fill: "Llenar",
    stretch: "Estirar"
  };

  var FIT_CYCLE_ORDER = ["fit", "fill", "stretch"];

  function initMirror(config) {
    config = config || {};
    var kiosk = !!config.kiosk;
    var mirror = document.getElementById(config.mirrorId || "mirror");
    var statusEl = document.getElementById(config.statusId || "mirror-status");
    var fpsLabel = config.fpsId ? document.getElementById(config.fpsId) : null;
    var fitMenu = config.fitMenuId ? document.getElementById(config.fitMenuId) : null;
    var badgeEl = config.badgeId ? document.getElementById(config.badgeId) : null;
    var pollMs = kiosk ? 100 : 150;
    var errorThreshold = kiosk ? 1 : 3;
    var touchEnabled = config.touchEnabled !== false;

    var lastSeq = -1;
    var lastConfigVersion = -1;
    var lastLoadedVersion = -1;
    var currentFitMode = "";
    var frames = 0;
    var startedAt = Date.now();
    var busy = false;
    var busyTimer = null;
    var gotFrame = false;
    var pollErrors = 0;
    var reconnectAttempt = 0;
    var badgeTimer = null;

    function setStatus(text, visible) {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.style.display = visible === false ? "none" : "block";
    }

    function updateStatus() {
      if (!fpsLabel) return;
      var elapsed = Math.max((Date.now() - startedAt) / 1000, 0.1);
      fpsLabel.textContent = Math.round((frames / elapsed) * 10) / 10 + " fps";
    }

    function clearBusy() {
      busy = false;
      if (busyTimer) {
        clearTimeout(busyTimer);
        busyTimer = null;
      }
    }

    function updateFitButtons(mode) {
      currentFitMode = mode || currentFitMode;
      var buttons = document.querySelectorAll(".fit-btn");
      for (var i = 0; i < buttons.length; i++) {
        var btn = buttons[i];
        if (btn.getAttribute("data-fit") === currentFitMode) {
          btn.className = "fit-btn fit-btn-active";
        } else {
          btn.className = "fit-btn";
        }
      }
      updateImageClass(currentFitMode);
    }

    function updateImageClass(mode) {
      if (!mirror) return;
      mirror.className = "mirror-img mirror-img-" + (mode || "fit");
    }

    function showBadge(mode) {
      if (!badgeEl) return;
      badgeEl.textContent = FIT_BADGE_LABELS[mode] || mode;
      badgeEl.className = "kiosk-fit-badge show";
      if (badgeTimer) clearTimeout(badgeTimer);
      badgeTimer = setTimeout(function () {
        badgeEl.className = "kiosk-fit-badge";
      }, 1500);
    }

    function cycleFitMode() {
      var nextIndex = 0;
      for (var i = 0; i < FIT_CYCLE_ORDER.length; i++) {
        if (FIT_CYCLE_ORDER[i] === currentFitMode) {
          nextIndex = (i + 1) % FIT_CYCLE_ORDER.length;
          break;
        }
      }
      var nextMode = FIT_CYCLE_ORDER[nextIndex];
      MiniPad.post("/api/fit/" + nextMode, {}, function (err, res) {
        if (err) return;
        var applied = (res && res.fit_mode) || nextMode;
        currentFitMode = applied;
        updateFitButtons(applied);
        showBadge(applied);
        forceReload();
      });
    }

    function forceReload() {
      lastSeq = -1;
      lastLoadedVersion = -1;
      pollMeta();
    }

    function showFrame(seq, version) {
      if (!mirror || busy) return;
      busy = true;

      var url = "/snapshot.jpg?s=" + seq + "&v=" + version + "&t=" + Date.now();

      mirror.onload = function () {
        clearBusy();
        gotFrame = true;
        reconnectAttempt = 0;
        frames += 1;
        updateStatus();
        setStatus("", false);
      };

      mirror.onerror = function () {
        clearBusy();
        lastSeq = -1;
        setStatus(kiosk ? "Reconectando…" : "Error cargando imagen. Reintentando…", true);
      };

      busyTimer = setTimeout(function () {
        if (busy) {
          clearBusy();
          lastSeq = -1;
        }
      }, kiosk ? 3000 : 4000);

      mirror.src = url;
    }

    function pollMeta() {
      MiniPad.get("/api/frame", function (err, info) {
        if (err || !info) {
          pollErrors += 1;
          reconnectAttempt += 1;
          if (!gotFrame || pollErrors > errorThreshold) {
            var msg = kiosk
              ? "Reconectando… (" + reconnectAttempt + ")"
              : "Sin conexión con el PC. ¿Está corriendo iPad Monitor?";
            setStatus(msg, true);
          }
          return;
        }

        pollErrors = 0;

        if (info.fit_mode) {
          updateFitButtons(info.fit_mode);
        }

        if (typeof info.seq !== "number") {
          setStatus(kiosk ? "Esperando PC…" : "Esperando servidor…", true);
          return;
        }

        if (!info.bytes || info.bytes <= 0) {
          setStatus(kiosk ? "Esperando señal…" : "Esperando captura de pantalla…", true);
          return;
        }

        if (info.config_version !== lastConfigVersion) {
          lastConfigVersion = info.config_version;
          lastSeq = -1;
          lastLoadedVersion = -1;
        }

        if (info.seq !== lastSeq || info.config_version !== lastLoadedVersion || !gotFrame) {
          lastSeq = info.seq;
          lastLoadedVersion = info.config_version || 0;
          showFrame(info.seq, info.config_version || 0);
        }
      });
    }

    if (kiosk) {
      var fitZone = document.getElementById("kiosk-fit-zone");
      var fitTapCount = 0;
      var fitTapTimer = null;
      if (fitZone) {
        fitZone.onclick = function () {
          fitTapCount += 1;
          if (fitTapTimer) clearTimeout(fitTapTimer);
          fitTapTimer = setTimeout(function () {
            fitTapCount = 0;
          }, 900);
          if (fitTapCount >= 3) {
            fitTapCount = 0;
            cycleFitMode();
          }
        };
      }
    }

    if (!kiosk && config.fitBtnId && fitMenu) {
      var fitBtn = document.getElementById(config.fitBtnId);
      if (fitBtn) {
        fitBtn.onclick = function (e) {
          e.preventDefault();
          fitMenu.className = fitMenu.className.indexOf("hidden") >= 0 ? "fit-menu" : "fit-menu hidden";
        };
      }

      var fitButtons = document.querySelectorAll(".fit-btn");
      for (var i = 0; i < fitButtons.length; i++) {
        fitButtons[i].onclick = (function (mode) {
          return function () {
            MiniPad.post("/api/fit/" + mode, {}, function (err, res) {
              if (err) return;
              fitMenu.className = "fit-menu hidden";
              updateFitButtons((res && res.fit_mode) || mode);
              forceReload();
            });
          };
        })(fitButtons[i].getAttribute("data-fit"));
      }
    }

    if (touchEnabled && mirror) {
      var touchStartX = 0;
      var touchStartY = 0;
      var touchStartTime = 0;
      var touchMoved = false;
      var longPressTimer = null;
      var lastTapTime = 0;
      var TAP_TIMEOUT_MS = 250;
      var LONG_PRESS_MS = 500;
      var MOVE_THRESHOLD = 6;

      function getRelativePos(e) {
        var rect = mirror.getBoundingClientRect();
        var clientX = e.clientX;
        var clientY = e.clientY;
        return {
          x: Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)),
          y: Math.max(0, Math.min(1, (clientY - rect.top) / rect.height))
        };
      }

      function sendMoveTo(e) {
        var pos = getRelativePos(e);
        MiniPad.post("/api/pointer/move-to", { x: pos.x, y: pos.y }, function () {});
      }

      function sendClick(button) {
        MiniPad.post("/api/pointer/click", { button: button || "left" }, function () {});
      }

      function startLongPress(e) {
        if (longPressTimer) clearTimeout(longPressTimer);
        longPressTimer = setTimeout(function () {
          if (!touchMoved) {
            sendMoveTo(e);
            sendClick("right");
            touchMoved = true; // evitar que también se envíe clic izquierdo
          }
        }, LONG_PRESS_MS);
      }

      mirror.addEventListener("touchstart", function (e) {
        if (e.touches.length !== 1) return;
        e.preventDefault();
        var touch = e.touches[0];
        touchStartX = touch.clientX;
        touchStartY = touch.clientY;
        touchStartTime = Date.now();
        touchMoved = false;
        startLongPress(touch);
      }, false);

      mirror.addEventListener("touchmove", function (e) {
        if (e.touches.length !== 1) return;
        var touch = e.touches[0];
        if (Math.abs(touch.clientX - touchStartX) > MOVE_THRESHOLD ||
            Math.abs(touch.clientY - touchStartY) > MOVE_THRESHOLD) {
          touchMoved = true;
          if (longPressTimer) clearTimeout(longPressTimer);
        }
      }, false);

      mirror.addEventListener("touchend", function (e) {
        if (longPressTimer) clearTimeout(longPressTimer);
        var touch = e.changedTouches[0];
        var elapsed = Date.now() - touchStartTime;

        if (touchMoved || elapsed > LONG_PRESS_MS) return;

        sendMoveTo(touch);

        var now = Date.now();
        if (now - lastTapTime < TAP_TIMEOUT_MS) {
          // doble clic
          sendClick("left");
          setTimeout(function () { sendClick("left"); }, 80);
        } else {
          sendClick("left");
        }
        lastTapTime = now;
      }, false);
    }

    pollMeta();
    setInterval(pollMeta, pollMs);

    return {
      forceReload: forceReload,
    };
  }

  window.MiniPadMirror = {
    init: initMirror,
  };
})();
