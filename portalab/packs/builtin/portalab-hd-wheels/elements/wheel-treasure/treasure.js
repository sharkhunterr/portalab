// « Treasure wheel HD » — the daily wheel's face (Portalab's sandbox, the region the wheel keeps for it: Portalab
// turns it, writes the amounts over it and says the result). Brushed gold, crimson lacquer inlaid with gold,
// emerald, obsidian, a diamond's rainbow fire for the gift, walnut for nothing; glints running over them, the
// winning slice catching the light once it stopped. Still for those who asked less motion.

const VERTEX = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
const FRAGMENT = `
precision highp float;
uniform vec2 u_res;
uniform float u_t, u_n, u_spin, u_win, u_pick;
uniform float u_tone[16];
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);vec2 u=f*f*(3.-2.*f);
  return mix(mix(hash(i),hash(i+vec2(1.,0.)),u.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),u.x),u.y);}
vec3 spectrum(float x){return .5+.5*cos(6.2831853*(x+vec3(0.,.33,.67)));}
void main(){
  vec2 uv=(gl_FragCoord.xy-.5*u_res)/(.5*min(u_res.x,u_res.y));
  float r=length(uv);
  if(r>1.){gl_FragColor=vec4(0.);return;}
  float TAU=6.2831853;
  float a=atan(uv.x,uv.y);
  if(a<0.)a+=TAU;
  float slice=TAU/u_n;
  float idx=floor(a/slice);
  float local=fract(a/slice);
  float k=5.;
  for(int i=0;i<16;i++){if(float(i)==idx)k=u_tone[i];}
  float mid=(idx+.5)*slice;
  // a light turning slowly around the treasure: where the facets and the metal catch it
  vec3 light=normalize(vec3(cos(u_t*.35),sin(u_t*.35),1.4));
  vec3 col;
  float shine=0.;
  if(k<.5){ // brushed gold
    float brush=noise(vec2(r*260.,a*3.))*.5+noise(vec2(r*90.,a*9.))*.5;
    vec3 n=normalize(vec3(sin(a-mid)*.6,(r-.6)*.8,1.));
    shine=pow(max(dot(n,light),0.),18.);
    col=mix(vec3(.62,.42,.1),vec3(1.,.82,.38),.45+.4*brush)+shine*vec3(1.,.95,.75);
  }else if(k<1.5){ // crimson lacquer, gold inlay
    float inlay=smoothstep(.012,.0,abs(fract(r*7.)-.5)*.14)*step(.25,r);
    col=mix(vec3(.24,.01,.04),vec3(.55,.04,.09),noise(uv*5.)*.6+.2);
    shine=pow(max(dot(normalize(vec3(uv*.5,1.)),light),0.),40.);
    col=mix(col,vec3(.95,.75,.3),inlay)+shine*.6;
  }else if(k<2.5){ // obsidian, silver veins
    float vein=smoothstep(.04,.0,abs(noise(uv*6.+idx)-.5));
    col=vec3(.035,.035,.05)+vein*vec3(.55,.58,.65)*.6;
    shine=pow(max(dot(normalize(vec3(uv*.8,1.)),light),0.),60.);
    col+=shine*.8;
  }else if(k<3.5){ // emerald, cut in facets
    vec2 f=vec2(floor(r*5.),floor((a-idx*slice)/slice*3.));
    vec3 n=normalize(vec3(hash(f)-.5,hash(f+7.)-.5,1.1));
    shine=pow(max(dot(n,light),0.),12.);
    col=mix(vec3(.0,.22,.12),vec3(.1,.72,.42),.35+.65*shine)+shine*vec3(.6,1.,.8)*.6;
  }else if(k<4.5){ // a diamond: rainbow fire in its facets
    vec2 f=vec2(floor(r*7.),floor((a-idx*slice)/slice*5.));
    vec3 n=normalize(vec3(hash(f)-.5,hash(f+3.)-.5,.9));
    shine=pow(max(dot(n,light),0.),8.);
    col=mix(vec3(.72,.78,.86),vec3(1.),shine)+spectrum(hash(f)+u_t*.08+r)*shine*.7;
  }else{ // walnut
    float grain=noise(vec2(r*40.,a*2.+noise(uv*3.)*2.));
    col=mix(vec3(.17,.08,.03),vec3(.36,.19,.08),grain);
  }
  // glints running over it
  vec2 g=uv*22.;vec2 c=floor(g);float h=hash(c+idx*7.);
  float glint=step(.93,h)*smoothstep(.25,.0,length(fract(g)-.5))*pow(max(0.,sin(u_t*1.7+h*60.)),24.);
  col+=vec3(1.,.95,.8)*glint*1.6;
  // light flying over it while it turns
  col+=vec3(1.,.9,.6)*u_spin*.35*pow(noise(vec2(a*60.,r*2.)),4.);
  // the winning slice catches the light
  if(abs(idx-u_pick)<.5)col+=vec3(1.,.85,.45)*u_win*(.28+.18*sin(u_t*4.))*smoothstep(.2,.95,r);
  // gold filets between slices and around the face
  float edge=min(local,1.-local)*slice*r;
  float filet=smoothstep(.016,.006,edge)+smoothstep(.02,.0,abs(r-.94))+smoothstep(.015,.0,abs(r-.3));
  col=mix(col,vec3(1.,.83,.4)+shine*.3,clamp(filet,0.,1.));
  float alpha=smoothstep(1.,.985,r);
  gl_FragColor=vec4(col*alpha,alpha);
}`;

