self.addEventListener("install", (event) => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    event.waitUntil(clients.claim());
});

self.addEventListener("push", function(event) {
    let data = {};

    try {
        data = event.data.json();
    } catch (e) {
        data = {
            title: "JZ Elektro",
            body: "Nová notifikace"
        };
    }

    const title = data.title || "JZ Elektro";
    const options = {
        body: data.body || "",
        icon: "/static/icons/icon-192.png",
        badge: "/static/icons/icon-192.png",
        vibrate: [200, 100, 200],
        data: {
            url: data.url || "/"
        }
    };

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener("notificationclick", function(event) {
    event.notification.close();

    const targetUrl = event.notification.data.url || "/";

    event.waitUntil(
        clients.matchAll({
            type: "window",
            includeUncontrolled: true
        }).then(function(clientList) {

            for (const client of clientList) {
                if ("focus" in client) {
                    client.navigate(targetUrl);
                    return client.focus();
                }
            }

            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
