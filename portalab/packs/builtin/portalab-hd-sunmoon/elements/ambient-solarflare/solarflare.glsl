// Portalab — ambient/solarflare: the « solarflare » ambience (spec 028, B2)
float fbm4(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = turn * p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}
// thin bright filaments: the creases of a noise, sharpened octave after octave
float ridged(vec2 p) {
  float v = 0.0;
  float a = 0.55;
  float prev = 1.0;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 5; i++) {
    float n = 1.0 - abs(2.0 * noise(p) - 1.0);
    n = n * n;
    v += n * a * prev;
    prev = n;
    p = turn * p * 2.1 + vec2(3.1, 7.7);
    a *= 0.5;
  }
  return v;
}
float starfield(vec2 p, float scale, float t, float density) {
  vec2 sg = p * scale;
  vec2 id = floor(sg);
  float h = hash(id);
  vec2 at = vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5;
  float s = step(1.0 - density, h) * smoothstep(0.12 + 0.1 * hash(id + 1.3), 0.0, length(fract(sg) - 0.5 - at * 0.6));
  return s * (0.55 + 0.45 * sin(t * (1.0 + 2.0 * hash(id + 5.0)) + h * 40.0));
}
// a star seen by a great telescope: a bright core, a halo and six diffraction spikes (two short ones across)
float spiked(vec2 d, float size) {
  float r = length(d);
  float core = exp(-r / size * 3.2) + exp(-r / size * 0.9) * 0.18;
  float spikes = 0.0;
  for (int i = 0; i < 3; i++) {
    float a = float(i) * 1.0472 + 1.5708;
    vec2 dir = vec2(cos(a), sin(a));
    float along = abs(dot(d, dir));
    float across = abs(dot(d, vec2(-dir.y, dir.x)));
    spikes += exp(-across / size * 9.0) * exp(-along / size * 0.55);
  }
  spikes += 0.5 * exp(-abs(d.y) / size * 9.0) * exp(-abs(d.x) / size * 1.1);
  return core + spikes * 0.55;
}
// a few big stars with their spikes, slowly twinkling, coloured blue-white to gold
vec4 brightStars(vec4 o, vec2 p, float aspect, float t, float seed, float count) {
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    if (fi >= count) break;
    vec2 at = vec2(hash(vec2(fi, seed)) * aspect, 0.08 + hash(vec2(fi, seed + 1.0)) * 0.86);
    float size = 0.006 + 0.008 * hash(vec2(fi, seed + 2.0));
    float tw = 0.75 + 0.25 * sin(t * (0.7 + hash(vec2(fi, seed + 3.0))) + fi * 2.0);
    vec3 col = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.88, 0.7), hash(vec2(fi, seed + 4.0)));
    o = over(o, col, clamp(spiked(p - at, size) * tw, 0.0, 1.0));
  }
  return o;
}

void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec2 ctr = vec2(1.05 * aspect, -0.25);
  float R = 0.85;
  vec2 c = p - ctr;
  float r = length(c);
  float ang = atan(c.y, c.x);
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 80.0, t, 0.02) * smoothstep(R + 0.3, R + 0.6, r));
  // the corona, streaming
  float streams = fbm4(vec2(ang * 6.0, r * 2.0 - t * 0.05));
  o = over(o, vec3(1.0, 0.6, 0.2), exp(-(r - R) * 4.0) * step(R, r) * (0.35 + 0.35 * streams));
  // prominences: arcs of plasma rising off the limb and falling back
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float a0 = 1.75 + fi * 0.32 + 0.05 * sin(t * 0.1 + fi);
    float span = 0.18 + 0.08 * hash(vec2(fi, 3.0));
    float h = (0.12 + 0.12 * hash(vec2(fi, 4.0))) * (0.75 + 0.25 * sin(t * 0.2 + fi * 2.0));
    float x = (ang - a0) / span;
    float arc = R + h * sqrt(max(0.0, 1.0 - x * x));
    float flow = fbm4(vec2(ang * 30.0 - t * 0.6 * (mod(fi, 2.0) * 2.0 - 1.0), r * 20.0));
    float prom = smoothstep(0.03, 0.0, abs(r - arc)) * step(abs(x), 1.0) * (0.5 + 0.5 * flow);
    o = over(o, mix(vec3(1.0, 0.35, 0.1), vec3(1.0, 0.75, 0.35), flow), prom * 0.9);
  }
  // the surface: granules boiling, spots, darker at the limb
  vec2 q = c * 6.0;
  vec2 w = vec2(fbm4(q + t * 0.05), fbm4(q + 4.0 - t * 0.04));
  float gran = fbm(q * 1.5 + w * 1.5 + t * 0.03);
  float cells = 1.0 - smoothstep(0.0, 0.4, abs(fbm4(q * 3.0 + w * 2.0 + t * 0.08) - 0.5));
  vec3 surf = mix(vec3(0.95, 0.45, 0.08), vec3(1.0, 0.85, 0.45), gran);
  surf = mix(surf, vec3(1.0, 0.95, 0.75), cells * 0.3);
  float spots = smoothstep(0.72, 0.8, fbm4(c * 3.0 + 9.0));
  surf = mix(surf, vec3(0.25, 0.08, 0.02), spots * 0.8);
  float limb = sqrt(max(0.0, 1.0 - (r / R) * (r / R)));
  surf *= 0.55 + 0.6 * limb;
  float flare = exp(-abs(mod(t, 23.0) - 4.0) * 1.5);
  surf += vec3(1.0, 0.9, 0.7) * flare * 0.35 * limb;
  o = over(o, surf, smoothstep(R + 0.004, R - 0.004, r));
  o = over(o, vec3(1.0, 0.7, 0.3), exp(-abs(r - R) * 60.0) * 0.6);
  gl_FragColor = o;
}