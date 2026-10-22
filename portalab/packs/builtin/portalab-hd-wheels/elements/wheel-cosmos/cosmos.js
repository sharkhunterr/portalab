// « Cosmic wheel HD » — the daily wheel's face (Portalab's sandbox, the region the wheel keeps for it: Portalab
// turns it, writes the amounts over it and says the result). Each slice a nebula of its tone, stars, light
// streaking while it turns, the winning slice glowing once it stopped. Still for those who asked less motion.

const VERTEX = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
const FRAGMENT = `
precision highp float;
uniform vec2 u_res;
uniform float u_t, u_n, u_spin, u_win, u_pick;
uniform float u_tone[16];
float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float noise(vec2 p){vec2 i=floor(p),f=fract(p);vec2 u=f*f*(3.-2.*f);
  return mix(mix(hash(i),hash(i+vec2(1.,0.)),u.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.,1.)),u.x),u.y);}
float fbm(vec2 p){float v=0.,a=.5;for(int i=0;i<5;i++){v+=a*noise(p);p=p*2.03+vec2(1.7,9.2);a*=.5;}return v;}
void tone(float k,out vec3 deep,out vec3 hi){
  if(k<.5){deep=vec3(.32,.08,.62);hi=vec3(.98,.42,.86);}
  else if(k<1.5){deep=vec3(.05,.14,.55);hi=vec3(.35,.9,1.);}
  else if(k<2.5){deep=vec3(.42,.02,.08);hi=vec3(1.,.42,.18);}
  else if(k<3.5){deep=vec3(.01,.32,.3);hi=vec3(.5,1.,.78);}
  else if(k<4.5){deep=vec3(.55,.32,.04);hi=vec3(1.,.93,.62);}
  else{deep=vec3(.015,.015,.04);hi=vec3(.22,.22,.38);}
}
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
  vec3 deep,hi;tone(k,deep,hi);
  vec2 q=vec2(a*2.2+u_t*.04,r*3.5-u_t*.05);
  float n=fbm(q+fbm(uv*2.6+vec2(u_t*.02,-u_t*.03)+idx*3.1)*1.6);
  vec3 col=mix(deep*.35,deep,smoothstep(.2,.6,n));
  col=mix(col,hi,smoothstep(.55,.95,n)*.85);
  // dust lanes
  col*=.75+.35*smoothstep(.3,.7,fbm(uv*7.+idx));
  // stars
  vec2 g=uv*38.;vec2 c=floor(g);float h=hash(c+idx);
  float star=step(.965,h)*smoothstep(.32,.0,length(fract(g)-.5))*(.6+.4*sin(u_t*2.5+h*40.));
  col+=vec3(.95,.95,1.)*star*1.3;
  // a supernova in the gift's slice
  if(k>3.5&&k<4.5){float d=length(uv-vec2(sin((idx+.5)*slice),cos((idx+.5)*slice))*.62);
    col+=hi*(.09/(d*d*14.+.09))*(.85+.15*sin(u_t*3.));}
  // light streaking while it turns
  col+=hi*u_spin*.55*pow(noise(vec2(a*70.,r*3.)),3.)*r;
  col=mix(col,col*.7+deep*.3,u_spin*.4);
  // the winning slice
  if(abs(idx-u_pick)<.5)col+=hi*u_win*(.35+.25*sin(u_t*5.))*smoothstep(.15,.9,r);
  // starlight between slices, the rim's glow
  float edge=min(local,1.-local)*slice*r;
  col+=vec3(.85,.9,1.)*smoothstep(.012,.0,edge)*.9;
  col+=hi*smoothstep(.9,1.,r)*.45;
  col*=smoothstep(.0,.25,r)*.8+.2;
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
    const win = phase === "done" ? 0.3 + 0.7 * Math.max(0, 1 - elapsed / 4000) : 0;
    gl.uniform2f(at.res, w, h);
    gl.uniform1f(at.t, still ? 12 : now / 1000);
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
