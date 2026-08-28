// Service Worker da Lista de Mercado.
// Estratégia: network-first (sempre busca a versão mais nova quando online),
// caindo para o cache só quando a rede falhar de verdade — evita ficar preso
// numa versão antiga do app, mas garante que ele ainda abre sem internet.

var CACHE_NAME = 'lista-mercado-v1';
var PRECACHE_URLS = [
  './',
  './index.html',
  'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js'
];

self.addEventListener('install', function (event) {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return Promise.all(
        PRECACHE_URLS.map(function (url) {
          return fetch(url, { mode: 'no-cors' })
            .then(function (resp) { return cache.put(url, resp); })
            .catch(function () { /* segue sem essa entrada, tenta de novo depois */ });
        })
      );
    })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (key) { return key !== CACHE_NAME; })
            .map(function (key) { return caches.delete(key); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

function isPrecachedRequest(request) {
  if (request.mode === 'navigate') return true;
  return PRECACHE_URLS.indexOf(request.url) !== -1;
}

self.addEventListener('fetch', function (event) {
  var request = event.request;

  // Só cuida da página em si e da biblioteca do Supabase. Chamadas de API,
  // realtime (websocket) e qualquer outra coisa passam direto, sem cache.
  if (request.method !== 'GET' || !isPrecachedRequest(request)) return;

  event.respondWith(
    fetch(request).then(function (response) {
      var copy = response.clone();
      caches.open(CACHE_NAME).then(function (cache) {
        cache.put(request.mode === 'navigate' ? './index.html' : request, copy);
      });
      return response;
    }).catch(function () {
      return caches.match(request.mode === 'navigate' ? './index.html' : request);
    })
  );
});
