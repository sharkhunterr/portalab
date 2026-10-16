// Portalab — ambient/cliffs: the « cliffs » ambience (spec 028, B2)
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
  vec2 w = vec2(fbm4(p * 1.4 + vec2(t * 0.006, 0.0)), fbm4(p * 1.4 + vec2(4.0, -t * 0.005)));
  float gas = fbm(p * 1.8 + w * 1.6 + vec2(0.0, -t * 0.004));
  vec3 sky = mix(vec3(0.04, 0.1, 0.3), vec3(0.25, 0.5, 0.88), smoothstep(0.35, 0.85, gas));
  sky = mix(sky, vec3(0.6, 0.85, 0.95), smoothstep(0.75, 0.95, gas) * 0.35);
  float a = (0.3 + 0.3 * gas) * smoothstep(0.15, 0.55, uv.y);
  vec4 o = vec4(sky * a, a);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 85.0, t, 0.045) * smoothstep(0.3, 0.55, uv.y));
  // a mountain range of dust: big swells, crags, a few spires
  float x = p.x;
  float crest = 0.22 + 0.22 * fbm4(vec2(x * 1.1, 1.0)) + 0.06 * fbm4(vec2(x * 3.5, 3.0)) + 0.025 * fbm(vec2(x * 18.0, 5.0));
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float sx = (0.2 + 0.3 * fi + 0.08 * hash(vec2(fi, 4.0))) * aspect;
    crest += (0.06 + 0.06 * hash(vec2(fi, 5.0))) * exp(-pow((x - sx) / (0.09 + 0.06 * hash(vec2(fi, 6.0))), 2.0));
  }
  float d = uv.y - crest + (fbm(vec2(x * 22.0, p.y * 22.0) + w) - 0.5) * 0.035;
  float cliff = smoothstep(0.006, -0.006, d);
  float depth = clamp(-d * 4.0, 0.0, 1.0);
  float fluff = fbm(vec2(x * 6.0, p.y * 7.0) + w * 1.5);
  float grain = fbm(vec2(x * 16.0, p.y * 18.0) + w);
  vec3 rock = mix(vec3(0.85, 0.52, 0.26), vec3(0.26, 0.11, 0.05), depth);
  rock = mix(rock, vec3(0.98, 0.74, 0.44), smoothstep(0.55, 0.85, fluff) * (1.0 - depth * 0.8) * 0.6);
  rock *= 0.6 + 0.35 * grain + 0.2 * fluff;
  o = over(o, rock, cliff * 0.96);
  o = over(o, vec3(1.0, 0.82, 0.55), smoothstep(0.03, 0.0, abs(d)) * 0.55);
  float steam = fbm4(vec2(x * 5.0 + w.x * 1.5, d * 4.0 - t * 0.07)) * smoothstep(-0.01, 0.03, d) * smoothstep(0.3, 0.0, d);
  o = over(o, vec3(0.88, 0.82, 0.78), smoothstep(0.38, 0.75, steam) * 0.5);
  o = brightStars(o, p, aspect, t, 53.0, 6.0);
  gl_FragColor = o;
}