const TONE = (segment, index) =>
  segment.kind === "coins" ? (segment.amount < 0 ? 2 : index % 2) : { xp: 3, product: 4 }[segment.kind] ?? 5;

export default function mount(root, api) {
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "position:absolute;inset:0;width:100%;height:100%;border-radius:50%";
  root.append(canvas);
  const gl = canvas.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: true });
  if (!gl) throw new Error("no WebGL");
  const shader = (type, source) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) || "shader");
    return s;
  };
  const program = gl.createProgram();
  gl.attachShader(program, shader(gl.VERTEX_SHADER, VERTEX));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FRAGMENT));
  gl.linkProgram(program);
  gl.useProgram(program);
  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
  const u = (name) => gl.getUniformLocation(program, name);
  const at = { res: u("u_res"), t: u("u_t"), n: u("u_n"), spin: u("u_spin"), win: u("u_win"), pick: u("u_pick"), tone: u("u_tone") };

  let context = api.context;
  let phase = context.stage?.phase ?? "idle";
  let since = performance.now();
  let frame = 0;
  const stop = api.onContext((next) => {
    const nextPhase = next.stage?.phase ?? "idle";
    if (nextPhase !== phase) {
      phase = nextPhase;
      since = performance.now();
    }
    context = next;
    start();
  });

  const draw = (now) => {
    const box = root.getBoundingClientRect();
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const w = Math.max(1, Math.round(box.width * ratio));
    const h = Math.max(1, Math.round(box.height * ratio));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    gl.viewport(0, 0, w, h);
    const data = context.widget?.data ?? {};
    const segments = Array.isArray(data.segments) ? data.segments : [];
    const tones = new Float32Array(16).fill(5);
    segments.slice(0, 16).forEach((segment, index) => {
      tones[index] = TONE(segment, index);
    });
    const still = Boolean(context.reducedMotion);
    const elapsed = now - since;
    const spinMs = context.stage?.spin_ms || 5200;
    const spin = phase === "spinning" ? Math.min(1, elapsed / 400) * Math.max(0, 1 - elapsed / spinMs) ** 0.6 : 0;
    const win = phase === "done" ? 0.35 + 0.65 * Math.max(0, 1 - elapsed / 4000) : 0;
    gl.uniform2f(at.res, w, h);
    gl.uniform1f(at.t, still ? 8 : now / 1000);
    gl.uniform1f(at.n, Math.max(1, segments.length));
    gl.uniform1f(at.spin, still ? 0 : spin);
    gl.uniform1f(at.win, win);
    gl.uniform1f(at.pick, data.today?.index ?? -1);
    gl.uniform1fv(at.tone, tones);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (!still) frame = requestAnimationFrame(draw);
  };
  const start = () => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(draw);
  };
  start();
  return () => {
    cancelAnimationFrame(frame);
    stop();
  };
}
