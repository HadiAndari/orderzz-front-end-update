self.addEventListener('message', (event) => {
  console.log(event.data , event.data.type === 'SKIP_WAITING')
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

importScripts("https://www.gstatic.com/firebasejs/8.2.0/firebase-app.js");
importScripts("https://www.gstatic.com/firebasejs/8.2.0/firebase-messaging.js");
var firebaseConfig = {
  apiKey: "AIzaSyAewjnBU4cU-rRq6YQX8aQVsy1FAJPnDuw",
  authDomain: "orderzz.firebaseapp.com",
  projectId: "orderzz",
  storageBucket: "orderzz.appspot.com",
  messagingSenderId: "556020953858",
  appId: "1:556020953858:web:4d04ff8d23565c0307c81b",
  measurementId: "G-SY6EBR7DQQ"
};
firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();
messaging.onBackgroundMessage(function (payload) {
  const notificationTitle = payload.data.title || "";
  const notificationOptions = {
    body: payload.data.body || "",
    lang: payload.data.language,
    dir: payload.data.language === "ar" ? 'rtl' : "ltr",
    ...(payload.data.badge ? { badge: payload.data.badge } : {}),
    ...(payload.data.icon ? { icon: payload.data.icon } : {}),
    ...(payload.data.image ? { image: payload.data.image } : {}),
    ...(payload.data.sound ? { sound: payload.data.sound } : {}),
    ...(payload.data.vibrate
      ? { vibrate: JSON.parse(payload.data.vibrate) }
      : {}),

    ...(payload.data.actions
      ? { actions: JSON.parse(payload.data.actions) }
      : {}),
    ...(payload.data.data ? { data: JSON.parse(payload.data.data) } : {}),

    ...(payload.data.tag ? { tag: payload.data.tag } : {}),
    ...(payload.data.requireInteraction
      ? { requireInteraction: payload.data.requireInteraction }
      : {}),
    ...(payload.data.renotify ? { renotify: payload.data.renotify } : {}),
    ...(payload.data.silent ? { silent: payload.data.silent } : {}),

    ...(payload.data.timestamp
      ? { timestamp: Date.parse(payload.data.timestamp) }
      : {}),
  };
  self.registration.showNotification(notificationTitle, notificationOptions);
});
