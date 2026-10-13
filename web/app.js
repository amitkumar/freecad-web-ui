import * as THREE from '/vendor/three.module.js';

const $ = id => document.getElementById(id);
const token = new URLSearchParams(location.hash.slice(1)).get('token') || sessionStorage.getItem('freecad-session-token');
if (token) sessionStorage.setItem('freecad-session-token', token);
// Remove the authorization token from the visible URL and browser history entry.
if (location.hash) history.replaceState(null, '', location.pathname);
let state = null, busy = false, editing = false, available = false;
const message = (text, error = false) => { $('message').textContent = text; $('message').classList.toggle('error', error); };
function connection(ok) {
  available = ok;
  $('dot').classList.toggle('connected', ok);
  $('connection').textContent = ok ? 'Connected to FreeCAD' : 'FreeCAD disconnected';
  $('length').disabled = !ok || busy;
  $('apply').disabled = !ok || busy;
  $('save').disabled = !ok || busy || !state || state.saved;
}
async function api(path, body) {
  const response = await fetch(path, {method: body ? 'POST' : 'GET', headers: {'Authorization': `Bearer ${token || ''}`, ...(body ? {'Content-Type': 'application/json'} : {})}, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(12000)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}

const canvas = $('viewport');
let renderer;
try { renderer = new THREE.WebGLRenderer({canvas, antialias:true, alpha:true}); }
catch { message('WebGL is unavailable in this browser. Enable hardware acceleration or try another browser.', true); }
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 20000);
camera.up.set(0, 0, 1);
scene.add(new THREE.HemisphereLight(0xfff9e7, 0x8d9881, 2.8));
const key = new THREE.DirectionalLight(0xfff4df, 3); key.position.set(200, -300, 500); scene.add(key);
const fill = new THREE.DirectionalLight(0xffffff, 1.2); fill.position.set(-300, 200, 100); scene.add(fill);
const grid = new THREE.GridHelper(2000, 80, 0xc8d0bf, 0xdce2d2); grid.rotation.x = Math.PI/2; scene.add(grid);
let board, edges, meshRevision = null, meshSession = null, radius = 740, theta = -1.05, phi = 0.85, dragging = false, last = [0,0];
const target = new THREE.Vector3(0, 0, 0);
function cameraUpdate() { camera.position.set(target.x+radius*Math.sin(phi)*Math.cos(theta),target.y+radius*Math.sin(phi)*Math.sin(theta),target.z+radius*Math.cos(phi)); camera.lookAt(target); }
function fit() { if (!state) return; radius = Math.max(state.dimensionsMm.length,state.dimensionsMm.width)*2.2; cameraUpdate(); }
function updateMesh(next) {
  if (meshRevision === next.revision && meshSession === next.session) return;
  meshRevision = next.revision; meshSession = next.session;
  for (const old of [board, edges]) if (old) { scene.remove(old); old.geometry.dispose(); old.material.dispose(); }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(next.mesh.vertices, 3));
  geometry.setIndex(next.mesh.indices); geometry.computeVertexNormals(); geometry.computeBoundingBox();
  const center = geometry.boundingBox.getCenter(new THREE.Vector3()); geometry.translate(-center.x, -center.y, -center.z);
  board = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({color:0xc49b67,roughness:0.72,metalness:0})); scene.add(board);
  edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry),new THREE.LineBasicMaterial({color:0x886843,transparent:true,opacity:.55})); scene.add(edges);
  grid.position.z = -next.dimensionsMm.height/2 - 0.5;
}
function renderState(next) {
  const refit = state === null || state.dimensionsMm.length !== next.dimensionsMm.length;
  state = next; updateMesh(next);
  const dims = next.dimensionsMm;
  if (!editing) $('length').value = Number((dims.length/25.4).toFixed(4));
  $('length-mm').textContent = `${Number(dims.length.toFixed(3))} mm`;
  $('width').textContent = `${Number((dims.width/25.4).toFixed(3))} in`;
  $('height').textContent = `${Number((dims.height/25.4).toFixed(3))} in`;
  $('saved').textContent = next.saved ? 'Saved in FreeCAD' : 'Unsaved change';
  $('save-dot').classList.toggle('saved',next.saved);
  $('model-revision').textContent = `REV ${String(next.revision).padStart(3,'0')} · ${next.object}`;
  $('version').textContent = `FreeCAD ${next.freecadVersion} · dimensions in millimeters internally.`;
  $('file').textContent = next.modelFile;
  connection(true);
  if (refit) fit();
}
let editBase = null;
$('length').addEventListener('focus', () => {editing = true; if (!editBase && state) editBase = {session:state.session, revision:state.revision};});
$('length').addEventListener('input', () => { if (!editBase && state) editBase = {session:state.session, revision:state.revision}; });
// Preserve the draft across blur so a polling response cannot replace it before Apply.
async function command(operation) {
  if (!state || busy || !available) return;
  const base = operation === 'set_length' && editBase ? editBase : state;
  const body = {operation,session:base.session,revision:base.revision,requestId:crypto.randomUUID()};
  if (operation === 'set_length') body.lengthMm = Number($('length').value)*25.4;
  busy = true; connection(true); message(operation === 'save' ? 'Saving the sample model in FreeCAD…' : 'Applying length in FreeCAD…');
  try {
    const next = await api('/api/command',body); editing = false; editBase = null; renderState(next);
    message(operation === 'save' ? 'Saved. The FCStd file now contains this board geometry.' : 'Length updated in FreeCAD. Save when you want to keep this change.');
  } catch (error) {
    message(error.message,true); editing = false; editBase = null;
    try { renderState(await api('/api/snapshot')); } catch { connection(false); }
  } finally { busy = false; connection(available); }
}
$('length-form').addEventListener('submit',event => {event.preventDefault(); command('set_length');});
$('save').addEventListener('click',() => command('save'));
$('reset').addEventListener('click',()=> {theta=-1.05;phi=.85;fit();});
$('top').addEventListener('click',()=> {phi=.001;theta=-Math.PI/2;fit();});
$('fit').addEventListener('click',fit);
canvas.addEventListener('pointerdown',event=> {dragging=true;last=[event.clientX,event.clientY];canvas.setPointerCapture(event.pointerId);});
canvas.addEventListener('pointermove',event=> {if(!dragging)return;theta-=(event.clientX-last[0])*.007;phi=Math.max(.02,Math.min(Math.PI-.02,phi+(event.clientY-last[1])*.007));last=[event.clientX,event.clientY];cameraUpdate();});
canvas.addEventListener('pointerup',()=> {dragging=false;});
canvas.addEventListener('pointercancel',()=> {dragging=false;});
canvas.addEventListener('wheel',event=> {event.preventDefault();radius=Math.max(50,Math.min(15000,radius*Math.exp(event.deltaY*.001)));cameraUpdate();},{passive:false});
if (renderer) {
  renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  new ResizeObserver(()=> {const {width,height}=canvas.getBoundingClientRect();renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();}).observe(canvas);
  cameraUpdate(); renderer.setAnimationLoop(()=> renderer.render(scene,camera));
}
async function poll() {
  if (!token) {connection(false);message('Run StartWebUI.FCMacro in FreeCAD and open its authorized viewer link.',true);return;}
  if (!busy) {
    try {const wasConnected=available;const next=await api('/api/snapshot');if(!busy && (!state || next.session!==state.session || next.revision>=state.revision)){renderState(next);if(!wasConnected)message('Live geometry received from FreeCAD. Change the length to try the connection.');}}
    catch(error){connection(false);message(error.message,true);}
  }
  setTimeout(poll,1000);
}
poll();
