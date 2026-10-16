// Portalab — ambient/asteroids: the « asteroids » ambience (spec 028, B2)
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
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 90.0, t, 0.03));
  vec2 sun = vec2(-0.2, 0.9);
  o = over(o, vec3(1.0, 0.85, 0.6), exp(-length(p - sun) * 2.5) * 0.25);
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float scale = 3.0 + fk * 3.5;
    vec2 g = p * scale + vec2(t * (0.03 + fk * 0.03), sin(t * 0.02 + fk) * 0.3);
    vec2 id = floor(g);
    vec2 f = fract(g) - 0.5;
    float h = hash(id + fk * 7.0);
    if (h < 0.78 - fk * 0.06) continue;
    vec2 at = (vec2(hash(id + 1.3), hash(id + 2.7)) - 0.5) * 0.5;
    vec2 d = f - at;
    float spin = t * (0.3 + hash(id + 4.0)) + h * 6.0;
    d = mat2(cos(spin), -sin(spin), sin(spin), cos(spin)) * d;
    float size = 0.08 + 0.3 * pow(hash(id + 5.0), 2.0);
    float lump = size * (0.75 + 0.45 * fbm4(normalize(d + 1e-4) * 2.0 + h * 10.0));
    float body = smoothstep(lump, lump - 0.02, length(d));
    vec2 toSun = normalize(sun - p);
    float lit = clamp(dot(normalize(d + 1e-4), mat2(cos(spin), -sin(spin), sin(spin), cos(spin)) * toSun) * 0.8 + 0.35, 0.0, 1.0);
    vec3 rock = mix(vec3(0.2, 0.18, 0.17), vec3(0.62, 0.56, 0.5), lit) * (0.75 + 0.35 * fbm4(d * 18.0 + h));
    rock *= 0.6 + 0.4 * (fk / 2.0);
    o = over(o, rock, body * (0.75 + fk * 0.1));
  }
  o = over(o, vec3(1.0, 0.9, 0.75), starfield(p + vec2(t * 0.02, 0.0), 140.0, t * 2.0, 0.03) * 0.5);  // glittering dust
  gl_FragColor = o;
}