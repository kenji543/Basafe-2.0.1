(() => {
  "use strict";

  const offlineBanner = document.getElementById("offline-banner");
  const installButtons = [...document.querySelectorAll("[data-install]")];
  let installEvent = null;

  const updateConnectivity = () => {
    if (offlineBanner) offlineBanner.hidden = navigator.onLine;
    document.documentElement.dataset.connectivity = navigator.onLine ? "online" : "offline";
  };

  window.addEventListener("online", updateConnectivity);
  window.addEventListener("offline", updateConnectivity);
  updateConnectivity();

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installEvent = event;
    installButtons.forEach((button) => { button.hidden = false; });
  });

  installButtons.forEach((button) => button.addEventListener("click", async () => {
    if (!installEvent) {
      alert("On iPhone or iPad, open the Share menu and choose 'Add to Home Screen'. New scoring requests still require current source access.");
      return;
    }
    installEvent.prompt();
    await installEvent.userChoice;
    installEvent = null;
    installButtons.forEach((item) => { item.hidden = true; });
  }));

  window.addEventListener("appinstalled", () => {
    installButtons.forEach((button) => { button.hidden = true; });
  });

  if ("serviceWorker" in navigator) {
    document.addEventListener("geosafe:update-available", () => {
      if (document.getElementById("pwa-update-notice")) return;
      const notice = document.createElement("div");
      notice.id = "pwa-update-notice";
      notice.className = "offline-banner update-notice";
      notice.setAttribute("role", "status");
      notice.innerHTML = '<span>Basafe update ready.</span><div class="update-actions"><button type="button" data-update-refresh>Refresh</button><button type="button" class="update-later" data-update-later>Later</button></div>';
      notice.querySelector("[data-update-refresh]").addEventListener("click", () => window.location.reload());
      notice.querySelector("[data-update-later]").addEventListener("click", () => notice.remove());
      document.body.appendChild(notice);
    });

    window.addEventListener("load", async () => {
      try {
        const registration = await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
        registration.addEventListener("updatefound", () => {
          const worker = registration.installing;
          worker?.addEventListener("statechange", () => {
            if (worker.state === "installed" && navigator.serviceWorker.controller) {
              document.dispatchEvent(new CustomEvent("geosafe:update-available"));
            }
          });
        });
      } catch (error) {
        console.warn("Basafe offline shell could not be registered.", error);
      }
    });
  }
})();
