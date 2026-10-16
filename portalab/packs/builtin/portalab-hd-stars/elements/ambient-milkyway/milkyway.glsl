// Portalab — ambient/milkyway: the « milkyway » ambience (spec 028, B2)
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
  vec2 c = p - vec2(0.5 * aspect + t * 0.002, 0.45);
  float ang = 0.55;
  vec2 b = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * c;
  float across = b.y + 0.06 * sin(b.x * 2.0);
  float band = exp(-across * across * 60.0);
  float core = exp(-dot((b - vec2(0.25, 0.0)) * vec2(1.0, 2.2), (b - vec2(0.25, 0.0)) * vec2(1.0, 2.2)) * 18.0);
  float clouds = fbm(b * vec2(2.5, 6.0) + vec2(t * 0.003, 0.0));
  float dust = smoothstep(0.5, 0.75, fbm(b * vec2(4.0, 14.0) + 3.0)) * exp(-across * across * 160.0);
  vec3 glow = mix(vec3(0.35, 0.4, 0.65), vec3(1.0, 0.85, 0.65), core);
  float a = (band * (0.16 + 0.34 * clouds) + core * 0.3) * (1.0 - dust * 0.85);
  o = over(o, glow, a);
  o = over(o, vec3(1.0, 0.97, 0.92), starfield(p, 110.0, t, 0.02 + band * 0.12) * (0.6 + 0.4 * band));
  o = over(o, vec3(0.85, 0.9, 1.0), starfield(p + 2.0, 220.0, t, 0.02 + band * 0.2) * band * 0.7);
  o = over(o, vec3(1.0, 0.95, 0.9), starfield(p + 7.0, 45.0, t, 0.012));
  float ridge = 0.11 + 0.06 * fbm(vec2(p.x * 2.5, 1.0)) + 0.04 * sin(p.x * 4.0 + 0.5);
  o = over(o, vec3(0.015, 0.02, 0.04), smoothstep(0.004, 0.0, uv.y - ridge) * 0.95);
  gl_FragColor = o;
}