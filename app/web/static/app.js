/* Minimal progressive enhancement (DD-17).
 *
 * Everything on these pages works without this file: filters are GET forms,
 * job state is server-rendered, and /healthz is a plain link. This only
 * removes manual refreshing.
 */
(function () {
  "use strict";

  function renderHealth() {
    var target = document.getElementById("health-items");
    if (!target) return;
    fetch("/healthz")
      .then(function (r) { return r.json(); })
      .then(function (report) {
        target.innerHTML = "";
        Object.keys(report).forEach(function (key) {
          var ok = report[key] === "ok";
          var el = document.createElement("span");
          el.className = "badge badge-" + (ok ? "succeeded" : "failed");
          el.setAttribute("data-testid", "health-item-" + key);
          el.textContent = key + ": " + report[key];
          target.appendChild(el);
        });
      })
      .catch(function () {
        target.textContent = "상태를 확인할 수 없습니다.";
      });
  }

  function setupAutoRefresh() {
    var toggle = document.getElementById("auto-refresh");
    if (!toggle) return;
    var timer = null;
    function start() {
      if (timer) return;
      timer = window.setInterval(function () { window.location.reload(); }, 5000);
    }
    function stop() {
      if (!timer) return;
      window.clearInterval(timer);
      timer = null;
    }
    toggle.addEventListener("change", function () {
      if (toggle.checked) { start(); } else { stop(); }
    });
    if (toggle.checked) start();
  }

  document.addEventListener("DOMContentLoaded", function () {
    renderHealth();
    setupAutoRefresh();
  });
})();
