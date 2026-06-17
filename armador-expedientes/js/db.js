/* Armador de Expedientes — Almacenamiento local (IndexedDB)
 *
 * Todo se guarda en el navegador del propio equipo: no hay servidor ni se envía
 * nada a internet. Los PDF se guardan como bytes en el almacén `blobs`.
 */
(function (global) {
  'use strict';

  const NOMBRE_DB = 'armador_expedientes';
  const VERSION = 1;
  const STORES = ['archivos', 'plantillas', 'expedientes', 'blobs'];
  let _db = null;

  function abrir() {
    return new Promise(function (resolve, reject) {
      if (_db) return resolve(_db);
      if (!global.indexedDB) {
        return reject(new Error('Este navegador no soporta almacenamiento local (IndexedDB).'));
      }
      const req = global.indexedDB.open(NOMBRE_DB, VERSION);
      req.onupgradeneeded = function (e) {
        const db = e.target.result;
        STORES.forEach(function (s) {
          if (!db.objectStoreNames.contains(s)) db.createObjectStore(s, { keyPath: 'id' });
        });
      };
      req.onsuccess = function () { _db = req.result; resolve(_db); };
      req.onerror = function () { reject(req.error); };
    });
  }

  function _almacen(store, modo) {
    return _db.transaction(store, modo).objectStore(store);
  }

  function _wrap(req) {
    return new Promise(function (res, rej) {
      req.onsuccess = function () { res(req.result); };
      req.onerror = function () { rej(req.error); };
    });
  }

  async function put(store, obj) { await abrir(); return _wrap(_almacen(store, 'readwrite').put(obj)); }
  async function get(store, id) { await abrir(); return _wrap(_almacen(store, 'readonly').get(id)); }
  async function getAll(store) { await abrir(); return _wrap(_almacen(store, 'readonly').getAll()); }
  async function del(store, id) { await abrir(); return _wrap(_almacen(store, 'readwrite').delete(id)); }
  async function clear(store) { await abrir(); return _wrap(_almacen(store, 'readwrite').clear()); }

  async function putBlob(id, datos) { return put('blobs', { id: id, datos: datos }); }
  async function getBlob(id) { const r = await get('blobs', id); return r ? r.datos : null; }
  async function delBlob(id) { return del('blobs', id); }

  global.DB = {
    abrir: abrir, put: put, get: get, getAll: getAll, del: del, clear: clear,
    putBlob: putBlob, getBlob: getBlob, delBlob: delBlob, STORES: STORES
  };
})(window);
