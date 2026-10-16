// Portalab — ambient/perseids: the « perseids » ambience (spec 028, B2)
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
  vec4 o = vec4(0.0);
  float band = exp(-abs(uv.y - 0.6 - (uv.x - 0.5) * 0.4) * 5.0) * fbm(p * 3.0);
  o = over(o, vec3(0.55, 0.6, 0.85), band * 0.18);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 90.0, t, 0.035) * smoothstep(0.1, 0.3, uv.y));
  vec2 radiant = vec2(0.8 * aspect, 0.95);
  for (int i = 0; i < 14; i++) {
    float fi = float(i);
    float period = 2.6 + 2.5 * hash(vec2(fi, 1.0));
    float k = floor((t + fi * 1.7) / period);
    float life = fract((t + fi * 1.7) / period) * period / 0.9;
    if (life > 1.3 || hash(vec2(k, fi + 9.0)) < 0.2) continue;
    float a = 3.4 + hash(vec2(k, fi + 2.0)) * 1.4;
    vec2 way = vec2(cos(a), sin(a));
    vec2 head = radiant + way * (0.15 + 0.4 * hash(vec2(k, fi + 3.0)) + life * 0.9);
    vec2 rel = p - head;
    float along = dot(rel, -way);
    float across = abs(dot(rel, vec2(-way.y, way.x)));
    float big = step(0.9, hash(vec2(k, fi + 4.0)));
    float trail = smoothstep(mix(0.0018, 0.004, big), 0.0, across) * smoothstep(0.3 + big * 0.2, 0.0, along) * step(0.0, along);
    float burn = smoothstep(0.0, 0.15, life) * smoothstep(1.3, 0.8, life);
    vec3 col = mix(vec3(0.8, 0.88, 1.0), vec3(0.6, 1.0, 0.7), big);
    o = over(o, col, trail * burn);
    o = over(o, vec3(1.0), exp(-length(rel) * mix(250.0, 90.0, big)) * burn);
  }
  // rolling hills against the sky, a nearer darker ridge
  float far = 0.16 + 0.05 * sin(p.x * 2.3 + 1.0) + 0.04 * fbm4(vec2(p.x * 3.0, 1.0));
  float near = 0.08 + 0.04 * sin(p.x * 4.1 + 2.0) + 0.03 * fbm4(vec2(p.x * 6.0, 4.0));
  o = over(o, vec3(0.04, 0.05, 0.1), smoothstep(0.004, 0.0, uv.y - far) * 0.85);
  o = over(o, vec3(0.015, 0.02, 0.04), smoothstep(0.004, 0.0, uv.y - near) * 0.95);
  gl_FragColor = o;
}