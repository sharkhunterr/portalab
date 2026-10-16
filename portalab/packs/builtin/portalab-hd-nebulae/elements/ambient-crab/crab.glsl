// Portalab — ambient/crab: the « crab » ambience (spec 028, B2)
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
  float grow = 1.0 + 0.035 * sin(t * 0.07);
  vec2 q = (p - vec2(0.55 * aspect, 0.5)) * 2.0 / grow;
  q = mat2(0.9, -0.44, 0.44, 0.9) * q;
  vec2 w = vec2(fbm4(q * 1.4 + vec2(t * 0.01, 2.0)), fbm4(q * 1.4 + vec2(6.0, -t * 0.008)));
  float r = length(q * vec2(0.74, 1.0)) + (w.x - 0.5) * 0.3 + (fbm4(q * 3.0) - 0.5) * 0.15;
  float m = smoothstep(1.02, 0.82, r);
  float glow = fbm(q * 2.0 + w * 1.6 + vec2(0.0, t * 0.006));
  vec4 o = vec4(0.0);
  vec3 cyan = mix(vec3(0.12, 0.5, 0.8), vec3(0.5, 0.95, 1.0), glow);
  o = over(o, cyan, m * exp(-r * r * 2.6) * (0.25 + 0.55 * glow));
  // the web: a dense net of fine filaments, and a few thicker strands
  float fine = smoothstep(0.3, 0.62, ridged(q * 4.5 + w * 2.6 + vec2(t * 0.003, 0.0)));
  float strands = smoothstep(0.42, 0.75, ridged(q * 2.2 + w * 1.6 + 4.0));
  vec3 fcol = mix(vec3(1.0, 0.85, 0.55), vec3(1.0, 0.45, 0.12), smoothstep(0.15, 0.6, r));
  fcol = mix(fcol, vec3(0.9, 0.12, 0.06), smoothstep(0.55, 0.95, r));
  fcol = mix(fcol, vec3(0.6, 0.85, 0.3), smoothstep(0.62, 0.9, w.y) * smoothstep(0.3, 0.7, r) * 0.7);
  float reach = 0.35 + 0.65 * smoothstep(0.1, 0.8, r);
  float lace = smoothstep(0.32, 0.6, ridged(q * 9.0 + w * 3.0 + 7.0));
  o = over(o, fcol, clamp(fine * 0.6 + strands * 0.6 + lace * 0.35, 0.0, 1.0) * m * reach);
  o = over(o, vec3(0.95, 0.3, 0.15), smoothstep(1.1, 0.75, r) * smoothstep(0.75, 0.95, r) * fbm4(q * 4.0 - w) * 0.35);
  float pulse = 0.55 + 0.45 * step(0.5, fract(t * 1.5));
  o = over(o, vec3(0.85, 0.95, 1.0), clamp(spiked(p - vec2(0.55 * aspect, 0.5), 0.004) * pulse, 0.0, 1.0));
  o = over(o, vec3(0.75, 0.9, 1.0), starfield(p, 80.0, t, 0.035) * (1.0 - m * 0.6));
  o = over(o, vec3(1.0, 0.9, 0.8), starfield(p + 5.0, 150.0, t, 0.02) * 0.5);
  o = brightStars(o, p, aspect, t, 23.0, 3.0);
  gl_FragColor = o;
}